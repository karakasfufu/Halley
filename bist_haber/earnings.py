"""Bilanço (finansal rapor) takvimi: yasal son bildirim tarihleri ve şirketin açıklayıp açıklamadığı (Parça B2).

Kural kaynağı: SPK Tebliğ II-14.1 Madde 10–11, değişiklik II-14.1.a (Resmî Gazete 3 Şubat 2017, sayı 29968; metin
2026-11-07'de Resmî Gazete PDF'inden okundu):
- Yıllık: hesap dönemi bitiminden itibaren 60 gün; konsolide finansal tablo hazırlama yükümlülüğü varsa 70 gün.
- Ara dönem (3, 6, 9 aylık): 30 gün; konsolide ise 40 gün. Sınırlı bağımsız denetime tabi ara dönemde borsada işlem
  gören işletmeler için +10 gün. Pratikte 6 aylık raporlar sınırlı denetimlidir → 40 / 50 gün (varsayım, ekranda
  belirtilir).
- Son gün resmi tatile denk gelirse sonraki ilk iş günü (hafta sonu da iş günü sayılmadı: temkinli).
- Banka, sigorta, finansal kiralama, faktoring, finansman şirketleri: kendi özel mevzuatlarında DAHA KISA süre varsa
  o geçerli → bu şirketler için "daha erken olabilir" denir (özel süreler doğrulanmadı).
- SPK geçmişte istisnai ek süre verdi (ör. TMS 29'un ilk yılı): yasal tarih "en geç" bilgisidir, garanti değildir.

Şirketin raporu açıklayıp açıklamadığı yalnız ELDEKİ KAP kayıtlarından bakılır; kayıtlar dönemin başından itibaren
yoksa "bilinmiyor" denir (uydurulmaz). Konsolide olup olmadığı "Sorumluluk Beyanı / Faaliyet Raporu (Konsolide |
Konsolide Olmayan)" bildirimlerinden çıkarılır; bulunamazsa iki tarih birlikte verilir.
"""
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from . import config, market_calendar

SPECIAL_WORDS = ("BANKASI", "BANKA A.Ş", "SİGORTA", "REASÜRANS", "EMEKLİLİK", "FİNANSAL KİRALAMA", "FAKTORİNG",
                 "FİNANSMAN A.Ş", "KATILIM BANKASI", "LEASING")


def _add_days(d: date, n: int) -> date:
    x = d + timedelta(days=n)
    while not market_calendar.is_trading_day(x):  # tatil / hafta sonu → sonraki iş günü
        x += timedelta(days=1)
    return x


def periods_around(today: date) -> List[Dict]:
    """Bugünden önce biten son dönem ve sonraki dönem (gerekirse bir öncekiyle birlikte)."""
    out = []
    for y in (today.year - 1, today.year, today.year + 1):
        for m, label, kind in ((3, "3 aylık", "ara"), (6, "6 aylık", "ara6"), (9, "9 aylık", "ara"),
                               (12, "yıllık", "yillik")):
            end = date(y, m, 31 if m in (3, 12) else 30)
            if kind == "yillik":
                single, consol = _add_days(end, 60), _add_days(end, 70)
            elif kind == "ara6":
                single, consol = _add_days(end, 40), _add_days(end, 50)   # 30/40 + sınırlı denetim 10 gün
            else:
                single, consol = _add_days(end, 30), _add_days(end, 40)
            out.append({"donem": f"{y} {label}", "donem_sonu": end.isoformat(), "son_bireysel": single.isoformat(),
                        "son_konsolide": consol.isoformat(), "tur": kind, "kod": f"{y}/{m // 3}"})
    out.sort(key=lambda p: p["donem_sonu"])
    past = [p for p in out if p["donem_sonu"] < today.isoformat()]
    future = [p for p in out if p["donem_sonu"] >= today.isoformat()]
    return [past[-1], future[0]] if past and future else out[:2]


def _is_special(conn, ticker: str) -> bool:
    row = conn.execute("SELECT name FROM companies WHERE ticker=?", (ticker,)).fetchone()
    name = (row["name"] if row else "") or ""
    return any(w in name.upper() for w in SPECIAL_WORDS)


