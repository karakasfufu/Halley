"""Borsa İstanbul işlem günü takvimi: tatiller ve yarım günler (2026-11-07).

Tarihler TAHMİN EDİLMEZ. Kaynaklar (Borsa İstanbul sitesi otomatik erişime kapalı, ECONNRESET):
- 2026: Midas destek sayfası "Borsa İstanbul'un kapalı olduğu özel günler" ve hisse.net (06.12.2025) — iki liste
  birebir aynı. Yarım günlerde pay piyasası 12:40'ta kapanır (Midas).
- 2027: Borsa İstanbul listesi henüz yayımlanmadı. Yalnız 2429 sayılı Kanun'la tarihi SABİT milli tatiller eklendi;
  dini bayram (Ramazan/Kurban) kapanışları ve arefe yarım günleri borsa açıklayınca eklenmeli. Bu yüzden
  RELIGIOUS_KNOWN_UNTIL'den sonrası için uyarı verilir.
Hafta sonuna denk gelen tatiller (ör. 30 Ağustos 2026 Pazar) zaten işlem günü değildir.
"""
from datetime import date, datetime, time, timedelta
from typing import Optional

CHECKED = "2026-11-07"
# Hafta içine denk gelen, pay piyasasının TAM GÜN kapalı olduğu günler.
CLOSED = {
    "2026-01-01": "Yılbaşı", "2026-03-20": "Ramazan Bayramı", "2026-04-23": "Ulusal Egemenlik ve Çocuk Bayramı",
    "2026-05-01": "Emek ve Dayanışma Günü", "2026-05-19": "Atatürk'ü Anma, Gençlik ve Spor Bayramı",
    "2026-05-27": "Kurban Bayramı", "2026-05-28": "Kurban Bayramı", "2026-05-29": "Kurban Bayramı",
    "2026-07-15": "Demokrasi ve Milli Birlik Günü", "2026-10-29": "Cumhuriyet Bayramı",
    # 2027 — yalnız yasayla sabit milli tatiller (hafta içine denk gelenler):
    "2027-01-01": "Yılbaşı", "2027-04-23": "Ulusal Egemenlik ve Çocuk Bayramı", "2027-05-19": "Atatürk'ü Anma, "
    "Gençlik ve Spor Bayramı", "2027-07-15": "Demokrasi ve Milli Birlik Günü", "2027-08-30": "Zafer Bayramı",
    "2027-10-29": "Cumhuriyet Bayramı",
}
# Yarım gün (arefe): pay piyasası 12:40'ta kapanır.
HALF_DAYS = {"2026-03-19": "Ramazan Bayramı arefesi", "2026-05-26": "Kurban Bayramı arefesi",
             "2026-10-28": "Cumhuriyet Bayramı arefesi",
             "2027-10-28": "Cumhuriyet Bayramı arefesi"}  # 28 Ekim öğleden sonrası yasayla tatil (sabit)
HALF_DAY_CLOSE = time(12, 40)
NORMAL_CLOSE = time(18, 0)   # sürekli işlem 18:00'de biter (kapanış seansı 18:10'a kadar)
FIXED_KNOWN_UNTIL = "2027-12-31"      # sabit milli tatiller
RELIGIOUS_KNOWN_UNTIL = "2026-12-31"  # dini bayram kapanışları ve arefe yarım günleri


def is_trading_day(d: date) -> bool:
    return d.weekday() < 5 and d.isoformat() not in CLOSED


def next_trading_day(d: date) -> date:
    d += timedelta(days=1)
    while not is_trading_day(d):
        d += timedelta(days=1)
    return d


def add_trading_days(start: date, n: int) -> date:
    d = start
    for _ in range(n):
        d = next_trading_day(d)
    return d


def trading_days_between(a: date, b: date) -> int:
    """a'dan SONRA b'ye kadar (b dahil) işlem günü sayısı."""
    n, d = 0, a
    while d < b:
        d += timedelta(days=1)
        if is_trading_day(d):
            n += 1
    return n


def session_close(d: date) -> Optional[time]:
    if not is_trading_day(d):
        return None
    return HALF_DAY_CLOSE if d.isoformat() in HALF_DAYS else NORMAL_CLOSE


def effective_trading_day(local: datetime) -> date:
    """Haberin fiyata ilk yansıyabileceği işlem günü: seans kapanışından önce → aynı gün; sonra, tatil ya da hafta
    sonu → sonraki işlem günü. Yarım günlerde kapanış 12:40."""
    d = local.date()
    close = session_close(d)
    if close is None or local.time() >= close:
        return next_trading_day(d)
    return d


def coverage_note(start: date, end: date) -> Optional[str]:
    """Aralık, dini bayram kapanışlarının bilinmediği döneme taşıyorsa uyarı metni."""
    if end.isoformat() > RELIGIOUS_KNOWN_UNTIL:
        return (f"{RELIGIOUS_KNOWN_UNTIL[:4]} sonrası için Borsa İstanbul'un dini bayram kapanışları henüz takvimde yok; "
                "işlem günü sayısı birkaç gün fazla görünebilir.")
    return None
