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


if __name__ == "__main__":
    sys.exit("modül; faz3_hesap.py tarafından kullanılır")
