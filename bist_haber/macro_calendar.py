"""Piyasa geneli makro takvim: TCMB faiz kararları (PPK) ve TÜİK enflasyon (TÜFE) açıklamaları (Parça B1).

Tarihler TAHMİN EDİLMEZ; yalnızca yayımlanmış takvimlerden elle girilir. Takvimde olmayan dönem için "bilinmiyor"
denir. Son kontrol: 2026-11-07.

Kaynaklar:
- PPK 2026 (8 toplantı) ve 21 Ocak 2027: TCMB'nin Aralık 2025 duyurusu. TCMB sitesi otomatik erişime kapalı olduğu
  için duyuruyu aktaran bağımsız kaynaklarla karşılaştırıldı (hepsi aynı): Bloomberg HT (28.12.2025), CNBC-e,
  QNB Invest, 24 Saat. Mart/Nisan/Haziran 2027 yalnız QNB Invest'te → "tek kaynak" işaretli.
- TÜFE 2026: TÜİK Ulusal Veri Yayımlama Takvimi (2 Ocak 2026), Foreks aktarımı; Mayıs (5 Haziran) ve Eylül (5 Ekim)
  ayrıca haber kaynaklarıyla doğrulandı. Gün adları takvimdekiyle birebir tutuyor. 2027 TÜFE takvimi henüz yok.
Saatler: PPK kararı 14:00, TÜFE 10:00 (TR saati).
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
       ("2027-03-18", False), ("2027-04-22", False), ("2027-06-10", False)]  # False = tek kaynak
TUFE = [("2026-01-05", "Aralık 2025"), ("2026-02-03", "Ocak 2026"), ("2026-03-03", "Şubat 2026"),
        ("2026-04-03", "Mart 2026"), ("2026-05-04", "Nisan 2026"), ("2026-06-05", "Mayıs 2026"),
        ("2026-07-03", "Haziran 2026"), ("2026-08-03", "Temmuz 2026"), ("2026-09-03", "Ağustos 2026"),
        ("2026-10-05", "Eylül 2026"), ("2026-11-03", "Ekim 2026"), ("2026-12-03", "Kasım 2026")]

# Yayımlanan takvimin KAPSADIĞI dönemin sonu (son olayın tarihi değil): TÜİK 2026 takvimi 2026'nın tüm TÜFE
# açıklamalarını içerir; TCMB'nin 2027 takvimi (aktarıldığı kadarıyla) yılın ilk yarısını kapsar. Ötesi "bilinmiyor".
KNOWN_UNTIL = {"ppk": "2027-06-30", "tufe": "2026-12-31"}
NAMES = {"ppk": "TCMB faiz kararı (PPK)", "tufe": "TÜİK enflasyon (TÜFE)"}


def events() -> List[Dict]:
    out = [{"tarih": d, "tur": "ppk", "ad": "TCMB faiz kararı (PPK)", "saat": "14:00",
            "dogrulama": "doğrulandı" if ok else "tek kaynak"} for d, ok in PPK]
    out += [{"tarih": d, "tur": "tufe", "ad": f"TÜİK enflasyon (TÜFE, {period} verisi)", "saat": "10:00",
             "dogrulama": "doğrulandı"} for d, period in TUFE]
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
    unknown = [NAMES[k] for k, until in KNOWN_UNTIL.items() if date.fromisoformat(until) < end]
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
    soon = [NAMES[k] for k, until in KNOWN_UNTIL.items() if (date.fromisoformat(until) - today).days < warn_days]
    if not soon:
        return None
    return ("Makro takvimin sonu yaklaştı ya da geçti: " + ", ".join(soon) + ". Yeni yayımlanan takvim "
            "bist_haber/macro_calendar.py dosyasına eklenmeli (tarihler tahmin edilmez).")


def next_of_each(today: date) -> List[Dict]:
    """Her türün bugünden sonraki ilk olayı (pencere dışında olsa da); takvimde yoksa "bilinmiyor"."""
    out = []
    for kind in ("tufe", "ppk"):
        nxt = next((e for e in events() if e["tur"] == kind and e["tarih"] >= today.isoformat()), None)
        out.append(nxt or {"tur": kind, "ad": NAMES[kind], "tarih": None, "dogrulama": "takvimde yok"})
    return out
