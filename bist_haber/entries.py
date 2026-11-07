"""Üç giriş senaryosu: kırılım, geri çekilme, destekten tepki (2026-11-07, Parça A2).

"Bot her zaman mevcut fiyattan alım önermemeli" geri bildirimi üzerine. Tamamen KODLA hesaplanır (yapay zekâ yok).
Midas'ta koşullu (stop) emir yok: kırılım senaryosu "fiyat alarmı kur, alarm çalınca ve teyit gelince elle al"
olarak yazılır; geri çekilme ve destekten tepki "limit emir" senaryosudur.

Kurallar yaygın teknik yaklaşımlardır; sabitler aşağıda açıkça yazılıdır ve geçmiş veriyle sonradan
ayarlanmamıştır (küçük örnekle eşik değiştirmeme ilkesi). Bilgi/senaryo dilindedir, yatırım tavsiyesi değildir.
Seviyeler yalnızca hesap anına kadarki fiyatlardan çıkar (geleceği görmez).
"""
import math
from typing import Dict, List, Optional, Tuple

BREAKOUT_NEAR_ATR = 2.0      # direnç fiyata en fazla 2 ATR uzaksa kırılım senaryosu gösterilir
BREAKOUT_BUFFER_ATR = 0.2    # alarm çaldıktan sonra tahmini alış: direnç + 0,2 ATR
BREAKOUT_STOP_ATR = 1.0      # SL: kırılan seviyenin 1 ATR altı (fiyat geri dönerse kırılım başarısız)
PULLBACK_ZONE_ATR = 0.3      # fiyat 20 EMA'ya 0,3 ATR'den yakınsa "zaten bölgede"
PULLBACK_STOP_ATR = 1.5      # salınım dibi uygun değilse SL = giriş − 1,5 ATR
PULLBACK_FAR_ATR = 3.0       # bölge fiyattan 3 ATR'den uzaksa "gerçekleşmeyebilir" notu
BOUNCE_NEAR_ATR = 2.0        # destek fiyata en fazla 2 ATR uzaksa destekten tepki senaryosu gösterilir
BOUNCE_ENTRY_ATR = 0.25      # limit: desteğin 0,25 ATR üstü (dokunmadan dönebilir)
BOUNCE_STOP_ATR = 0.75       # SL: desteğin 0,75 ATR altı
TARGET_MIN_ATR = 0.5         # girişe 0,5 ATR'den yakın seviye hedef sayılmaz (gürültü)
TARGET_MAX_ATR = 10.0        # girişe 10 ATR'den uzak seviye hedef sayılmaz: günde ~0,5 ATR ile ~20 işlem günü,
                             # kullanıcının swing vadesi (birkaç gün–birkaç hafta). Test sonucuna bakmadan seçildi.
MAX_STOP_PCT = 15.0          # zarar mesafesi %15'ten büyükse senaryo elverişsiz
VALID_DAYS = {"kirilim": 10, "geri_cekilme": 10, "destek": 5}
DAILY_PROGRESS = 0.5         # vade: fiyatın hedefe günde ~0,5 ATR ilerlediği kaba varsayımı

# Gerçek veri testi (2026-11-07): 44 BIST hissesi, ~2 yıl, 5 günde bir kesim, HABER OLMADAN yalnız teknik kurallar.
# Kurallar bu sonuca bakılarak AYARLANMADI. Panelde aynen gösterilir.
BACKTEST_NOTE = ("Geçmiş test (haber olmadan, 44 BIST hissesi, yaklaşık 2 yıl): emir gerçekleştiğinde TP1'e önce ulaşma "
                 "yaklaşık %33, SL'ye önce düşme yaklaşık %60; ortalama getiri sıfıra yakın. Yani bu teknik kurallar tek başına "
                 "avantaj sağlamadı; riski önceden tanımlamaya yarar. Haber sinyalinin katkısı henüz ölçülmedi.")

NAMES = {"kirilim": "Kırılım (breakout)", "geri_cekilme": "Geri çekilme (pullback)",
         "destek": "Destekten tepki (support bounce)"}


