"""KAP bildirimlerini toplar (Dipnot 2).

KAP'ın resmi, belgelenmiş bir geliştirici API'si yok; bu modül sitenin kendi
kullandığı JSON uç noktasını ve bildirim sayfasını okur. Site değişirse burası
bozulabilir. Ciddi kullanımda lisanslı bir veri sağlayıcı düşünülmeli.
"""
import json
import re
import time
from datetime import date, datetime, timedelta
from typing import Callable, Dict, List, Optional

import requests

from . import config
from .textutil import effective_date, html_to_text, strip_translation, tr_lower

LIST_URL = config.KAP_BASE + "/tr/api/disclosure/members/byCriteria"
DETAIL_URL = config.KAP_BASE + "/tr/Bildirim/{index}"


def _criteria(d_from: date, d_to: date) -> dict:
    return {
        "fromDate": d_from.isoformat(), "toDate": d_to.isoformat(),
        "memberType": "IGS",  # işlem gören şirketler
        "mkkMemberOidList": [], "inactiveMkkMemberOidList": [], "disclosureClass": "",
        "subjectList": [], "isLate": "", "mainSector": "", "sector": "", "subSector": "",
        "marketOidList": [], "index": "", "bdkReview": "", "bdkMemberOidList": [],
        "year": "", "term": "", "ruleType": "", "period": "", "fromSrc": False,
        "srcCategory": "", "disclosureIndexList": [],
    }


def list_disclosures(d_from: date, d_to: date) -> List[dict]:
    def interval(start, end):
        # KAP uzun aralıklarda tam 2000 kayıt döndürebiliyor: kesilmiş listeyi tam sanma.
        # POST liste istekleri de GET metin istekleriyle aynı hız sınırını korur.
        time.sleep(config.KAP_REQUEST_DELAY)
        for wait in (5, 15, None):
            r = requests.post(LIST_URL, json=_criteria(start, end), headers=config.HTTP_HEADERS, timeout=60)
            if r.status_code != 429:
                r.raise_for_status()
                break
            if wait is None:
                raise RateLimited("KAP bildirim listesi için istek sınırı uyguluyor")
            time.sleep(wait)
        items = r.json()
        if not isinstance(items, list):
            raise ValueError("KAP beklenen bildirim listesini döndürmedi")
        if len(items) >= 2000:
            if start == end:
                raise RuntimeError("Tek günlük KAP listesi kayıt sınırına ulaştı; tamlık doğrulanamadı.")
            middle = start + (end - start) // 2
            return interval(start, middle) + interval(middle + timedelta(days=1), end)
        return items

    out = []
    # KAP, başlangıç ve bitişin aynı takvim yılında olmasını istiyor.
    start = d_from
    while start <= d_to:
        end = min(d_to, date(start.year, 12, 31))
        out.extend(interval(start, end))
        start = end + timedelta(days=1)
    return list({str(it["disclosureIndex"]): it for it in out}.values())


class RateLimited(Exception):
    """KAP istek sınırı (HTTP 429) beklemeye rağmen sürüyor."""


def _get(url: str) -> requests.Response:
    """KAP istek sınırına (HTTP 429) takılınca kısa bekleyip tekrar dener; sürerse RateLimited."""
    for wait in (5, 15, None):
        r = requests.get(url, headers=config.HTTP_HEADERS, timeout=60)
        if r.status_code != 429:
            r.raise_for_status()
            return r
        if wait is None:
            raise RateLimited("KAP geçici olarak istek sınırı uyguluyor")
        time.sleep(wait)
    raise AssertionError("unreachable")


