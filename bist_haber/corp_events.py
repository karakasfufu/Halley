"""Şirket olayları: genel kurul, kâr payı (temettü), sermaye artırımı tarihleri (Parça B3, 2026-11-07).

Kaynak: eldeki KAP bildirimlerinin YAPILANDIRILMIŞ FORM ALANLARI (etiket satırı + altındaki değer satırı). Serbest
metindeki tarihler kullanılmaz (yanlış eşleşme riski). Alanlar 22 gerçek bildirimde (canlı + pilot veri) incelendi.
Yapay zekâ kullanılmaz, KAP'a yeni istek atılmaz. Aynı olay için birden çok bildirim (güncelleme/düzeltme) varsa EN
SON yayımlanan geçerlidir.

Kâr payı ödeme tablosu (2026-11-07, 6 gerçek dolu örnek: FROTO, SUMAS, MCARD, SDTTR, OYAKC): sütunlar "Teklif Edilen
Hak Kullanım (1) | Kesinleşen Hak Kullanım (2) | Ödeme (3) | Kayıt (4)"; boş hücre metinde düşer. Satır başı "Peşin"
ya da "N. Taksit". 3 tarih → (hak kullanım, ödeme, kayıt); 4 tarih → kesinleşen hak kullanım kullanılır. Tutarlılık:
hak kullanım ≤ kayıt ≤ ödeme olmalı; değilse tarihler etiketlenmez, "bildirimi açın" denir.
"""
import re
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config, market_calendar

SUBJECTS = ("Genel Kurul İşlemlerine İlişkin Bildirim", "Genel Kurul Bildirimi", "Kar Payı Dağıtım İşlemlerine İlişkin Bildirim",
            "Sermaye Artırımı - Azaltımı İşlemlerine İlişkin Bildirim")
_DATE = re.compile(r"^(\d{2})[./](\d{2})[./](\d{4})")
# Eski "Genel Kurul Bildirimi" formunda Türkçe etiketin altında İngilizce etiket satırı olur. Yalnız bu bilinen
# etiketler atlanır ("Evet", "Yoktur" gibi ASCII değerler atlanmasın — gerçek bildirimde yakalanan hata).
ENGLISH_LABELS = {"Date", "Time", "Address", "Agenda", "Minutes", "Fiscal Period"}

# (etiket, olay türü, ekrandaki ad, fiyatı düzeltir mi)
DATE_FIELDS = {
    "gk": [("Genel Kurul Tarihi", "genel_kurul", "Genel kurul toplantısı", False),
           ("GK'na Katılım İçin Pay Sahibi Olunması Gereken Son Tarih", "gk_son_pay",
            "Genel kurula katılım için son pay sahipliği günü", False)],
    "kar": [("Konunun Gündemde Yer Aldığı Genel Kurul Tarihi", "temettu_gk", "Kâr payının görüşüleceği genel kurul", False)],
    "sa": [("Bedelsiz Pay Alma Hakkı Kullanım Başlangıç Tarihi", "bedelsiz_hak",
            "Bedelsiz pay hak kullanımı başlangıcı (fiyat bu gün düzeltilir)", True),
           ("Rüçhan Hakkı Kullanımı Başlangıç Tarihi", "ruchan_bas",
            "Rüçhan hakkı (bedelli) kullanım başlangıcı (fiyat bu gün düzeltilir)", True),
           ("Rüçhan Hakkı Kullanımı Bitiş Tarihi", "ruchan_bit", "Rüçhan hakkı kullanım bitişi", False),
           ("SPK Onay Tarihi", "spk_onay", "Sermaye artırımı SPK onayı", False),
           ("Kayıt Tarihi", "kayit", "Hak sahiplerinin belirlendiği kayıt tarihi", False),
           ("Ödeme Tarihi", "odeme", "Yeni payların hesaplara geçeceği tarih", False)],
}


def _kind(subject: str) -> Optional[str]:
    if subject.startswith("Genel Kurul"):
        return "gk"
    if subject.startswith("Kar Payı"):
        return "kar"
    if subject.startswith("Sermaye Artırımı - Azaltımı"):
        return "sa"
    return None


def _lines(body: str) -> List[str]:
    return [l.strip() for l in (body or "").splitlines() if l.strip()]


def _to_date(text: str) -> Optional[str]:
    m = _DATE.match(text)
    if not m:
        return None
    try:
        return date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
    except ValueError:
        return None


def _value_after(lines: List[str], label: str) -> Optional[str]:
    """Etiket satırının hemen altındaki değer (araya tek bir İngilizce etiket satırı girebilir)."""
    for i, l in enumerate(lines):
        if l == label and i + 1 < len(lines):
            nxt = lines[i + 1]
            if nxt in ENGLISH_LABELS and i + 2 < len(lines):
                nxt = lines[i + 2]
            return nxt
    return None


def _number(text: str) -> Optional[float]:
    t = text.replace(".", "").replace(",", ".") if "," in text else text
    try:
        return float(t)
    except ValueError:
        return None


