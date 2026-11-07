"""Takvim için KAP geçmişi (2026-11-07, kullanıcı onayı: "Evet, KAP'tan çek").

Bilanço durumu (B2) ve şirket olayları (B3) yalnız kayıtlı bildirimlere bakar; günlük güncelleme penceresi kısa
olduğu için çoğu hisse "bilinmiyor" kalıyordu. Bu modül son N günün KAP listesinden YALNIZ takvim için gereken
konuları kaydeder:
- Liste bilgisi yeterli (metin çekilmez): Finansal Rapor, Sorumluluk Beyanı (...), Faaliyet Raporu (...)
- Form alanları gerekli (yalnız ana sayfa metni, EK İNDİRİLMEZ): Genel Kurul, Kâr Payı, Sermaye Artırımı bildirimleri

Kayıtlar status='context' ile saklanır: yapay zekâ kuyruğuna GİRMEZ, kredi harcamaz. Günlük güncelleme aynı
bildirimi kendi penceresinde görürse normal sıraya alır (kap.collect). KAP bekleme süresi (1,5 sn) korunur; KAP
sınır uygularsa tur bırakılır, eksik metinler sonraki çalıştırmada tamamlanır. Ücretsizdir.
"""
import time
from datetime import datetime, timedelta
from typing import Callable, Dict, Optional

import requests

from . import config, corp_events, kap
from .textutil import effective_date

LIST_ONLY = ("Finansal Rapor", "Sorumluluk Beyanı (", "Faaliyet Raporu (")
EXTENSION_SUBJECT = "Finansal Rapor Ek Süre"   # "Finansal Rapor Ek Süre Taleplerine İlişkin SPK Değerlendirmesi"
CONTEXT_NOTE = "takvim için (analiz edilmez)"


def _wanted(subject: str) -> Optional[str]:
    if subject in corp_events.SUBJECTS:
        return "body"
    if subject == "Finansal Rapor" or subject.startswith(LIST_ONLY[1:]) or subject.startswith(EXTENSION_SUBJECT):
        return "list"
    return None


def backfill(conn, universe: Dict[str, str], days: int = 45, progress: Optional[Callable[[str, float], None]] = None,
             today=None, list_fn=None, page_fn=None, sleep=time.sleep, fetch_pages: bool = True,
             d_from=None, d_to=None) -> Dict[str, int]:
    say = progress or (lambda m, p: None)
    list_fn = list_fn or kap.list_disclosures
    page_fn = page_fn or (lambda index: kap._parse_page(kap._get(kap.DETAIL_URL.format(index=index)).text)[0])
    today = today or datetime.now(config.TR_TZ).date()
    say("KAP bildirim listesi alınıyor...", 0.02)
    d_from = d_from or today - timedelta(days=days - 1)
    d_to = d_to or today
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    items = list_fn(d_from, d_to)
    st = {"listelenen": len(items), "eklenen": 0, "zaten_var": 0, "metin_alinan": 0, "metin_bekleyen": 0,
          "kap_siniri": False}
    for it in items:
        subject = it.get("subject") or ""
        need = _wanted(subject)
        if not need:
            continue
        tickers = [t for t in kap._tickers(it) if t in universe]
        if not tickers:
            continue
        news_id = f"kap:{it['disclosureIndex']}"
        if conn.execute("SELECT 1 FROM news WHERE id=?", (news_id,)).fetchone():
            conn.execute("UPDATE news SET donem=COALESCE(donem, ?) WHERE id=?", (kap.item_period(it), news_id))
            st["zaten_var"] += 1
            continue
        published = datetime.strptime(it["publishDate"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=config.TR_TZ)
        conn.execute(
            "INSERT INTO news(id,source,published_at,effective_date,title,subject,body,url,candidates,status,note,"
            "fetched_at,donem) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (news_id, "kap", published.isoformat(), effective_date(published),
             f"{it.get('kapTitle', '')}: {it.get('summary') or subject}", subject, "" if need == "list" else None,
             kap.DETAIL_URL.format(index=it["disclosureIndex"]), ",".join(tickers), "context", CONTEXT_NOTE, now,
             kap.item_period(it)))
        st["eklenen"] += 1
    conn.commit()
    if list_fn is kap.list_disclosures or getattr(list_fn, "records_coverage", False):
        kap.record_coverage(conn, d_from, d_to, now)
    if not fetch_pages:  # sayfaları arka plan okuyucu (kap_worker) KAP sınırına göre bekleyerek okur
        return st
    rows = conn.execute("SELECT id, subject FROM news WHERE status='context' AND body IS NULL AND subject IN (%s) "
                        "ORDER BY published_at DESC" % ",".join("?" * len(corp_events.SUBJECTS)),
                        corp_events.SUBJECTS).fetchall()
    for i, r in enumerate(rows):
        say(f"Olay bildirimlerinin form alanları okunuyor ({i + 1}/{len(rows)})...", 0.1 + 0.88 * i / max(len(rows), 1))
        try:
            body = page_fn(int(r["id"].split(":")[1]))
        except kap.RateLimited:
            st["kap_siniri"] = True
            st["metin_bekleyen"] += len(rows) - i
            break
        except requests.RequestException:
            st["metin_bekleyen"] += 1
            continue
        finally:
            sleep(config.KAP_REQUEST_DELAY)
        if body and body.strip():
            conn.execute("UPDATE news SET body=? WHERE id=?", (body, r["id"]))
            st["metin_alinan"] += 1
        else:  # sayfa boş: tekrar tekrar denenmesin (olay tarihi çıkarılamaz, kayıt yine durur)
            conn.execute("UPDATE news SET body='', note=? WHERE id=?", (CONTEXT_NOTE + "; sayfa boş", r["id"]))
            st["bos_sayfa"] = st.get("bos_sayfa", 0) + 1
        conn.commit()
    say("Tamamlandı.", 1.0)
    return st


def fill_gaps(conn, universe: Dict[str, str], lookback_days: int = 45, today=None, list_fn=None) -> Dict:
    """Son N günde listesi alınmamış günleri takvim için doldurur (yalnız liste; sayfaları kap_worker okur).
    Uygulama birkaç gün açılmadıysa aradaki bildirimler bilanço/olay takviminden kaçmasın. Yapay zekâya gitmez."""
    today = today or datetime.now(config.TR_TZ).date()
    gaps = kap.coverage_gaps(conn, today - timedelta(days=lookback_days - 1), today)
    if not gaps:
        return {"bosluk_gun": 0, "eklenen": 0}
    ranges, start, prev = [], gaps[0], gaps[0]
    for d in gaps[1:]:
        if (d - prev).days > 1:
            ranges.append((start, prev))
            start = d
        prev = d
    ranges.append((start, prev))
    added = 0
    for a, b in ranges:
        added += backfill(conn, universe, today=today, d_from=a, d_to=b, list_fn=list_fn, fetch_pages=False)["eklenen"]
    return {"bosluk_gun": len(gaps), "eklenen": added, "araliklar": [(a.isoformat(), b.isoformat()) for a, b in ranges]}


def estimate(items, universe) -> Dict[str, int]:
    """Liste alındıktan sonra kaç sayfa okunacağı (süre tahmini için)."""
    n_body = sum(1 for it in items if _wanted(it.get("subject") or "") == "body"
                 and any(t in universe for t in kap._tickers(it)))
    return {"okunacak_sayfa": n_body, "tahmini_dakika": round(n_body * (config.KAP_REQUEST_DELAY + 0.6) / 60, 1)}