def _parse_page(html: str):
    """Bildirim sayfasından (ana metin, ek listesi) çıkarır (Next.js veri akışı)."""
    parts = re.findall(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', html, flags=re.S)
    flight = "".join(json.loads('"' + p + '"') for p in parts)
    attachments = []
    m = re.search(r'"attachments":(\[\{.*?\}\])', flight)
    if m:
        try:
            attachments = json.loads(m.group(1))
        except ValueError:
            pass
    m = re.search(r'"disclosureBody":\["\$(\w+)"\]', flight)
    if not m:
        return "", attachments
    raw = flight.encode("utf-8")
    mm = re.search(rb"(?:^|\n)" + m.group(1).encode() + rb":T([0-9a-f]+),", raw)
    if not mm:
        return "", attachments
    body = raw[mm.end(): mm.end() + int(mm.group(1), 16)].decode("utf-8", "ignore")
    return _clean(html_to_text(body)), attachments


def _pdf_text(data: bytes) -> str:
    # KAP dosyanın başına fazladan bayt ekleyebiliyor; PDF başlığından itibaren al.
    start = data.find(b"%PDF")
    if start < 0:
        return ""
    import io
    import logging
    from pypdf import PdfReader
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    reader = PdfReader(io.BytesIO(data[start:]))
    text = "\n".join((p.extract_text() or "") for p in reader.pages[:config.KAP_ATTACHMENT_PAGES])
    return strip_translation(re.sub(r"[ \t]+", " ", text).strip())


# Bilgi taşımayan rutin ekler (adından tanınır). Örnek: hazirun cetveli, vekaletname.
_ROUTINE_ATTACHMENT = re.compile(
    r"hazirun|hazır bulunan|vekaletname|vekâletname|imza sirk|imza beyan|özgeçmiş|ozgecmis"
    r"|\bttsg\b|_ttsg\b|ticaret sicil|başvuru formu|basvuru formu|talep formu")
# Türkçesi de yüklenmiş belgelerin İngilizce kopyası.
_ENGLISH_ATTACHMENT = re.compile(
    r"\(eng\)|[\s_\-]eng[\s_.\-]|\beng\.pdf$|english|ingilizce|invitation|disclosure policy"
    r"|distribution table|translation|announcement|\bminutes\b|general assembly")


def select_attachments(attachments: List[dict]):
    """(okunacak PDF'ler, atlanan PDF adları). Ek sayısı sınırı yalnızca bilgi taşıyan eklere harcanır.

    İngilizce kopya ancak listede başka (Türkçe) PDF varsa atlanır; tek PDF hiçbir zaman atlanmaz.
    """
    pdfs = [a for a in attachments if str(a.get("fileExtension", "")).lower() == "pdf"]
    keep, skipped = [], []
    for a in pdfs:
        name = tr_lower(str(a.get("fileName", "")))
        if _ROUTINE_ATTACHMENT.search(name):
            skipped.append(a.get("fileName", "PDF"))
        else:
            keep.append(a)
    english = [a for a in keep if _ENGLISH_ATTACHMENT.search(tr_lower(str(a.get("fileName", ""))))]
    if english and len(keep) > len(english):
        skipped += [a.get("fileName", "PDF") for a in english]
        keep = [a for a in keep if a not in english]
    if not keep and pdfs:  # hepsi rutin görünüyorsa yine de ilkini oku; hiçbir şeyi körlemesine atma
        keep, skipped = pdfs[:1], [a.get("fileName", "PDF") for a in pdfs[1:]]
    return keep, skipped


def _attachment_texts(attachments: List[dict]) -> str:
    """Ana metin "açıklama ekte" diyorsa asıl bilgi PDF ektedir; ilk birkaç PDF'yi okur."""
    out = []
    pdfs, skipped = select_attachments(attachments)
    pdfs = [a for a in pdfs if a.get("objId")]
    if skipped:
        out.append("[ATLANAN RUTİN/ÇEVİRİ EKLER: " + "; ".join(skipped) + "]")
    for a in pdfs[:config.KAP_MAX_ATTACHMENTS]:
        time.sleep(config.KAP_REQUEST_DELAY)
        r = _get(f"{config.KAP_BASE}/tr/api/file/download/{a['objId']}")
        if len(r.content) > 5_000_000:
            continue
        try:
            text = _pdf_text(r.content)
        except Exception:  # bozuk/şifreli PDF: atla
            continue
        if text:
            out.append(f"[EK: {a.get('fileName', 'dosya')}]\n{text[:config.KAP_ATTACHMENT_CHARS]}")
    return "\n\n".join(out)


# Ana metin asıl bilginin ekte olduğunu söylüyorsa ekler her durumda okunur.
_POINTS_TO_ATTACHMENT = re.compile(r"\bekte\b|\bekinde\b|\bekteki\b|ek[’']?te yer|sunum|attached", re.I)


def fetch_body(index: int, subject: str = "") -> str:
    """Bildirimin analiz edilecek metnini döndürür.

    - "Finansal Rapor": ana metin rakam içermez → KAP Excel çıktısından finansal özet.
    - Ana metin kısaysa ya da "ekte/sunum" diyorsa → PDF eklerinin metni de eklenir.
    Sayfada metin yoksa "" döner; istek başarısızsa hata fırlatır.
    """
    if "Finansal Rapor" in subject:
        from .financials import fetch_summary
        summary = fetch_summary(index)
        if summary:
            return summary
        time.sleep(config.KAP_REQUEST_DELAY)
    body, attachments = _parse_page(_get(DETAIL_URL.format(index=index)).text)
    if attachments and (len(body) < config.KAP_SHORT_BODY_CHARS or _POINTS_TO_ATTACHMENT.search(body)):
        extra = _attachment_texts(attachments)
        if extra:
            body = f"{body}\n\n{extra}" if body else extra
    return body


_BOILERPLATE = {
    "[CONSOLIDATION_METHOD_TITLE]", "[CONSOLIDATION_METHOD]", "İlgili Şirketler", "Related Companies",
    "[]", "İlgili Fonlar", "Related Funds", "Türkçe", "Turkish", "İngilizce", "English",
}


def _clean(text: str) -> str:
    """Şablon satırlarını ve tekrar eden (TR/EN aynı değer) satırları atar; token tasarrufu."""
    text = re.sub(r"\b[a-z]{2,5}_[A-Za-z0-9]+\|\s*", "", text)  # "oda_XyzAbstract|" etiketleri
    out, prev = [], None
    for line in text.splitlines():
        line = line.strip()
        if not line or line in _BOILERPLATE or line.startswith("http://www.xbrl.org/") or line == prev:
            continue
        out.append(line)
        prev = line
    return strip_translation("\n".join(out))


def _tickers(item: dict) -> List[str]:
    codes = []
    for field in ("stockCodes", "relatedStocks"):
        if item.get(field):
            codes += [c for c in re.split(r"[,\s]+", item[field]) if c]
    return sorted(set(codes))


def collect(conn, universe: Dict[str, str], days: int = 1, fetch_bodies: bool = True,
            progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, int]:
    today = datetime.now(config.TR_TZ).date()
    items = list_disclosures(today - timedelta(days=days - 1), today)
    stats = {"listed": len(items), "new": 0, "out_of_universe": 0, "skipped_subject": 0}
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    for it in items:
        news_id = f"kap:{it['disclosureIndex']}"
        if conn.execute("SELECT 1 FROM news WHERE id=?", (news_id,)).fetchone():
            continue
        tickers = [t for t in _tickers(it) if t in universe]
        if not tickers:
            stats["out_of_universe"] += 1
            continue
        published = datetime.strptime(it["publishDate"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=config.TR_TZ)
        subject = it.get("subject") or ""
        status, note, body = "new", None, None  # body NULL = metin henüz alınmadı
        if any(s in subject for s in config.KAP_SKIP_SUBJECTS):
            status, note, body = "skipped", "konu listesi", ""
            stats["skipped_subject"] += 1
        conn.execute(
            "INSERT INTO news(id,source,published_at,effective_date,title,subject,body,url,candidates,status,note,fetched_at)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (news_id, "kap", published.isoformat(), effective_date(published),
             f"{it.get('kapTitle', '')}: {it.get('summary') or subject}", subject, body,
             DETAIL_URL.format(index=it["disclosureIndex"]), ",".join(tickers), status, note, now),
        )
        stats["new"] += 1
    conn.commit()
    stats["skipped_subject"] += apply_skip_rules(conn)
    if fetch_bodies:
        stats.update(fetch_missing_bodies(conn, progress))
    return stats


def apply_skip_rules(conn) -> int:
    """Atlama listesi sonradan genişlerse, bekleyen bildirimlere de uygula."""
    n = 0
    for s in config.KAP_SKIP_SUBJECTS:
        n += conn.execute("UPDATE news SET status='skipped', note='konu listesi', body=COALESCE(body,'') "
                          "WHERE source='kap' AND status='new' AND subject LIKE ?", (f"%{s}%",)).rowcount
    conn.commit()
    return n


def fetch_missing_bodies(conn, progress: Optional[Callable[[int, int], None]] = None) -> Dict[str, int]:
    """Metni alınmamış bildirimlerin metnini çeker (KAP sınırı yüzünden yavaş: ~1 sn/bildirim).

    Yeni yayımlanan bildirimin sayfası ilk dakikalarda boş gelebiliyor; o zaman metin
    NULL bırakılır ve bir sonraki toplamada tekrar denenir.
    """
    # Eski sürümün başlıkla analize bıraktığı, henüz analiz edilmemiş kayıtları kurtar.
    # Yayın yaşı, metnin alınmasından vazgeçmek için bir gerekçe değildir.
    conn.execute("UPDATE news SET body=NULL, note=NULL WHERE source='kap' AND status='new' "
                 "AND body='' AND note='metin alınamadı, başlıkla analiz'")
    conn.commit()
    rows = conn.execute("SELECT id, published_at, subject FROM news WHERE source='kap' AND status='new' AND body IS NULL"
                        " ORDER BY published_at DESC").fetchall()
    st = {"bodies_fetched": 0, "bodies_pending": 0, "rate_limited": False}
    for i, r in enumerate(rows):
        if progress:
            progress(i, len(rows))
        try:
            body = fetch_body(int(r["id"].split(":")[1]), r["subject"] or "")
        except RateLimited:
            # KAP engelliyor: turu bırak, kalanlar bir sonraki güncellemede okunur.
            st["rate_limited"] = True
            st["bodies_pending"] += len(rows) - i
            break
        except requests.RequestException:
            st["bodies_pending"] += 1
            continue
        finally:
            time.sleep(config.KAP_REQUEST_DELAY)
        if not body.strip():
            conn.execute("UPDATE news SET note='Metin alınamadı; başlıkla analiz yapılmadı.' WHERE id=?", (r["id"],))
            conn.commit()
            st["bodies_pending"] += 1
            continue
        conn.execute("UPDATE news SET body=? WHERE id=?", (body, r["id"]))
        conn.commit()
        st["bodies_fetched"] += 1
    return st
