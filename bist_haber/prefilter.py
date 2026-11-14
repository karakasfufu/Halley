"""Python haber ön elemesi (2026-11-14, plan Aşama 3). Yapay zekâ KULLANILMAZ.

Karar: "ai" (yapay zekâ yorumlasın: önemli ya da belirsiz) | "rutin" (yorum gerekmez, analiz sırasına girmez).
İlke: doğruluk önce — emin olunmayan her şey "ai". "Rutin" yalnız şu durumlarda:
  1) KAP konusu yapısı gereği fiyatı etkilemeyen bir süreç/bilgi bildirimiyse (RUTIN_KONU),
  2) koşullu konularda metinde önemli işaret YOKSA (geri alım: süren programın günlük uygulama raporuysa;
     genel kurul: bedelsiz/temettü/birleşme/sermaye gibi bir karar yoksa),
  3) haber sitelerinde (RSS) belirli bir şirket eşleşmesi ve piyasa geneli/sektör anahtar kelimesi yoksa ya da
     yalnız piyasa bülteniyse.
Bu kurallar mevcut analiz talimatıyla (analyzer.FILTER_PROMPT / ANALYSIS_PROMPT) aynı çizgidedir: fon/aracı kurum
alım satımı ve eşik aşımı nötr; genel kurul çağrısı, denetçi seçimi, rutin rapor önemsiz; geri alım programı önemli.
"""
import re
from typing import Dict, Tuple

from .textutil import tr_fold

# Konusu gereği yorum gerektirmeyen KAP bildirimleri (süreç, belge, takvim; fiyat bilgisi taşımaz)
RUTIN_KONU = (
    "Portföy Sınırlamalarına Uyumun Kontrolü", "Merkezi Kayıt Kuruluşu", "Borsada İşlem Gören Tipe Dönüşüm",
    "Tertip İhraç Belgesi", "İhraç Tavanına İlişkin", "Borçlanma Araçları, Yatırım Fonları ve Varant İtfa",
    "Yönetim Kurulu Komiteleri", "Bağımsız Denetim Kuruluşunun Belirlenmesi", "Şirket Merkezi Değişikliği",
    "Finansal Takvim", "Herhangi Bir Otoriteye Mali Tablo Verilmesi", "Yatırımcı Raporu", "İzahname",
    "Hak Kullanım Süreç İptal", "Pay Mali Hak Kullanım İşlemi", "Sermaye Artırımından Elde Edilecek",
    "Halka Arz Fiyatının Belirlenmesinde Esas Alınan Varsayımlara", "Fon Kurucusu Tarafından Yapılan Pay Alım Satım",
    "Kar Payı Avansı Ödemesi", "Esas Sözleşme", "Ödünç Pay", "Tescil", "Vekaletname", "Yatırım Kuruluşu Bildirimi",
)
# Metne bakılarak karar verilen konular: önemli işaret varsa "ai", yoksa "rutin"
# Not: "Pay Alım Satım Bildirimi" burada YOK, hep yapay zekâya gider: SPK II-15.1 md.12 gereği bu bildirimleri
# yönetimde söz sahibi kişiler ve büyük ortaklar yapar (içeriden işlem); ölçümde "rutin" sanılan örneklerin
# bildirimi yapanı yönetim kurulu üyesi/ortak çıktı (2026-11-14).
KOSULLU = {
    # Programın ilk duyurusu / kararı / bitişi önemli; aynı programın günlük uygulama raporu ("Güncelleme mi? Evet")
    # yeni bilgi taşımaz. Güncelleme alanı bulunamazsa güvenli taraf: yapay zekâ.
    "Payların Geri Alınmasına İlişkin Bildirim": (
        r"guncelleme mi \?\s*hayir|^(?![\s\S]*guncelleme mi \?)|"
        r"\A[^\n]*(baslat|yonetim kurulu karar|sona er|tamamla|sonlan|iptal|yeni program|program(i|in) hk)",
        "geri alım programının duyurusu/kararı/sonu"),
    "Genel Kurul İşlemlerine İlişkin Bildirim": (
        r"bedelsiz|sermaye artir|sermaye azalt|kar payi|kar dagit|temettu|birlesme|bolunme|devralma|pay geri alim|"
        r"kayitli sermaye tavan.{0,60}(artir|yukselt)", "genel kurulda sermaye/kâr payı/birleşme kararı"),
}
# Haber sitelerinde: belirli şirket yoksa yalnız piyasa geneli/sektörü doğrudan etkileyen konular yoruma gider
RSS_MAKRO = (r"\b(tcmb|merkez bankasi|ppk|faiz|politika faizi|enflasyon|tufe|ufe|fed\b|ecb|swap|rezerv|cari acik|"
             r"buyume|gsyh|issizlik|kredi notu|not artir|not indir|moody|fitch|s&p|vergi|kdv|otv|tesvik|ihracat yasa|"
             r"ithalat|gumruk|tarife|kota|petrol|brent|dogalgaz|elektrik fiyat|akaryakit|zam|asgari ucret|"
             r"bddk|spk|borsa istanbul|halka arz|savas|ateskes|yaptirim|saldiri|catisma|opec|aramco|hurmuz)")