def _levels(t: Dict) -> List[Tuple[float, str]]:
    raw = ((t.get("direnc_20g"), "20 günlük direnç"), (t.get("direnc_60g"), "60 günlük direnç"),
           (t.get("zirve_52h"), "52 haftalık zirve"))
    seen, out = set(), []
    for lvl, name in sorted((x for x in raw if x[0]), key=lambda x: x[0]):
        key = round(lvl, 6)
        if key not in seen:  # aynı fiyattaki seviyeler bir kez sayılır (ilk/en kısa adıyla)
            seen.add(key)
            out.append((lvl, name))
    return out


def _targets(entry: float, risk: float, atr: float, levels: List[Tuple[float, str]]):
    """TP1 = girişin 0,5 ATR'den fazla üstündeki ilk direnç; yoksa 1:2. TP2 = sonraki direnç; yoksa 1:3
    (TP1'in en az 1 risk üstü). Uzak seviyeye atlanmaz; 10 ATR'den uzak seviyeler hedef sayılmaz (not düşülür)."""
    far = entry + TARGET_MAX_ATR * atr
    skipped = [f"{name} ({lvl:.2f} TL, {(lvl / entry - 1) * 100:+.0f}%) swing vadesi için uzak; hedef olarak alınmadı"
               for lvl, name in levels if lvl > far]
    cands = [(lvl, name) for lvl, name in levels if entry + TARGET_MIN_ATR * atr < lvl <= far]
    if cands:
        tp1, b1 = cands[0]
    else:
        tp1, b1 = entry + 2 * risk, "risk/getiri 1:2 (üstte belirgin direnç yok)"
    rest = [(lvl, name) for lvl, name in cands if lvl > tp1 + TARGET_MIN_ATR * atr]
    if rest:
        tp2, b2 = rest[0]
    else:
        tp2 = max(entry + 3 * risk, tp1 + risk)
        b2 = "risk/getiri 1:3 hedefi (üstte başka belirgin direnç yok)" if tp2 == entry + 3 * risk else "TP1 + 1 risk"
    return tp1, b1, tp2, b2, skipped


def _days(entry: float, target: float, atr: float) -> int:
    return max(1, math.ceil((target - entry) / (DAILY_PROGRESS * atr)))


def _finish(kind: str, t: Dict, entry: float, sl: float, sl_basis: str, levels, order: str,
            confirm: str, invalid: str, notes: List[str]) -> Dict:
    price, atr = t["son_fiyat"], t["atr"]
    risk = entry - sl
    tp1, b1, tp2, b2, skipped = _targets(entry, risk, atr, levels)
    notes = notes + skipped
    rr1, rr2 = (tp1 - entry) / risk, (tp2 - entry) / risk
    pct = lambda x: (x / entry - 1) * 100
    stop_pct = -pct(sl)
    if stop_pct > MAX_STOP_PCT:
        quality = "elverişsiz"
        notes = notes + [f"Zarar mesafesi %{stop_pct:.1f}: %{MAX_STOP_PCT:.0f} sınırından büyük"]
    else:
        quality = "elverişsiz" if rr1 < 1 else ("zayıf" if rr1 < 2 else "iyi")
    d1, d2 = _days(entry, tp1, atr), _days(entry, tp2, atr)
    valid = VALID_DAYS[kind]
    return {
        "tur": kind, "ad": NAMES[kind], "emir": order, "giris": entry, "uzaklik_%": (entry / price - 1) * 100,
        "sl": sl, "sl_dayanak": sl_basis, "tp1": tp1, "tp1_dayanak": b1, "tp2": tp2, "tp2_dayanak": b2,
        "sl_%": pct(sl), "tp1_%": pct(tp1), "tp2_%": pct(tp2), "rr1": rr1, "rr2": rr2, "kalite": quality,
        "tp1_gun": d1, "tp2_gun": d2, "gecerlilik_gun": valid, "teyit": confirm, "gecersiz": invalid, "notlar": notes,
        "olumlu": f"Giriş gerçekleşir, fiyat TP1'e ({tp1:.2f} TL, {pct(tp1):+.1f}%) ve sonra TP2'ye ({tp2:.2f} TL, "
                  f"{pct(tp2):+.1f}%) ilerler; kaba tahminle TP1 yaklaşık {d1}, TP2 yaklaşık {d2} işlem günü.",
        "olumsuz": f"Fiyat SL'ye ({sl:.2f} TL) iner: zarar yaklaşık %{stop_pct:.1f} (işlem maliyeti hariç).",
        "iptal": f"{valid} işlem günü içinde giriş koşulu oluşmazsa senaryo geçersiz sayılır; yeniden hesaplanmalı.",
    }


