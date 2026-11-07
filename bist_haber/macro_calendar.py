"""Piyasa geneli makro takvim: TCMB faiz kararları (PPK) ve TÜİK enflasyon (TÜFE) açıklamaları (Parça B1).

Tarihler TAHMİN EDİLMEZ; yalnızca yayımlanmış takvimlerden elle girilir. Takvimde olmayan dönem için "bilinmiyor"
denir. Son kontrol: 2026-11-07.

Kaynaklar:
- PPK 2026 (8 toplantı) ve 21 Ocak 2027: TCMB'nin Aralık 2025 duyurusu. TCMB sitesi otomatik erişime kapalı olduğu
  için duyuruyu aktaran bağımsız kaynaklarla karşılaştırıldı (hepsi aynı): Bloomberg HT (28.12.2025), CNBC-e,
  QNB Invest, 24 Saat. Mart/Nisan/Haziran 2027 yalnız QNB Invest'te → "tek kaynak" işaretli.
- TÜFE 2026: TÜİK Ulusal Veri Yayımlama Takvimi (2 Ocak 2026), Foreks aktarımı; Mayıs (5 Haziran) ve Eylül (5 Ekim)
  ayrıca haber kaynaklarıyla doğrulandı. Gün adları takvimdekiyle birebir tutuyor. 2027 TÜFE takvimi henüz yok.
- TCMB Enflasyon Raporu 2026 (12 Şubat, 14 Mayıs, 13 Ağustos, 12 Kasım) ve Finansal İstikrar Raporu (22 Mayıs,
  27 Kasım): TCMB 2026 takvimi — Karar ve CNBC-e/diğer aktarımlar aynı. PPK toplantı özetleri (kararın ~1 hafta
  sonrası): yalnız Karar'da → "tek kaynak" (gün düzeni tutarlı: 29 Ekim tatili nedeniyle özet 30 Ekim).
- Fed (FOMC) 2026–2027: federalreserve.gov resmi takvimi (2026-11-07). Karar ikinci gün 14:00 ABD Doğu saati =
  TR 21:00 (ABD yaz saati) / 22:00 (kış saati): BIST kapandıktan sonra, etkisi ertesi işlem günü. "*" = ekonomik
  projeksiyonlu toplantı (daha çok oynaklık).
- 2026-11-07: TCMB resmi takvim sayfası kullanıcının bilgisayarından okundu (calendar_sync); yukarıdaki 2026 tarihlerinin
  tamamı ve 2027 ilk yarısı (PPK, özet, Enflasyon Raporu, Finansal İstikrar Raporu) resmi olarak doğrulandı.
- Kredi notu 2026: Moody's 23 Ocak / 24 Temmuz, S&P 17 Nisan / 16 Ekim, Fitch 23 Ocak / 17 Temmuz (Foreks 20.12.2025 ve
  Bloomberg HT aynı). Cuma akşamı ABD kapanışından sonra açıklanır → etkisi sonraki işlem günü. Planlı tarihte not
  açıklama zorunluluğu yoktur. 2027 takvimleri henüz eklenmedi.
- VİOP BIST 30 endeks vadeli: vade ayları Şubat/Nisan/Haziran/Ağustos/Ekim/Aralık; son işlem günü vade ayının son
  işlem günü; o gün yarım günse bir önceki iş günü (Borsa İstanbul sözleşme metni). Tarihler bu kuralla hesaplanır.
Saatler: PPK kararı 14:00, TÜFE 10:00 (TR saati); Enflasyon Raporu saati takvimde verilmiyor.
İşlem günleri Borsa İstanbul tatilleri ve yarım günleriyle sayılır (market_calendar).
"""
from datetime import date, timedelta
from typing import Dict, List, Optional

from . import market_calendar

CHECKED = "2026-11-07"
SOURCES = {
    "ppk": "TCMB 2026–2027 PPK takvimi (Bloomberg HT, CNBC-e, QNB Invest, 24 Saat aktarımlarıyla doğrulandı)",
    "tufe": "TÜİK 2026 Ulusal Veri Yayımlama Takvimi (Foreks aktarımı; haber kaynaklarıyla doğrulandı)",
}

PPK = [("2026-01-22", True), ("2026-03-12", True), ("2026-04-22", True), ("2026-06-11", True), ("2026-07-23", True),
       ("2026-09-10", True), ("2026-10-22", True), ("2026-12-10", True), ("2027-01-21", True),
       ("2027-03-18", True), ("2027-04-22", True), ("2027-06-10", True)]  # 2027: TCMB resmi tablo (2026-11-07)