def _consolidated(conn, ticker: str) -> Optional[bool]:
    like = f"%,{ticker},%"
    rows = conn.execute("SELECT subject FROM news WHERE source='kap' AND (','||candidates||',') LIKE ? AND "
                        "(subject LIKE 'Sorumluluk Beyanı (%' OR subject LIKE 'Faaliyet Raporu (%') "
                        "ORDER BY published_at DESC", (like,)).fetchall()
    # Hem konsolide hem bireysel tablo veren şirket (gerçek örnek: QYATB) konsolide sayılır: yükümlülük varsa süre
    # konsolide süresidir (II-14.1 Md. 10/5, 11/5). Yalnız "Konsolide Olmayan" bildirimi varsa bireysel.
    subjects = [r["subject"] for r in rows]
    if any("(Konsolide)" in s for s in subjects):
        return True
    if any("Konsolide Olmayan" in s for s in subjects):
        return False
    return None


def status(conn, ticker: str, today: Optional[date] = None) -> Dict:
    """Hissenin bilanço durumu: son dönem raporu açıklandı mı, ne zamana kadar açıklanmalı, sıradaki dönem."""
    today = today or datetime.now(config.TR_TZ).date()
    last, nxt = periods_around(today)
    consol = _consolidated(conn, ticker)
    special = _is_special(conn, ticker)
    like = f"%,{ticker},%"
    # Raporun DÖNEMİ KAP listesinden (year/period) eşleştirilir: geç verilen eski dönem raporu (gerçek örnek: BRKO,
    # BTCIM, BSOKE 6 aylık raporları Eylül sonu/Ekim başında) yeni dönem sanılmaz.
    pub = conn.execute("SELECT MIN(published_at) d FROM news WHERE source='kap' AND subject='Finansal Rapor' AND "
                       "(','||candidates||',') LIKE ? AND donem=?", (like, last["kod"])).fetchone()["d"]
    # KAP kaydı yoksa: haber analizi bu dönem için "finansal sonuç" olayı bulduysa (ör. Bloomberg HT bilanço
    # haberi) rapor açıklanmış demektir; kaynağı ayrıca belirtilir.
    via_news = None
    if not pub:
        via_news = conn.execute("SELECT MIN(published_at) d FROM impacts WHERE ticker=? AND event_type='finansal_sonuc' "
                                "AND published_at > ?", (ticker, last["donem_sonu"])).fetchone()["d"]
    from .kap import coverage_gaps
    gaps = coverage_gaps(conn, date.fromisoformat(last["donem_sonu"]) + timedelta(days=1), today, today)
    covered = not gaps   # dönem sonundan bugüne her günün KAP listesi alınmış olmalı
    first_kap = conn.execute("SELECT MIN(day) d FROM kap_coverage").fetchone()["d"]
    deadline = (last["son_konsolide"] if consol else last["son_bireysel"]) if consol is not None else last["son_konsolide"]
    if pub or via_news:
        state = "açıklandı"
    elif covered:
        state = "açıklanmadı" if today.isoformat() <= deadline else "süresi geçti, kayıtlarda yok"
    else:
        state = "bilinmiyor"
    return {"ticker": ticker, "donem": last, "sonraki": nxt, "konsolide": consol, "ozel_mevzuat": special,
            "aciklama_tarihi": (pub or via_news)[:10] if (pub or via_news) else None,
            "kaynak": "KAP finansal rapor bildirimi" if pub else ("haber analizi (finansal sonuç)" if via_news else None),
            "ek_sure": _extension(conn, ticker, last["donem_sonu"]),
            "durum": state, "kapsam_basi": (first_kap or "")[:10], "bosluk": [d.isoformat() for d in gaps][:10],
            "bosluk_sayisi": len(gaps),
            "son_tarih": deadline}


def _extension(conn, ticker: str, since: str) -> Optional[str]:
    """SPK'nın finansal rapor ek süre talebi değerlendirmesi bildirimi (gerçek örnek: TRKNT 13.10.2026). Bildirimin
    tarihi döner; verilen yeni süre bildirim metnindedir (metin okunmaz, kullanıcıya KAP'ı açması söylenir)."""
    row = conn.execute("SELECT MAX(published_at) d FROM news WHERE source='kap' AND subject LIKE 'Finansal Rapor Ek Süre%' "
                       "AND (','||candidates||',') LIKE ? AND published_at > date(?, '-120 day')",
                       (f"%,{ticker},%", since)).fetchone()
    return row["d"][:10] if row and row["d"] else None