def breakout(t: Dict) -> Dict:
    price, atr = t["son_fiyat"], t["atr"]
    above = [(lvl, name) for lvl, name in _levels(t) if lvl > price * 1.005]
    if not above:
        return {"tur": "kirilim", "ad": NAMES["kirilim"], "uygulanamaz":
                "Fiyat 20/60 günlük direncin ve 52 haftalık zirvenin üstünde ya da çok yakınında: kırılım zaten "
                "gerçekleşmiş olabilir; geri çekilme senaryosuna bakın."}
    level, name = above[0]
    if level - price > BREAKOUT_NEAR_ATR * atr:
        return {"tur": "kirilim", "ad": NAMES["kirilim"], "uygulanamaz":
                f"En yakın direnç ({name}, {level:.2f} TL) fiyata {BREAKOUT_NEAR_ATR:.0f} günlük ortalama hareketten uzak."}
    entry = level + BREAKOUT_BUFFER_ATR * atr
    sl = level - BREAKOUT_STOP_ATR * atr
    notes = []
    if t.get("adx") is not None and t["adx"] < 20:
        notes.append(f"ADX {t['adx']:.0f}: trend gücü zayıf; zayıf trendde kırılımlar daha sık başarısız olur")
    if t.get("bb_sikisma"):
        notes.append("Bollinger sıkışması var: sert hareket olasılığı yüksek (yönü belli değil)")
    if t.get("obv_egilim") == "azalıyor":
        notes.append("OBV azalıyor: kırılım hacimle desteklenmeyebilir")
    out = _finish("kirilim", t, entry, sl, f"kırılan seviyenin ({level:.2f} TL) {BREAKOUT_STOP_ATR:g} ATR altı",
                   [x for x in _levels(t) if x[0] > level], f"Fiyat alarmı: {level:.2f} TL üstü → teyit gelince elle al",
                   f"Günlük kapanış {level:.2f} TL ({name}) üstünde olmalı; hacim 20 günlük ortalamanın üstündeyse "
                   "teyit daha güçlü. Alarm gün içinde çalıp fiyat geri düşerse alım yapılmaz.",
                   f"Kapanış {sl:.2f} TL altına inerse kırılım başarısız sayılır.", notes)
    out["alarm"] = level   # işlem günlüğü: alarm seviyesi (kapanış bunun üstündeyse ertesi gün alınır)
    return out


def pullback(t: Dict) -> Dict:
    price, atr = t["son_fiyat"], t["atr"]
    e20, e50, e200 = t.get("ema20"), t.get("ema50"), t.get("ema200")
    if not (e20 and e50 and e20 > e50 and price > e50 and (e200 is None or e50 > e200)):
        return {"tur": "geri_cekilme", "ad": NAMES["geri_cekilme"], "uygulanamaz":
                "Yükseliş trendi yok (20 EMA > 50 EMA > 200 EMA ve fiyat 50 EMA üstünde koşulu sağlanmıyor)."}
    notes = []
    if price > e20 + PULLBACK_ZONE_ATR * atr:
        entry, basis = e20, "20 günlük üstel ortalama (EMA 20)"
        if price - entry > PULLBACK_FAR_ATR * atr:
            notes.append(f"Geri çekilme bölgesi fiyattan %{(1 - entry / price) * 100:.1f} aşağıda: geçerlilik süresinde "
                         "gerçekleşmeyebilir")
    else:
        entry, basis = price, "fiyat zaten 20 EMA bölgesinde"
        if price < e20:
            notes.append("Fiyat 20 EMA'nın altına sarktı; 50 EMA'ya kadar geri çekilme sürebilir")
    low = t.get("salinim_dibi")
    if low and entry - 3 * atr <= low <= entry - 0.5 * atr:
        sl, sl_basis = low - 0.2 * atr, f"son salınım dibinin ({low:.2f} TL) biraz altı"
    else:
        sl, sl_basis = entry - PULLBACK_STOP_ATR * atr, f"giriş − {PULLBACK_STOP_ATR:g} ATR"
    order = (f"Limit emir: {entry:.2f} TL ({basis})" if entry < price else f"Limit emir: {entry:.2f} TL civarı ({basis})")
    return _finish("geri_cekilme", t, entry, sl, sl_basis, _levels(t), order,
                   "Fiyat bölgeye gelip tepki vermeli (gün içi dönüş ya da yükselen kapanış); bölgede hacimli satış "
                   "varsa beklenmeli.",
                   f"Kapanış 50 EMA ({e50:.2f} TL) altına inerse yükseliş trendi bozulur; ya da SL {sl:.2f} TL.", notes)