def _group_line(line: str, ticker: str) -> bool:
    """Pay grubu satırı: "B Grubu, ETILR, TRE..." ya da tek gruplu şirkette "OYAKC, TRA..." (gerçek örnekler)."""
    return bool(re.search(rf"(^|,)\s*{re.escape(ticker)}\s*,\s*TR[A-Z0-9]{{10}}(?![A-Z0-9])", line))


def _gross_dividend(lines: List[str], ticker: str) -> Optional[float]:
    """İşlem gören grubun 1 TL nominal paya brüt nakit kâr payı (TL); taksitliyse TOPLAM satırı."""
    rows = [i for i, l in enumerate(lines) if _group_line(l, ticker)]
    if not rows:
        return None
    for i in rows:  # önce TOPLAM satırı
        if i + 2 < len(lines) and lines[i + 1] == "TOPLAM":
            return _number(lines[i + 2])
    i = rows[0]
    if i + 2 < len(lines) and (lines[i + 1] == "Peşin" or re.match(r"^\d+\. Taksit$", lines[i + 1])):
        return _number(lines[i + 2])
    return None


def _gross_by_row(lines: List[str], ticker: str) -> Dict[str, float]:
    """Nakit tablosunda işlem gören grubun satır etiketine göre brüt TL/pay: {"Peşin": x, "1. Taksit": y, "TOPLAM": z}."""
    out = {}
    for i, l in enumerate(lines):
        if _group_line(l, ticker) and i + 2 < len(lines):
            label = lines[i + 1]
            if (label in ("Peşin", "TOPLAM") or re.match(r"^\d+\. Taksit$", label)) and label not in out:
                v = _number(lines[i + 2])
                if v is not None:
                    out[label] = v
    return out


def _payment_table(body: str):
    """Kâr payı ödeme tablosu → [(satır, hak_kullanım, ödeme, kayıt)] ya da None (yapı tanınmadı)."""
    seg = body.split("Kar Payı Ödeme Tarihleri", 1)[1].split("Pay Olarak Kar Payı", 1)[0]
    lines = _lines(seg)
    if "Kayıt Tarihi (4)" not in lines:
        return None
    rows, i = [], lines.index("Kayıt Tarihi (4)") + 1
    while i < len(lines) and (lines[i] == "Peşin" or re.match(r"^\d+\. Taksit$", lines[i])):
        label, dates, i = lines[i], [], i + 1
        while i < len(lines) and _to_date(lines[i]):
            dates.append(_to_date(lines[i]))
            i += 1
        if len(dates) == 3:
            hak, odeme, kayit = dates
        elif len(dates) == 4:
            _, hak, odeme, kayit = dates
        else:
            return None
        if not (hak <= kayit <= odeme):
            return None
        rows.append((label, hak, odeme, kayit))
    return rows or None


def parse_notice(subject: str, body: str, tickers: List[str], published_at: str, news_id: str) -> List[Dict]:
    kind = _kind(subject or "")
    if not kind:
        return []
    lines = _lines(body)
    base = {"kaynak": news_id, "yayin": published_at, "konu": subject}
    out = []
    fields = list(DATE_FIELDS[kind])
    if kind == "gk" and not _value_after(lines, "Genel Kurul Tarihi"):
        fields.append(("Tarih", "genel_kurul", "Genel kurul toplantısı", False))  # eski "Genel Kurul Bildirimi" formu
    extra = {}
    if kind == "gk":
        extra["tip"] = _value_after(lines, "Genel Kurul Tipi") or _value_after(lines, "Genel Kurul Toplantı Türü")
        extra["saat"] = _value_after(lines, "Genel Kurul Saati") or _value_after(lines, "Saati")
        extra["yapildi"] = _value_after(lines, "Genel Kurul Yapıldı mı?")
        extra["hak_surecleri"] = _value_after(lines, "Gündemde Yer Alan Hak Kullanım Süreçleri")
    if kind == "sa":
        # Tam satır eşleşmesi: "Bedelli Sermaye Artırımında ..." gibi özet satırları tür sayılmaz.
        extra["tip"] = next((l for l in lines if re.match(r"^(Bedelsiz Sermaye Artırımı|Bedelli Sermaye Artırımı"
                                                           r"( \([^)]*\))?|Sermaye Azaltımı( \([^)]*\))?)$", l)), None)
    for ticker in tickers:
        ev_extra = dict(extra)
        if kind == "kar":
            ev_extra["odeme_sekli"] = _value_after(lines, "Nakit Kar Payı Ödeme Şekli")
            ev_extra["brut_tl"] = _gross_dividend(lines, ticker)
            table = _payment_table(body) if "Kar Payı Ödeme Tarihleri" in (body or "") else None
            if table:
                gross = _gross_by_row(lines, ticker)
                for label, hak, odeme, kayit in table:
                    part = "" if label == "Peşin" else f" ({label})"
                    row_extra = dict(ev_extra, brut_tl=gross.get(label, ev_extra["brut_tl"] if label == "Peşin" else None))
                    out.append(dict(base, ticker=ticker, tur="temettu_hak", tarih=hak, fiyat_duzeltir=False,
                                    ad=f"Kâr payı hak kullanım günü{part}: hisse temettüsüz işlem görür, fiyat temettü kadar düşer",
                                    **row_extra))
                    out.append(dict(base, ticker=ticker, tur="temettu_odeme", tarih=odeme, fiyat_duzeltir=False,
                                    ad=f"Kâr payı ödeme günü{part}", **row_extra))
            elif "Kar Payı Ödeme Tarihleri" in (body or ""):
                seg = (body.split("Kar Payı Ödeme Tarihleri", 1)[1].split("Pay Olarak Kar Payı", 1)[0])
                dates = sorted({d for d in (_to_date(x) for x in _lines(seg)) if d})
                for d in dates:
                    out.append(dict(base, ticker=ticker, tur="temettu_tarih", tarih=d, fiyat_duzeltir=False,
                                    ad="Kâr payı ödeme tablosundaki tarih (hak kullanım/ödeme: bildirimi açın)",
                                    **ev_extra))
        for label, tur, name, adjusts in fields:
            val = _value_after(lines, label)
            d = _to_date(val) if val else None
            if d:
                out.append(dict(base, ticker=ticker, tur=tur, tarih=d, ad=name, fiyat_duzeltir=adjusts, **ev_extra))
    return out