TUFE = [("2026-01-05", "Aralık 2025"), ("2026-02-03", "Ocak 2026"), ("2026-03-03", "Şubat 2026"),
        ("2026-04-03", "Mart 2026"), ("2026-05-04", "Nisan 2026"), ("2026-06-05", "Mayıs 2026"),
        ("2026-07-03", "Haziran 2026"), ("2026-08-03", "Temmuz 2026"), ("2026-09-03", "Ağustos 2026"),
        ("2026-10-05", "Eylül 2026"), ("2026-11-03", "Ekim 2026"), ("2026-12-03", "Kasım 2026")]

ENFLASYON_RAPORU = ["2026-02-12", "2026-05-14", "2026-08-13", "2026-11-12", "2027-02-11", "2027-05-13"]
FINANSAL_ISTIKRAR = ["2026-05-22", "2026-11-27", "2027-05-28"]
PPK_OZET = ["2026-01-29", "2026-03-18", "2026-04-30", "2026-06-18", "2026-07-30", "2026-09-17", "2026-10-30",
            "2026-12-17", "2027-01-28", "2027-03-25", "2027-04-29", "2027-06-17"]
RATINGS = [("2026-01-23", "Moody's"), ("2026-01-23", "Fitch"), ("2026-04-17", "S&P"), ("2026-07-17", "Fitch"),
           ("2026-07-24", "Moody's"), ("2026-10-16", "S&P")]
VIOP_MONTHS = (2, 4, 6, 8, 10, 12)


def viop_expiries(years=(2026, 2027)) -> List[str]:
    """BIST 30 endeks vadeli son işlem günleri (kural: vade ayının son işlem günü; yarım günse önceki iş günü)."""
    out = []
    for y in years:
        for m in VIOP_MONTHS:
            d = date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)
            while not market_calendar.is_trading_day(d) or d.isoformat() in market_calendar.HALF_DAYS:
                d -= timedelta(days=1)
            out.append(d.isoformat())
    return out
# FOMC karar günü (toplantının 2. günü), projeksiyonlu mu (*)
FOMC = [("2026-01-28", False), ("2026-03-18", True), ("2026-04-29", False), ("2026-06-17", True),
        ("2026-07-29", False), ("2026-09-16", True), ("2026-10-28", False), ("2026-12-09", True),
        ("2027-01-27", False), ("2027-03-17", True), ("2027-04-28", False), ("2027-06-09", True),
        ("2027-07-28", False), ("2027-09-15", True), ("2027-10-27", False), ("2027-12-08", True)]
US_DST = {2026: ("2026-03-08", "2026-11-01"), 2027: ("2027-03-14", "2027-11-07")}  # ABD yaz saati aralığı


def fomc_tr_time(d: str) -> str:
    start, end = US_DST[int(d[:4])]
    return "21:00" if start <= d < end else "22:00"


# Yayımlanan takvimin KAPSADIĞI dönemin sonu (son olayın tarihi değil): TÜİK 2026 takvimi 2026'nın tüm TÜFE
# açıklamalarını içerir; TCMB'nin 2027 takvimi (aktarıldığı kadarıyla) yılın ilk yarısını kapsar. Ötesi "bilinmiyor".
BUILTIN_KNOWN_UNTIL = {"ppk": "2027-06-30", "tufe": "2026-12-31", "er": "2027-06-30", "fomc": "2027-12-31",
                       "kredi": "2026-12-31"}
NAMES = {"ppk": "TCMB faiz kararı (PPK)", "tufe": "TÜİK enflasyon (TÜFE)", "er": "TCMB Enflasyon Raporu",
         "fomc": "Fed faiz kararı (FOMC)", "kredi": "Kredi notu değerlendirmesi"}


def _official() -> Dict:
    """calendar_sync ile resmi sayfalardan okunmuş, geçerli veri (yoksa boş)."""
    from . import calendar_sync
    return calendar_sync.load().get("sources", {})


def _merge(builtin: List[str], official: Optional[List[str]], until: Optional[str]) -> List[str]:
    """Resmi listenin kapsadığı dönemde (ilk yılın başı → until) resmi liste geçerlidir; dışında yerleşik liste."""
    if not official:
        return list(builtin)
    start = official[0][:4] + "-01-01"
    return sorted(set(official) | {d for d in builtin if not (start <= d <= until)})