def bounce(t: Dict) -> Dict:
    price, atr = t["son_fiyat"], t["atr"]
    support, name = None, ""
    # Destek bugün HARİÇ önceki günlerin en düşüğüdür (bugünkü dip test edilmiş destek değildir; bkz. technical.py).
    s20, s60 = t.get("onceki_destek_20g"), t.get("onceki_destek_60g")
    for lvl, nm in ((s20, "20 günlük destek"), (s60, "60 günlük destek")):
        if lvl and 0 <= price - lvl <= BOUNCE_NEAR_ATR * atr:
            support, name = lvl, nm
            break
    if support is None:
        if s20 and price < s20:
            return {"tur": "destek", "ad": NAMES["destek"], "uygulanamaz":
                    f"Fiyat önceki 20 günün desteğinin ({s20:.2f} TL) altına indi: destek kırıldı, yeni dip oluşuyor "
                    "(düşen bıçak). Tepki senaryosu için fiyatın önce bir dip oluşturması beklenir."}
        return {"tur": "destek", "ad": NAMES["destek"], "uygulanamaz":
                f"Fiyat 20/60 günlük desteğe {BOUNCE_NEAR_ATR:.0f} günlük ortalama hareketten uzak."}
    entry = min(price, support + BOUNCE_ENTRY_ATR * atr)
    sl = support - BOUNCE_STOP_ATR * atr
    notes = []
    if t.get("trend") == "Düşüş":
        notes.append("Trend düşüşte: destek kırılabilir (düşen bıçağı tutma riski)")
    if t.get("rsi14") is not None and t["rsi14"] <= 30:
        notes.append(f"RSI {t['rsi14']:.0f}: aşırı satım; tepki olasılığı ama satış baskısı da güçlü")
    levels = _levels(t)
    if t.get("ema20"):
        levels = sorted(levels + [(t["ema20"], "20 günlük üstel ortalama")], key=lambda x: x[0])
    return _finish("destek", t, entry, sl, f"{name} seviyesinin ({support:.2f} TL) {BOUNCE_STOP_ATR:g} ATR altı", levels,
                   f"Limit emir: {entry:.2f} TL ({name} {support:.2f} TL'nin hemen üstü)",
                   "Destekte tepki görülmeli (alt fitil, yükselen kapanış, hacim artışı); destek gün içinde hacimle "
                   "kırılıyorsa beklenmeli.",
                   f"Kapanış {support:.2f} TL ({name}) altına inerse senaryo geçersiz; SL {sl:.2f} TL.", notes)


def scenarios(t: Optional[Dict]) -> Dict:
    """{"senaryolar": [...], "en_uygun": tur|None, "neden_yok"?}. ATR yoksa senaryo üretilmez."""
    if not t or not t.get("atr"):
        return {"senaryolar": [], "en_uygun": None, "neden_yok": "Günlük ortalama hareket (ATR) hesaplanamadı."}
    items = [breakout(t), pullback(t), bounce(t)]
    usable = [s for s in items if "uygulanamaz" not in s and s["kalite"] != "elverişsiz"]
    # En uygun: en yüksek TP1 risk/getirisi; eşitlikte fiyata en yakın giriş.
    best = max(usable, key=lambda s: (round(s["rr1"], 2), -abs(s["uzaklik_%"])))["tur"] if usable else None
    out = {"senaryolar": items, "en_uygun": best}
    if best is None:
        out["neden_yok"] = "Üç giriş senaryosunun hiçbiri uygun değil (uygulanamaz ya da risk/getiri elverişsiz)."
    return out