def _fmt(d: str) -> str:
    aylar = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
             "Aralık"]
    return f"{int(d[8:10])} {aylar[int(d[5:7]) - 1]} {d[:4]}"


def describe(s: Dict, today: Optional[date] = None) -> str:
    """Panel için tek paragraf, yalnız bilinenler."""
    today = today or datetime.now(config.TR_TZ).date()
    p, n = s["donem"], s["sonraki"]
    both = f"konsolide değilse {_fmt(p['son_bireysel'])}, konsolide ise {_fmt(p['son_konsolide'])}"
    rule = {True: f"konsolide: {_fmt(p['son_konsolide'])}", False: f"konsolide değil: {_fmt(p['son_bireysel'])}",
            None: both}[s["konsolide"]]
    if s["durum"] == "açıklandı":
        text = f"{p['donem']} raporu {_fmt(s['aciklama_tarihi'])} tarihinde açıklandı (kaynak: {s['kaynak']})."
    elif s["durum"] == "açıklanmadı":
        left = market_calendar.trading_days_between(today, date.fromisoformat(s["son_tarih"]))
        text = (f"{p['donem']} raporu henüz açıklanmadı; yasal son gün {rule} (yaklaşık {left} işlem günü). "
                "Açıklama fiyatı sert oynatabilir.")
    elif s["durum"] == "süresi geçti, kayıtlarda yok":
        text = (f"{p['donem']} raporunun yasal süresi doldu ({rule}) ama kayıtlarımızda raporu göremiyoruz; KAP'tan "
                "kontrol edin (gecikme ya da ek süre olabilir).")
    else:
        why = (f"{s['bosluk_sayisi']} günün KAP listesi alınmamış (ilk: {_fmt(s['bosluk'][0])})" if s.get("bosluk")
               else "KAP kayıtları yetersiz")
        text = (f"{p['donem']} raporunun açıklanıp açıklanmadığını bilmiyoruz ({why}; bir sonraki güncellemede "
                f"kendiliğinden tamamlanır). Yasal son gün {rule}.")
    if p.get("tur") == "ara6":
        text += " (6 aylık süreye sınırlı bağımsız denetim için +10 gün eklendi; borsada işlem gören şirketlerde olağan.)"
    if s.get("ek_sure"):
        text += (f" SPK ek süre talebini değerlendirdi ({_fmt(s['ek_sure'])} bildirimi): son tarih farklı olabilir, "
                 "ayrıntı için KAP bildirimini açın.")
    if s["ozel_mevzuat"]:
        text += " Banka/sigorta/finansal kuruluş: kendi mevzuatındaki süre daha kısa olabilir."
    nb = {True: _fmt(n["son_konsolide"]), False: _fmt(n["son_bireysel"])}.get(
        s["konsolide"], f"{_fmt(n['son_bireysel'])} / {_fmt(n['son_konsolide'])}")
    text += f" Sonraki: {n['donem']} raporu en geç {nb}."
    return text


def window_risk(s: Dict, today: date, horizon_days: int) -> Optional[str]:
    """Rapor açıklanmadıysa ya da durum bilinmiyorsa ve son gün işlem vadesi içindeyse risk maddesi."""
    if s["durum"] == "açıklandı":
        candidate = s["sonraki"]["son_konsolide" if s["konsolide"] is not False else "son_bireysel"]
        first_possible = s["sonraki"]["donem_sonu"]
    else:
        candidate, first_possible = s["son_tarih"], None
    end = market_calendar.add_trading_days(today, horizon_days).isoformat()
    if s["durum"] == "açıklanmadı" and today.isoformat() <= candidate <= end:
        return (f"Vade içinde bilanço açıklanacak (yasal son gün {_fmt(candidate)}): sonuç fiyatı sert "
                "oynatabilir, zarar durdur seviyesi boşlukla geçilebilir")
    if s["durum"] == "bilinmiyor" and today.isoformat() <= candidate <= end:
        return (f"Bilanço henüz açıklanmadıysa vade içinde açıklanacak (yasal son gün {_fmt(candidate)}); "
                "açıklanıp açıklanmadığını kayıtlarımızdan bilemiyoruz, KAP'tan kontrol edin")
    if first_possible and first_possible < end and candidate <= end:
        return f"Vade içinde sonraki bilanço açıklanabilir (en geç {_fmt(candidate)})"
    return None