def _month_end(d: str) -> str:
    x = date.fromisoformat(d)
    return (date(x.year + (x.month == 12), 1 if x.month == 12 else x.month + 1, 1) - timedelta(days=1)).isoformat()


def lists() -> Dict:
    """Yerleşik + resmi (otomatik kontrol) birleşik takvim ve kapsam sonları."""
    src = _official()
    tcmb, fed = (src.get("tcmb") or {}).get("data"), (src.get("fed") or {}).get("data")
    known = dict(BUILTIN_KNOWN_UNTIL)
    t_until = _month_end(tcmb["ppk"][-1]) if tcmb else None
    if t_until:
        known["ppk"] = max(known["ppk"], t_until)
        known["er"] = max(known["er"], t_until)
    f_until = (fed[-1][0][:4] + "-12-31") if fed else None
    if f_until:
        known["fomc"] = max(known["fomc"], f_until)
    builtin_fomc = {d: sep for d, sep in FOMC}
    fomc_dates = _merge(list(builtin_fomc), [d for d, _ in fed] if fed else None, f_until)
    fed_sep = {d: sep for d, sep in fed} if fed else {}
    return {
        "ppk": _merge([d for d, _ in PPK], tcmb and tcmb["ppk"], t_until),
        "ozet": _merge(PPK_OZET, tcmb and tcmb["ozet"], t_until),
        "er": _merge(ENFLASYON_RAPORU, tcmb and tcmb["er"], t_until),
        "fir": _merge(FINANSAL_ISTIKRAR, tcmb and tcmb["fir"], t_until),
        "fomc": [(d, fed_sep.get(d, builtin_fomc.get(d, False))) for d in fomc_dates],
        "known": known, "official": {"tcmb": bool(tcmb), "fed": bool(fed)},
    }


def diff_with_builtin(name: str, data) -> List[str]:
    """Resmi sayfadan okunan ile yerleşik takvim arasındaki farklar (kapsanan dönem içinde)."""
    out = []
    if name == "tcmb":
        until = _month_end(data["ppk"][-1])
        pairs = (("PPK kararı", [d for d, _ in PPK], data["ppk"]), ("PPK özeti", PPK_OZET, data["ozet"]),
                 ("Enflasyon Raporu", ENFLASYON_RAPORU, data["er"]),
                 ("Finansal İstikrar Raporu", FINANSAL_ISTIKRAR, data["fir"]))
    else:
        until = data[-1][0][:4] + "-12-31"
        pairs = (("Fed kararı", [d for d, _ in FOMC], [d for d, _ in data]),)
    for label, builtin, official in pairs:
        start = official[0][:4] + "-01-01" if official else "9999"
        b = {d for d in builtin if start <= d <= until}
        o = set(official)
        if o - b:
            out.append(f"{label}: resmi takvimde yeni/değişen tarih: " + ", ".join(sorted(o - b)))
        if b - o:
            out.append(f"{label}: yerleşik takvimde olup resmi takvimde olmayan: " + ", ".join(sorted(b - o)))
    return out


def events() -> List[Dict]:
    L = lists()
    tag = lambda key: "resmi sayfadan kontrol edildi" if L["official"][key] else "doğrulandı"
    out = [{"tarih": d, "tur": "ppk", "ad": "TCMB faiz kararı (PPK)", "saat": "14:00", "dogrulama": tag("tcmb")}
           for d in L["ppk"]]
    out += [{"tarih": d, "tur": "tufe", "ad": f"TÜİK enflasyon (TÜFE, {period} verisi)", "saat": "10:00",
             "dogrulama": "doğrulandı"} for d, period in TUFE]
    out += [{"tarih": d, "tur": "er", "ad": "TCMB Enflasyon Raporu (enflasyon tahminleri)", "saat": "",
             "dogrulama": tag("tcmb")} for d in L["er"]]
    out += [{"tarih": d, "tur": "fir", "ad": "TCMB Finansal İstikrar Raporu", "saat": "", "dogrulama": tag("tcmb")}
            for d in L["fir"]]
    out += [{"tarih": d, "tur": "ozet", "ad": "PPK toplantı özeti", "saat": "", "dogrulama": tag("tcmb")}
            for d in L["ozet"]]
    for d, agency in RATINGS:
        eff = market_calendar.next_trading_day(date.fromisoformat(d)).isoformat()
        out.append({"tarih": d, "tur": "kredi", "ad": f"{agency} Türkiye kredi notu değerlendirmesi (planlı)",
                    "saat": "akşam, BIST kapandıktan sonra", "etki_gunu": eff, "dogrulama": "doğrulandı"})
    for d in viop_expiries():
        out.append({"tarih": d, "tur": "viop", "ad": "VİOP BIST 30 endeks vadeli vade sonu", "saat": "",
                    "dogrulama": "kural (Borsa İstanbul sözleşme metni)"})
    for d, sep in L["fomc"]:
        eff = market_calendar.next_trading_day(date.fromisoformat(d)).isoformat()
        out.append({"tarih": d, "tur": "fomc", "ad": "Fed faiz kararı (FOMC" + (", projeksiyonlu" if sep else "") + ")",
                    "saat": f"TR {fomc_tr_time(d)}, BIST kapandıktan sonra", "etki_gunu": eff,
                    "dogrulama": "resmi sayfadan kontrol edildi" if L["official"]["fed"] else "resmi"})
    return sorted(out, key=lambda e: e["tarih"])


