"""FAZ 3 (araştırma): işlem içi MAE/MFE, iki R paydası ve günlük veri belirsizliği; çıkış sonrası hareket AYRI.

İŞLEM İÇİ PENCERE (bist_haber.defter.mae_mfe ile aynı, "gunluk_s2"):
  giriş mumu tam (giriş açılışta, mumun tamamı girişten sonra) · ara mumlar tam · çıkış mumu: açılışta çıkışsa yalnız
  açılış; gün içi çıkışsa yalnız çıkış fiyatı (mumun kalanı çıkıştan sonra olabilir); süre dolduysa (kapanış) tam mum.
  → gün içi çıkışta değer bir ALT SINIRDIR (yaklaşık=1): o gün çıkıştan önce daha kötü/iyi fiyat görülmüş olabilir.
  Fiyat hareketidir, pozisyon K/Z'si değildir (TP1 sonrası kalan yarı pozisyon için de fiyat ölçülür).
R PAYDALARI:
  R_plan  = (fiyat − dolum) / (plan girişi − SL)      journal ve defterle aynı (planlanan risk mesafesi)
  R_dolum = (fiyat − dolum) / (dolum − SL)            gerçek dolumla risk; dolum ≤ SL ise TANIMSIZ (None)
  R_plan, dolum plan girişinin üstündeyse kaybı olduğundan küçük gösterir (Ek H3).
ÇIKIŞ SONRASI (işlem içi DEĞİL): çıkıştan sonraki 10 mumun en yüksek/en düşüğünün çıkış fiyatına göre yüzdesi.
  Yalnız "erken/geç çıkış" bağlamı için; kesin işlem içi ölçüm gibi okunmamalı."""
import sys
from typing import Dict, List, Optional

SONRA_GUN = 10


def _hl(b):
    return b.get("high") or b["close"], b.get("low") or b["close"], b.get("open") or b["close"]


def hesapla(t: Dict, bars: List[Dict], defter_mod) -> Optional[Dict]:
    """t: kabul işlem satırı (islem_oku). bars: hissenin tarih sıralı mumları."""
    i0 = next((i for i, b in enumerate(bars) if b["date"] == t["giris_gunu"]), None)
    if i0 is None:
        return None
    n = t["islem_gunu"]
    held = bars[i0:i0 + n]
    son = t["bacaklar"][-1]
    res = {"islem_gunu": n, "bacaklar": [{"neden": son["neden"], "fiyat": son["fiyat"]}]}
    fill, sl = t["giris_fiyati"], t["sl"]
    risk_plan = t["planlanan_giris"] - sl
    m = defter_mod.mae_mfe(held, fill, res, risk_plan)
    risk_dolum = fill - sl
    out = {"mae_R_plan": m["mae_r"], "mfe_R_plan": m["mfe_r"], "yaklasik": m["yaklasik"],
           "mae_R_dolum": round(m["mae_r"] * risk_plan / risk_dolum, 3) if risk_dolum > 0 and m["mae_r"] is not None else None,
           "mfe_R_dolum": round(m["mfe_r"] * risk_plan / risk_dolum, 3) if risk_dolum > 0 and m["mfe_r"] is not None else None,
           "mae_%": round(m["mae_r"] * risk_plan / fill * 100, 3) if m["mae_r"] is not None else None,
           "mfe_%": round(m["mfe_r"] * risk_plan / fill * 100, 3) if m["mfe_r"] is not None else None,
           "varsayimsal_cikis": t.get("varsayimsal", False)}
    sonra = bars[i0 + n:i0 + n + SONRA_GUN]
    if sonra and son["fiyat"]:
        out["cikis_sonrasi_en_yuksek_%"] = round(100 * (max(_hl(b)[0] for b in sonra) / son["fiyat"] - 1), 3)
        out["cikis_sonrasi_en_dusuk_%"] = round(100 * (min(_hl(b)[1] for b in sonra) / son["fiyat"] - 1), 3)
        out["cikis_sonrasi_gun"] = len(sonra)
    return out