RSS_BULTEN = (r"(borsa (istanbul )?(gune|gunu|haftaya|haftayi)|bist ?100 (endeksi )?(gune|gunu|yukselis|dusus)|piyasalarda bugun|"
              r"altin fiyatlari|gram altin|ceyrek altin|dolar(/tl)? (kuru )?(bugun|ne kadar)|euro (bugun|ne kadar)|"
              r"kripto|bitcoin|ethereum|gunun ozeti|canli (borsa|piyasa))")


def classify(row) -> Tuple[str, str]:
    """(karar, neden). karar: 'ai' | 'rutin'."""
    src = str(row["source"] or "")
    subject = row["subject"] or ""
    text = tr_fold(f"{row['title'] or ''}\n{(row['body'] or '')[:6000]}")
    if src == "kap":
        for s in RUTIN_KONU:
            if s in subject:
                return "rutin", f"rutin KAP konusu ({s})"
        for s, (pat, label) in KOSULLU.items():
            if s in subject:
                if re.search(pat, text):
                    return "ai", f"{s}: {label} işareti var"
                return "rutin", f"{s}: önemli işaret yok (süren programın günlük uygulaması ya da rutin gündem)"
        return "ai", f"önemli ya da belirsiz KAP konusu ({subject or 'konu yok'})"
    # haber siteleri
    if re.search(RSS_BULTEN, text) and not row["candidates"]:
        return "rutin", "piyasa bülteni / fiyat haberi (belirli şirket yok)"
    if row["candidates"]:
        return "ai", "BIST şirketi geçiyor"
    if re.search(RSS_MAKRO, text):
        return "ai", "piyasa geneli/sektörü etkileyebilecek konu"
    return "rutin", "belirli bir BIST şirketi ya da açıkça etkilenen sektör yok"


def apply(conn, limit_rows=None) -> Dict[str, int]:
    """Analiz sırasındaki (status='new', metni hazır) haberleri sınıflar; 'rutin' olanlar sıradan çıkar
    (status='skipped', not 'Python ön eleme: ...'). Geri alınabilir: not ile işaretlidir."""
    rows = conn.execute("SELECT * FROM news WHERE status='new' AND body IS NOT NULL AND TRIM(body)!=''"
                        + (" LIMIT ?" if limit_rows else ""), ((limit_rows,) if limit_rows else ())).fetchall()
    out = {"incelenen": len(rows), "rutin": 0, "ai": 0}
    for r in rows:
        karar, neden = classify(r)
        if karar == "rutin":
            conn.execute("UPDATE news SET status='skipped', note=? WHERE id=?", ("Python ön eleme: " + neden, r["id"]))
            out["rutin"] += 1
        else:
            out["ai"] += 1
    conn.commit()
    return out
