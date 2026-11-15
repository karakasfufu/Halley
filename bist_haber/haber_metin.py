"""Aşama 6 / haber 2. aşama (2026-11-15, kullanıcı: "Evet pythonla dene"): KAP metnini YAPAY ZEKÂSIZ okuma.

İki parça, eğitim (arastirma/asama6) ve canlı ORTAK kullanır:
- `rule_features(text, ...)`: kurallı okuma — olumlu/olumsuz ifade sayıları, güncelleme mi, metindeki en büyük tutarın
  hissenin günlük işlem hacmine oranı (TL; USD/EUR o günün kuruyla çevrilir).
- `tokens(text)`: kelime listesi (öğrenen model için; ağırlıklar model dosyasında).
Kurallar genel dil bilgisiyle yazıldı, geçmiş sonuçlara bakılarak seçilmedi. Ek PDF'ler okunmaz.
"""
import math
import re
from typing import Dict, Iterable, List, Optional

from .textutil import strip_translation, tr_lower

POS = ("sözleşme imzala", "sözleşmesi imzala", "ihale kazan", "ihaleyi kazan", "en avantajlı teklif", "sipariş al",
       "sipariş alın", "yeni iş", "iş birliği", "işbirliği", "anlaşma imzala", "anlaşmaya var", "teşvik belgesi",
       "kapasite artır", "yatırım kararı", "ihracat", "satın alınması", "satın alma işlemi tamamla", "onaylanmıştır",
       "onay verildi", "ruhsat", "lisans alın", "rekor", "tahsil edil", "üretime başla", "devreye alın", "faaliyete geç",
       "temettü", "kâr payı", "bedelsiz", "geri alım", "fiyat artış", "zam yap", "talep artış", "pazar payı")
NEG = ("dava ", "davası", "davanın", "davaya", "ceza", "iptal", "fesh", "fesih", "zarar", "haciz", "iflas", "konkordato",
       "yangın", "kaza ", "kazası", "patlama",
       "durdur", "soruşturma", "inceleme başlat", "vergi incelemesi", "temerrüt", "tedbir", "kayyum", "gözaltı",
       "istifa", "görevden ayrıl", "kapatıl", "üretime ara", "arıza", "deprem", "sel ", "olumsuz", "kayıp", "düşüş",
       "erteleme", "ertelen", "reddedil", "uzlaşamadı", "tazminat", "icra")
_NUM = r"(\d{1,3}(?:\.\d{3})+(?:,\d+)?|\d+(?:,\d+)?)"
_MULT = {"bin": 1e3, "milyon": 1e6, "milyar": 1e9}
_CUR = r"(tl|türk lirası|try|usd|abd doları|dolar|\$|eur|avro|euro|€)"
_AMOUNT = re.compile(_NUM + r"\s*(bin|milyon|milyar)?\s*" + _CUR)
_AMOUNT_PRE = re.compile(r"(usd|eur|\$|€)\s*" + _NUM + r"\s*(bin|milyon|milyar)?")
_WORD = re.compile(r"[a-zçğıöşü]{3,}")
STOP = {"ile", "olan", "olarak", "için", "bir", "ve", "veya", "bu", "şirketimiz", "şirketimizin", "açıklama", "hayır",
        "evet", "tarafından", "ilişkin", "ilgili", "kamuya", "yapılan", "tarihli", "olup", "edilmiştir", "olduğu",
        "the", "and", "our", "company", "yes", "explanations"}


def clean(text: Optional[str]) -> str:
    return tr_lower(strip_translation(text or ""))


def _num(s: str) -> float:
    return float(s.replace(".", "").replace(",", "."))


def amounts_tl(t: str, usd: Optional[float] = None, eur: Optional[float] = None) -> List[float]:
    out = []
    for m in _AMOUNT.finditer(t):
        v = _num(m.group(1)) * _MULT.get(m.group(2) or "", 1)
        c = m.group(3)
        rate = 1.0 if c in ("tl", "türk lirası", "try") else (usd if c in ("usd", "abd doları", "dolar", "$") else eur)
        if rate:
            out.append(v * rate)
    for m in _AMOUNT_PRE.finditer(t):
        v = _num(m.group(2)) * _MULT.get(m.group(3) or "", 1)
        rate = usd if m.group(1) in ("usd", "$") else eur
        if rate:
            out.append(v * rate)
    return out


def rule_features(texts: Iterable[str], turnover_tl: Optional[float] = None, usd: Optional[float] = None,
                  eur: Optional[float] = None) -> Dict[str, float]:
    """texts: plan öncesi penceredeki Özel Durum metinleri. Metin yoksa hepsi 0 (m_var=0)."""
    f = {"m_var": 0.0, "m_pos": 0.0, "m_neg": 0.0, "m_net": 0.0, "m_guncelleme": 0.0, "m_tutar": 0.0, "m_uzun": 0.0}
    n = 0
    for raw in texts:
        if not raw:
            continue
        n += 1
        t = clean(raw)
        guncel = bool(re.search(r"güncelleme mi\?\s*\n?\s*evet", t))
        f["m_guncelleme"] = max(f["m_guncelleme"], 1.0 if guncel else 0.0)
        body = t.split("açıklamalar", 1)[-1]
        f["m_pos"] += sum(body.count(k) for k in POS)
        f["m_neg"] += sum(body.count(k) for k in NEG)
        f["m_uzun"] = max(f["m_uzun"], math.log10(len(body) + 10))
        if turnover_tl:
            am = amounts_tl(body, usd, eur)
            if am:
                f["m_tutar"] = max(f["m_tutar"], math.log10(1 + max(am) / turnover_tl))
    if n:
        f["m_var"] = 1.0
        f["m_net"] = math.tanh((f["m_pos"] - f["m_neg"]) / 2)
        f["m_pos"], f["m_neg"] = math.log1p(f["m_pos"]), math.log1p(f["m_neg"])
    return f


def tokens(texts: Iterable[str]) -> List[str]:
    """Penceredeki metinlerin tekil kelimeleri ve ikili kelime grupları (öğrenen model girdisi)."""
    out = set()
    for raw in texts:
        t = clean(raw).split("açıklamalar", 1)[-1]
        w = [x for x in _WORD.findall(t) if x not in STOP]
        out.update(w)
        out.update(a + "_" + b for a, b in zip(w, w[1:]))
    return sorted(out)