def sinirlar(t: Dict, bars: List[Dict]) -> Optional[Dict]:
    """Ek I2: İŞARET ve SINIR tanımı (R_plan biriminde).
      MAE = (pozisyon açıkken en düşük fiyat − dolum) / (plan girişi − SL)  → NEGATİF ya da 0 (aleyhte hareket)
      MFE = (pozisyon açıkken en yüksek fiyat − dolum) / (plan girişi − SL) → POZİTİF ya da 0 (lehte hareket)
    KESİN BİLİNEN hareket: giriş mumu (giriş açılışta → mumun tamamı girişten sonra), ara mumlar ve çıkış fiyatı.
    OLABİLECEK hareket: gün içi çıkış mumunda çıkıştan ÖNCEKİ kısım bilinmez; o mumun en yüksek/en düşüğü çıkıştan önce
    ya da sonra olmuş olabilir. Kural kısıtları:
      - stopta gün içi çıkış (SL / başabaş): çıkıştan önce fiyat stopun ÜSTÜNDEYDİ (stop ilk dokunuşta satar) →
        MAE KESİN (= çıkış fiyatı dahil); MFE ∈ [kesin, mumun en yükseği] (en yüksek çıkıştan önce olmuş olabilir).
      - hedefte gün içi çıkış (TP2): çıkıştan önce fiyat hedefin ALTINDAYDI → MFE KESİN; MAE ∈ [mumun en düşüğü, kesin].
      - açılışta çıkış ya da süre doldu (kapanış): bilinmeyen kısım yok → ikisi de KESİN.
      - alış fiyatı stopun altında (s3 varsayımsal çıkış): çıkış varsayım olduğundan değerler VARSAYIMSAL.
    Böylece MAE için hesaplanan değer işaretli olarak bir ÜST sınırdır (gerçek MAE ondan küçük ya da eşit, yani daha
    kötü olabilir); büyüklük olarak ALT sınırdır. MFE için hesaplanan değer ALT sınırdır. Varsayım: stop ve hedef emri
    tam seviyesinden dolar (boşluk dışında; boşlukta açılıştan çıkış ayrı durumdur)."""
    i0 = next((i for i, b in enumerate(bars) if b["date"] == t["giris_gunu"]), None)
    if i0 is None:
        return None
    n, fill, risk = t["islem_gunu"], t["giris_fiyati"], t["planlanan_giris"] - t["sl"]
    if risk <= 0:
        return None
    held = bars[i0:i0 + n]
    son = t["bacaklar"][-1]
    neden, cikis = son.get("neden") or "", son.get("fiyat")
    lows, highs = [fill], [fill]
    for b in held[:-1]:
        h, l, _ = _hl(b)
        lows.append(l)
        highs.append(h)
    h, l, o = _hl(held[-1])
    if neden.startswith("SL varsayımı"):
        durum, l_olasi, h_olasi = "varsayimsal", None, None
        lows.append(cikis)
        highs.append(cikis)
    elif neden == "süre doldu" or ("açılış" in neden and n > 1):
        if neden == "süre doldu":
            lows.append(l)
            highs.append(h)
        else:
            lows.append(o)
            highs.append(o)
        durum, l_olasi, h_olasi = "kesin", None, None
    elif neden.startswith("SL") or neden.startswith("başabaş"):
        lows.append(cikis)
        highs.append(cikis)
        durum, l_olasi, h_olasi = "mfe_aralik", None, h
    elif neden.startswith("TP2"):
        lows.append(cikis)
        highs.append(cikis)
        durum, l_olasi, h_olasi = "mae_aralik", l, None
    else:
        lows.append(cikis)
        highs.append(cikis)
        durum, l_olasi, h_olasi = "yaklasik", l, h
    R = lambda x: round((x - fill) / risk, 3)
    mae_k, mfe_k = R(min(lows)), R(max(highs))
    return {"durum": durum, "mae_kesin": mae_k, "mfe_kesin": mfe_k,
            "mae_en_kotu_olasi": R(min(min(lows), l_olasi)) if l_olasi is not None else mae_k,
            "mfe_en_iyi_olasi": R(max(max(highs), h_olasi)) if h_olasi is not None else mfe_k}


if __name__ == "__main__":
    sys.exit("modül; faz3_hesap.py tarafından kullanılır")