def events_for(conn, ticker: str) -> List[Dict]:
    """Hissenin kayıtlı KAP bildirimlerinden olaylar; aynı tür + aynı konu için en son bildirim geçerli."""
    rows = conn.execute("SELECT id, published_at, subject, body, candidates FROM news WHERE source='kap' AND "
                        "(','||candidates||',') LIKE ? AND subject IN (%s) ORDER BY published_at" % ",".join("?" * len(SUBJECTS)),
                        (f"%,{ticker},%", *SUBJECTS)).fetchall()
    latest: Dict = {}
    for r in rows:
        evs = parse_notice(r["subject"], r["body"], [ticker], r["published_at"], r["id"])
        kinds = {e["tur"] for e in evs}
        for k in kinds:  # yeni bildirim aynı türdeki eski tarihleri geçersiz kılar (güncelleme/düzeltme/erteleme)
            latest[k] = [e for e in evs if e["tur"] == k]
    return sorted((e for v in latest.values() for e in v), key=lambda e: e["tarih"])


def upcoming(conn, ticker: str, today: Optional[date] = None, trading_days: int = 15) -> Dict:
    today = today or datetime.now(config.TR_TZ).date()
    end = market_calendar.add_trading_days(today, trading_days).isoformat()
    evs = events_for(conn, ticker)
    ahead = [e for e in evs if today.isoformat() <= e["tarih"] <= end]
    recent = [e for e in evs if (today - timedelta(days=60)).isoformat() <= e["tarih"] < today.isoformat()]
    return {"yaklasan": ahead, "yakin_gecmis": recent, "bitis": end}


def risk_lines(up: Dict, price: Optional[float] = None) -> List[str]:
    """Vade içindeki olaylardan risk maddeleri."""
    out = []
    for e in up["yaklasan"]:
        d = f"{int(e['tarih'][8:10])}.{e['tarih'][5:7]}"
        if e["fiyat_duzeltir"]:
            out.append(f"Vade içinde fiyat düzeltmesi: {d} {e['ad']} — fiyat oranında aşağı düzeltilir; teknik seviyeler "
                       "(SL/TP) ve getiri hesabı buna göre değişir")
        elif e["tur"] in ("temettu_gk", "temettu_tarih", "temettu_hak") and (e.get("brut_tl") or 0) > 0:
            y = f" (brüt {e['brut_tl']:.4f} TL/pay" + (f", fiyata oranı %{e['brut_tl'] / price * 100:.1f})" if price else ")")
            tail = "" if e["tur"] == "temettu_hak" else "; hak kullanım günü fiyat temettü kadar düşer"
            out.append(f"Vade içinde kâr payı süreci: {d} {e['ad']}{y}{tail}")
        elif e["tur"] == "genel_kurul":
            out.append(f"Vade içinde genel kurul: {d} ({e.get('tip') or 'tür belirtilmemiş'})")
    return out


def describe(up: Dict) -> str:
    if not up["yaklasan"] and not up["yakin_gecmis"]:
        return "Kayıtlı KAP bildirimlerinde yaklaşan genel kurul, kâr payı ya da sermaye artırımı tarihi yok."
    fmt = lambda e: f"{int(e['tarih'][8:10])}.{e['tarih'][5:7]}.{e['tarih'][:4]} {e['ad']}" + (
        f" ({e['tip']})" if e.get("tip") and e["tur"] == "genel_kurul" else "")
    parts = []
    if up["yaklasan"]:
        parts.append("Yaklaşan: " + "; ".join(fmt(e) for e in up["yaklasan"]))
    if up["yakin_gecmis"]:
        parts.append("Son 60 gün: " + "; ".join(fmt(e) for e in up["yakin_gecmis"]))
    return " · ".join(parts) + ". (Kaynak: KAP bildirimlerinin form alanları; yalnız kayıtlı bildirimler.)"