def add_business_days(start: date, n: int) -> date:
    """n işlem günü sonrası (Borsa İstanbul tatilleri hariç; market_calendar)."""
    return market_calendar.add_trading_days(start, n)


def business_days_between(a: date, b: date) -> int:
    """a'dan sonra b'ye kadar (b dahil) işlem günü sayısı (tatiller hariç)."""
    return market_calendar.trading_days_between(a, b)


def upcoming(today: date, trading_days: int = 15) -> Dict:
    """{"olaylar": [... + "is_gunu_sonra"], "bilinmeyen": [tür adı...], "bitis": tarih}. Bugün dahil değildir
    (bugün açıklanan veri zaten fiyatlanıyor olabilir); bugünkü olaylar "bugun": True ile ayrıca döner."""
    end = add_business_days(today, trading_days)
    found = []
    for e in events():
        d = date.fromisoformat(e["tarih"])
        if today <= d <= end:
            found.append(dict(e, is_gunu_sonra=business_days_between(today, d), bugun=d == today))
    unknown = [NAMES[k] for k, until in lists()["known"].items() if date.fromisoformat(until) < end]
    # Borsa İstanbul tatil ve yarım günleri de pencerede gösterilir (işlem yapılamaz / seans 12:40'ta biter).
    d = today
    while d < end:
        d += timedelta(days=1)
        key = d.isoformat()
        if key in market_calendar.CLOSED and d.weekday() < 5:
            found.append({"tarih": key, "tur": "tatil", "ad": f"Borsa kapalı ({market_calendar.CLOSED[key]})",
                          "saat": "tüm gün", "dogrulama": "doğrulandı", "is_gunu_sonra": None, "bugun": False})
        elif key in market_calendar.HALF_DAYS:
            found.append({"tarih": key, "tur": "yarim", "ad": f"Yarım gün ({market_calendar.HALF_DAYS[key]})",
                          "saat": "12:40'ta kapanış", "dogrulama": "doğrulandı",
                          "is_gunu_sonra": business_days_between(today, d), "bugun": False})
    found.sort(key=lambda e: e["tarih"])
    return {"olaylar": found, "bilinmeyen": unknown, "bitis": end.isoformat(),
            "tatil_notu": market_calendar.coverage_note(today, end)}


def stale(today: date, warn_days: int = 30) -> Optional[str]:
    """Takvimin sonuna 30 günden az kaldıysa bakım uyarısı (yeni yıl takvimleri eklenmeli)."""
    soon = [NAMES[k] for k, until in lists()["known"].items() if (date.fromisoformat(until) - today).days < warn_days]
    if not soon:
        return None
    return ("Makro takvimin sonu yaklaştı ya da geçti: " + ", ".join(soon) + ". TCMB ve Fed tarihleri "
            "'Takvimi kontrol et' ile resmi sayfalardan yenilenir; diğerleri (TÜFE, kredi notu) yayımlanınca "
            "bist_haber/macro_calendar.py dosyasına elle eklenmeli (tarihler tahmin edilmez).")


def next_of_each(today: date) -> List[Dict]:
    """Her türün bugünden sonraki ilk olayı (pencere dışında olsa da); takvimde yoksa "bilinmiyor"."""
    out = []
    for kind in ("tufe", "ppk", "er", "fomc"):
        nxt = next((e for e in events() if e["tur"] == kind and e["tarih"] >= today.isoformat()), None)
        out.append(nxt or {"tur": kind, "ad": NAMES[kind], "tarih": None, "dogrulama": "takvimde yok"})
    return out
