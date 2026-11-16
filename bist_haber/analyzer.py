"""OpenAI ile haber analizi (Faz 2).

İlke: LLM karar vermez; haberi sabit şemalı yapılandırılmış veriye çevirir.
Karar (skor/sinyal) report.py'deki kurallarla verilir.

- Aşama 1 (ucuz model): "Bu haber fiyatı anlamlı etkiler mi?"
- Aşama 2 (güçlü model): hisse bazında yön, etki büyüklüğü, kalıcılık, güven.
- Her haber bir kez analiz edilir; sonuç saklanır (önbellek, Dipnot 4).
"""
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Dict, List, Literal, Optional, Tuple

from openai import (AuthenticationError, BadRequestError, OpenAI, PermissionDeniedError,
                    RateLimitError)
from pydantic import BaseModel, Field

from . import config

EventType = Literal[
    "finansal_sonuc", "temettu", "bedelli_sermaye_artirimi", "bedelsiz_sermaye_artirimi",
    "pay_geri_alim", "yeni_is_sozlesme_ihale", "yatirim_kapasite", "birlesme_satin_alma",
    "ortaklik_yapisi_degisikligi", "iceriden_pay_alim_satim", "yonetim_degisikligi",
    "hukuki_ceza_sorusturma", "kredi_derecelendirme", "borclanma_finansman",
    "sektorel_makro", "diger",
]


class FilterResult(BaseModel):
    onemli: bool
    neden: str


class StockImpact(BaseModel):
    hisse: str
    yon: Literal["pozitif", "negatif", "notr"]
    etki: int = Field(ge=1, le=5)
    gerekce: str


class FullAnalysis(BaseModel):
    olay_tipi: EventType
    kalicilik: Literal["kisa", "orta", "uzun"]
    guven: float = Field(ge=0, le=1)
    ozet: str
    etkiler: List[StockImpact]


FILTER_PROMPT = """Sen Borsa İstanbul haberlerini ön eleyen bir asistansın.
Görev: Haberin bir veya daha fazla BIST hissesinin fiyatını ANLAMLI etkileme ihtimali var mı?

Önemli sayılanlar (onemli=true): finansal sonuçlar, temettü, sermaye artırımı, geri alım,
büyük sözleşme/ihale, birleşme-satın alma, ceza/dava, ortaklık yapısı değişikliği,
önemli yatırım veya kapasite değişikliği, faaliyet durdurma, sektörü DOĞRUDAN etkileyen
somut düzenleme/karar (ör. vergi, teşvik, ihracat yasağı).

Önemsiz sayılanlar (onemli=false):
- Genel kurul gündemi/çağrısı, bağımsız denetçi seçimi, rutin rapor duyuruları, derecelendirme
  sözleşmesi yenileme, küçük tutarlı rutin işlemler, tekrarlanan eski bilgi.
- Endeks açılış/kapanış haberleri, "borsa güne yükselişle başladı" türü piyasa bültenleri,
  altın/döviz/kripto fiyat bültenleri, yurt dışı borsa haberleri.
- Belirli bir BIST şirketi veya açıkça etkilenen bir sektör içermeyen genel makro/siyasi haberler.
- Sponsorluk, ödül, vakıf, sosyal sorumluluk, reklam, röportaj, kampanya haberleri.
- Halka açık olmayan şirketlerle ilgili haberler.

Karar kuralı: Haberde belirli bir BIST şirketi ya da açıkça etkilenen bir sektör YOKSA false.
Varsa ve emin değilsen true. "neden" alanını tek kısa cümle yaz."""

ANALYSIS_PROMPT = """Sen Borsa İstanbul için haber analizi yapan bir analistsin. Yatırım tavsiyesi
vermiyorsun; haberi yapılandırılmış veriye dönüştürüyorsun.

KURALLAR
- Yalnızca verilen metne dayan. Metinde olmayan rakam veya olgu uydurma.
- Haberin yayın tarihinden sonra olanlar hakkındaki bilgini (fiyat hareketleri vb.) KULLANMA.
- "hisse" alanına yalnızca Borsa İstanbul işlem kodunu yaz (ör. THYAO). Aday listesindeki
  kodları tercih et. Dolaylı etkilenen başka hisse ancak etkisi açıksa eklenebilir.
- Bir haber farklı hisseleri zıt yönde etkileyebilir (ör. petrol fiyatı artışı: rafineri +, havayolu −).
- Etkilenen hisse yoksa "etkiler" boş liste olabilir. AMA KAP bildirimlerinde bildirimi yapan
  şirket (aday listesi) her zaman "etkiler"de yer almalı; etkisizse yon=notr, etki=1.
- Metnin TAMAMINI oku: [EK: ...] (PDF ek) ve [TAM METİN] (haberin tamamı) bölümleri asıl bilgiyi
  içerebilir. Rakam, beklenti, tarih, karşı taraf gibi ayrıntıları gerekçede kullan.
- Metinde bir ekin "taranmış görüntü" olduğu ya da "okunamadı" notu varsa, o ekteki bilgiyi bilmiyorsun:
  tahmin etme, eksikliği gerekçede belirt ve güveni en fazla 0.6 ver.

ŞİRKET BÜYÜKLÜĞÜ
- Aday listesinde piyasa değeri ve son fiyat verildiyse tutarları buna göre ölçekle
  (ör. 50 milyon TL'lik sözleşme 1 milyar TL'lik şirket için büyük, 300 milyar TL'lik için önemsiz).
- Pay alım satım bildirimlerinde "nominal tutar" pay adedidir (1 pay = 1 TL nominal);
  işlemin piyasa değeri ≈ nominal tutar × işlem fiyatı.

FİNANSAL SONUÇLAR
- [FİNANSAL TABLO ÖZETİ] içindeki "YILLIK DEĞİŞİMLER" kod tarafından hesaplanmıştır; doğru kabul et,
  kendin yeniden hesaplama.
- TMS 29 uygulanıp uygulanmadığını yalnızca verilen belgede açıkça yazıyorsa kabul et.
  Her şirketin veya dönemin enflasyon düzeltmesi içerdiğini varsayma; belirsizse reel büyüme deme.
- Değerlendir: net kâr (ana ortaklık payı) yönü ve büyüklüğü, esas faaliyet kârı (operasyonel güç),
  son çeyreğin önceki yılın aynı çeyreğine göre durumu (trend), zarardan kâra/kârdan zarara geçiş.
  "Net Parasal Pozisyon Kazançları" ve ertelenmiş vergi gibi nakit dışı kalemlerin sonucu
  sürüklediği durumları gerekçede belirt ve etkiyi buna göre sınırla.
- Piyasa beklentisi metinde yoksa beklentiye göre sapmayı bilemezsin: güveni en fazla 0.7 ver.
  Metinde beklenti varsa (ör. "beklentinin üzerinde") bunu en önemli etken say.

YENİ BİLGİ Mİ, ESKİ BİLGİ Mİ?
- "Yapılan Açıklama Güncelleme mi? Evet" ya da "Düzeltme mi? Evet" ise bildirim daha önce duyurulmuş bir
  konunun devamıdır. Eski açıklamada zaten bilinen olayı (ör. sözleşmenin askıya alınması) yeniden
  puanlama; YALNIZCA bu bildirimle gelen yeni bilgiyi değerlendir (ör. yenileme görüşmelerinin başlaması
  olumlu ya da nötr bir gelişmedir). Sadece tablo/sermaye düzeltmesi gibi teknik güncellemeler nötrdür.
- Dönemsel raporlarda (aylık satış, haftalık işlem vb.) projenin başından beri biriken KÜMÜLATİF toplamı
  yeni haber sayma. Yeni bilgi yalnızca son dönemin rakamıdır; düzenli tekrarlanan rutin bir raporsa ve
  metinde önceki dönemlere göre belirgin bir sapma yoksa etki en fazla 1–2 olmalı.

FİNANSAL SIKINTI İŞARETLERİ
- "Finansal yükümlülüklerin yerine getirilmesi", "nakit sıkıntısı", "borç yapılandırma", "konkordato",
  "ödeme güçlüğü", "faaliyetlerin sürdürülebilirliği" gibi ifadeler eşliğinde yapılan işten çıkarma,
  varlık satışı veya yeniden yapılanma ÖNCELİKLE bir sıkıntı sinyalidir: negatif say. "Maliyet tasarrufu
  sağlayacak" diye pozitif yorumlama; şirket bunu iyi niyetle sunsa da metnin bağlamı belirleyicidir.

ŞİRKET BÜYÜKLÜĞÜ BİLİNMİYORSA
- Piyasa değeri verilmediyse, tanınmış büyük bir şirket için küçük bir ceza/tutarın (ör. birkaç on milyon TL)
  etkisini abartma; belirsizliğin ortadan kalkması (soruşturmanın kapanması) da ayrıca değerlendirilmelidir.

PAY ALIM SATIM BİLDİRİMLERİ (olay_tipi iceriden_pay_alim_satim)
- Yöneticinin veya ana ortağın kendi şirketinden ALIMI hafif pozitif, SATIŞI hafif negatif sinyaldir.
  İşlem tutarı piyasa değerine göre anlamlıysa etki 2, küçük/rutin ise etki 1.
- Fon, aracı kurum veya yabancı kurumun alım-satımı ya da sadece eşik aşımı bildirimiyse notr.

ETKİ ÖLÇEĞİ (etki, 1-5; şirketin büyüklüğüne göre değerlendir)
1 = rutin / fiyata etkisi ihmal edilebilir
2 = küçük (ör. yıllık gelirin ~%5'inden küçük iş, beklentiye yakın sonuç)
3 = belirgin (ör. yıllık gelirin ~%5-15'i büyüklüğünde iş, beklentiden belirgin sapma)
4 = büyük (ör. gelirin ~%15-40'ı, çok güçlü/zayıf bilanço, yüksek bedelsiz)
5 = şirket değerini kökten değiştirebilir (birleşme, gelirin >%40'ı, faaliyet durdurma, ağır ceza)
Şirketin büyüklüğü metinden anlaşılmıyorsa bunu gerekçede belirt ve güveni düşür.

KALICILIK: kisa = birkaç gün, orta = birkaç hafta, uzun = aylar.
GÜVEN (guven, 0-1): Metin ne kadar net ve yoruma ne kadar az açık? Belirsiz/söylenti → ≤0.4.

ÖRNEKLER
- "X Enerji, yıllık cirosunun yaklaşık %30'u tutarında yurt dışı EPC sözleşmesi imzaladı."
  → yeni_is_sozlesme_ihale, X: pozitif, etki 4, kalicilik orta, guven 0.8
- "Y Holding genel kurulunu 25 Mart'ta yapacak."
  → diger, etkiler: [] (veya Y: notr, etki 1), guven 0.9
- "Brent petrol %8 yükseldi." → sektorel_makro; rafineri hissesi pozitif etki 2,
  havayolu hissesi negatif etki 2, kalicilik kisa, guven 0.5

"ozet": haberin tek-iki cümlelik Türkçe özeti. "gerekce": o hisse için kısa gerekçe."""


# 2026-11-14 Aşama 2: istemci merkezi YZ servisine taşındı; bütün çağrılar orada kaydedilir.
from .ai_service import LLM  # noqa: E402,F401  (eski ad: analyzer.LLM)
from .harcama import ButceYetersiz  # noqa: E402


def _fmt_tl(v: Optional[float]) -> str:
    if not v:
        return "?"
    if v >= 1e9:
        return f"{v / 1e9:,.1f} milyar TL".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v / 1e6:,.0f} milyon TL".replace(",", ".")


def _user_message(row, universe: Dict[str, str], body_chars: int, stats: Optional[Dict[str, dict]] = None,
                  body: Optional[str] = None) -> str:
    stats = stats or {}
    cands = [c for c in (row["candidates"] or "").split(",") if c]
    lines = []
    for c in cands:
        s = stats.get(c) or {}
        extra = ""
        if s.get("market_cap"):
            extra = f" — piyasa değeri ≈ {_fmt_tl(s['market_cap'])}, son fiyat ≈ {s['last_price']:.2f} TL (gecikmeli)"
        lines.append(f"- {c}: {universe.get(c, '?')}{extra}")
    cand_txt = "\n".join(lines) or "- (aday yok)"
    text = (body if body is not None else (row["body"] or ""))[:body_chars]
    return (f"Kaynak: {row['source']}\nYayın zamanı: {row['published_at']}\n"
            f"Başlık: {row['title']}\nKonu: {row['subject'] or '-'}\n"
            f"Aday hisseler:\n{cand_txt}\n\nMetin:\n{text or '(metin yok)'}")


def _save(conn, news_id, stage, model, result: BaseModel, tin, tout):
    conn.execute(
        "INSERT OR REPLACE INTO analyses(news_id,stage,model,result_json,input_tokens,output_tokens,created_at)"
        " VALUES(?,?,?,?,?,?,?)",
        (news_id, stage, model, result.model_dump_json(), tin, tout,
         datetime.now(config.TR_TZ).isoformat(timespec="seconds")),
    )


PRIORITY_LIQ_TL = 2e6        # tradeplan.LIQ_MIN_TL ile aynı: altında senaryo üretilmez
PRICE_COVERAGE_MIN = 200     # "fiyatı yok = borsada işlem görmüyor" sonucu yalnız evrenin fiyatı indirilmişse
PRIORITY_LABELS = {0: "açık/bekleyen işlem", 1: "likit hisse", 2: "sığ hisse", 3: "fiyatı olmayan şirket"}


def priority_context(conn) -> Dict:
    """Analiz sırası için hisse sınıfları (yapay zekâ yok, yalnız kayıtlı fiyat ve işlem günlüğü)."""
    last = conn.execute("SELECT MAX(date) FROM prices").fetchone()[0]
    liq, priced = {}, set()
    if last:
        rows = conn.execute("SELECT ticker, AVG(close*COALESCE(volume,0)) FROM prices WHERE date>date(?, '-30 day') "
                            "GROUP BY ticker", (last,)).fetchall()
        liq = {r[0]: r[1] or 0 for r in rows}
        priced = {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM prices")}
    held = {r[0] for r in conn.execute("SELECT DISTINCT ticker FROM trade_journal WHERE durum IN "
                                       "('bekliyor','açık','açık (TP1 görüldü)')")}
    return {"liq": liq, "priced": priced, "held": held, "coverage": len(priced) >= PRICE_COVERAGE_MIN}


def priority(row, ctx: Dict) -> int:
    """0 açık/bekleyen işlemi olan hisse · 1 likit · 2 sığ · 3 fiyatı hiç olmayan (yalnız evren fiyatı varsa).
    Bilinmeyen (fiyatı henüz indirilmemiş) hisse geri plana atılmaz: likit sayılır."""
    cands = [c for c in (row["candidates"] or "").split(",") if c]
    if any(c in ctx["held"] for c in cands):
        return 0
    if not cands:
        return 1                      # eşleşmesiz (ör. makro/sektör haberi): ön eleme karar verir
    best = 3
    for c in cands:
        if c not in ctx["priced"]:
            best = min(best, 3 if ctx["coverage"] else 1)
        elif ctx["liq"].get(c, 0) >= PRIORITY_LIQ_TL:
            best = min(best, 1)
        else:
            best = min(best, 2)
    return best


def pending(conn, limit: Optional[int] = None, max_age_days: Optional[int] = None,
            bas_zamani: Optional[str] = None) -> List:
    # body NULL: KAP metni henüz alınamadı → metin gelene kadar bekle.
    # Sıra (2026-11-09): önce açık/bekleyen işlemi olan hisseler, sonra likit, sığ, fiyatı olmayan; her grupta en yeni
    # haber önce (2026-11-06 kullanıcı isteği: taze haber daha değerli). Neden: güncelleme başına 10 haber sınırı var ve
    # bilanço sezonunda kuyruk yüzlerce haber (ölçüm 08.11: 961 bekleyen, 887'si likit hisse) — sınırlı analiz
    # işlem yapılabilecek hisselere gitsin. Maliyet değişmez (aynı adet).
    sql = ("SELECT * FROM news WHERE status='new' AND body IS NOT NULL "
           "AND LENGTH(TRIM(body, char(9)||char(10)||char(13)||' '))>0")
    args = []
    if max_age_days is not None:   # kendiliğinden analizde eski haber atlanır (elle seçimde sınır yok)
        from datetime import timedelta
        cutoff = (datetime.now(config.TR_TZ) - timedelta(days=max_age_days)).isoformat(timespec="seconds")
        sql += " AND published_at>=?"
        args.append(cutoff)
    if bas_zamani is not None:     # O3 (16.11.2026): son iki BIST işlem günü kapsamı (haber_kapsam.kapsam_baslangici)
        sql += " AND published_at>=?"
        args.append(bas_zamani)
    rows = conn.execute(sql + " ORDER BY published_at DESC, id", args).fetchall()
    ctx = priority_context(conn)
    rows = sorted(rows, key=lambda r: priority(r, ctx))     # sıralama kararlı: grup içinde en yeni önce kalır
    return rows[:int(limit)] if limit else rows


def month_spend(conn, now: Optional[datetime] = None) -> float:
    """Bu ay haber analizine harcanan (kayıtlı token × fiyat; ön eleme + analiz + ikinci görüş birlikte)."""
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    now = now or datetime.now(config.TR_TZ)
    ay = now.strftime("%Y-%m")
    r = conn.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses "
                     "WHERE substr(created_at,1,7)=?", (ay,)).fetchone()
    # derin yeniden incelemede analyses satırı yenisiyle değişir; o ay yapılmış ÖNCEKİ analizin maliyeti buradan eklenir
    o = conn.execute("SELECT COALESCE(SUM(eski_input_tokens),0), COALESCE(SUM(eski_output_tokens),0) FROM reanalysis_log "
                     "WHERE durum='tamam' AND eski_ay=?", (ay,)).fetchone()
    return (r[0] + o[0]) * INPUT_USD_PER_TOKEN + (r[1] + o[1]) * OUTPUT_USD_PER_TOKEN


def _avg_out(conn) -> float:
    v = conn.execute("SELECT AVG(output_tokens) FROM analyses WHERE stage='full' AND output_tokens>0").fetchone()[0]
    return float(v or 4000)


HIGH_OUT_DEFAULT = 16000   # geçmiş yokken haber başına üst çıktı varsayımı (ölçülen en fazla 12.961, ikinci görüş dahil)


def _high_out(conn) -> float:
    """Üst tahmin: gözlenen en pahalı haberin %25 fazlası ya da ortalamanın 2 katı (hangisi büyükse).
    2026-11-09: önceki üst tahmin (2 × ortalama) gerçek en pahalı haberin altında kalabiliyordu → bütçe aşılabilirdi."""
    r = conn.execute("SELECT MAX(output_tokens), AVG(output_tokens), COUNT(*) FROM analyses WHERE stage='full' AND "
                     "output_tokens>0").fetchone()
    if not r or not r[2]:
        return float(HIGH_OUT_DEFAULT)
    return max(1.25 * r[0], 2 * r[1])


def row_cost(row, avg_out: float, quality: Optional[str] = None, high_out: Optional[float] = None) -> Tuple[float, float]:
    """Bir haberin tahmini maliyeti (alt, üst $). Alt: ortalama çıktı; üst: ikinci görüş + en pahalı gözlenen çıktı."""
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    f, a = estimate([row])
    if row["source"] == "kap":
        f = 0                      # KAP haberleri ön elemeye girmez (doğrudan analiz)
    low = (f + a) * INPUT_USD_PER_TOKEN + avg_out * OUTPUT_USD_PER_TOKEN
    high = (f + 2 * a) * INPUT_USD_PER_TOKEN + (high_out or 2 * avg_out) * OUTPUT_USD_PER_TOKEN
    if not quality_profile(quality)["second_opinion"]:
        high = low
    return low, high


def estimate_cost(conn, rows, quality: Optional[str] = None) -> Dict[str, float]:
    avg, hi_out = _avg_out(conn), _high_out(conn)
    costs = [row_cost(r, avg, quality, hi_out) for r in rows]
    return {"adet": len(rows), "low_usd": sum(c[0] for c in costs), "high_usd": sum(c[1] for c in costs)}


def within_budget(conn, rows, budget_usd: Optional[float], quality: Optional[str] = None,
                  gunluk_usd: Optional[float] = None):
    """Bütçeye sığan haberler (sıra korunur; her birinin ÜST tahmini sayılır). (seçilen, bütçe dışı kalan sayısı).
    O3 (16.11.2026): aylık bütçe verildiğinde günlük sınır da uygulanır; daha kısıtlayıcı olan geçerlidir."""
    if budget_usd is None:
        return list(rows), 0
    from . import haber_kapsam
    left = haber_kapsam.butce_durumu(conn, budget_usd, gunluk_usd)["kalan"]
    avg, hi_out = _avg_out(conn), _high_out(conn)
    keep = []
    for r in rows:
        hi = row_cost(r, avg, quality, hi_out)[1]
        if hi > left:
            break
        keep.append(r)
        left -= hi
    return keep, len(rows) - len(keep)


def estimate(rows) -> Tuple[int, int]:
    """Kaba token tahmini (~4 karakter = 1 token)."""
    f = sum(len(r["title"]) + min(len(r["body"] or ""), config.FILTER_BODY_CHARS) + 1200 for r in rows) // 4
    a = sum(len(r["title"]) + min(len(r["body"] or ""), config.MAX_BODY_CHARS) + 3500 for r in rows) // 4
    return f, a


def fetch_article(url: str) -> str:
    """Haber sitesindeki makalenin tam metni (RSS sadece kısa özet veriyor)."""
    try:
        import requests
        import trafilatura
        r = requests.get(url, headers=config.HTTP_HEADERS, timeout=20)
        r.raise_for_status()
        return trafilatura.extract(r.text, include_comments=False, include_tables=True,
                                   favor_precision=True) or ""
    except Exception:
        return ""


def _needs_second_opinion(a: "FullAnalysis", min_impact: Optional[int] = None) -> bool:
    """Büyük etkili ya da belirsiz yönlü kararlar ikinci, bağımsız bir analizle kontrol edilir."""
    limit = config.SECOND_OPINION_MIN_IMPACT if min_impact is None else min_impact
    return any(i.etki >= limit or (i.yon != "notr" and a.guven < 0.6) for i in a.etkiler)


def quality_profile(name: Optional[str] = None) -> dict:
    """Analiz kalitesi profili. Bilinmeyen/boş ad varsayılan (yüksek doğruluk) profile döner."""
    return dict(config.QUALITY_PROFILES.get(name or config.DEFAULT_QUALITY,
                                            config.QUALITY_PROFILES[config.DEFAULT_QUALITY]))


def _reconcile(a1: "FullAnalysis", a2: "FullAnalysis") -> Tuple["FullAnalysis", Dict[str, str]]:
    """İki bağımsız analizi birleştirir. Yön çelişirse etki nötrlenir ve işaretlenir."""
    flags: Dict[str, str] = {}
    second = {i.hisse.strip().upper(): i for i in a2.etkiler}
    merged = []
    for i in a1.etkiler:
        j = second.pop(i.hisse.strip().upper(), None)
        if j is None:
            # İkinci analiz bu hisseyi hiç görmedi → etkiyi yarıya indir, işaretle
            merged.append(i.model_copy(update={"etki": max(1, i.etki // 2)}))
            flags[i.hisse] = "tek görüş"
        elif i.yon != j.yon:
            merged.append(i.model_copy(update={"yon": "notr", "etki": 1,
                                               "gerekce": f"ÇELİŞKİLİ: 1) {i.yon}: {i.gerekce} 2) {j.yon}: {j.gerekce}"}))
            flags[i.hisse] = "çelişkili"
        else:
            merged.append(i.model_copy(update={"etki": min(i.etki, j.etki)}))  # temkinli: küçük olanı al
            if abs(i.etki - j.etki) >= 2:
                flags[i.hisse] = "etki belirsiz"
            else:
                flags[i.hisse] = "teyitli"
    guven = min(a1.guven, a2.guven)
    return a1.model_copy(update={"etkiler": merged, "guven": guven}), flags


def _work(llm: LLM, row, universe: Dict[str, str], stats: Dict[str, dict], quality: Optional[dict] = None):
    """Tek haber için ağ ve LLM işleri (iş parçacığında; veritabanına dokunmaz).

    Dönen sözlük _store tarafından kaydedilir. quality verilmezse yüksek doğruluk profili kullanılır
    (geçmiş veri pilotu bu yolu kullanır ve kalitesi düşürülmez).
    """
    q = quality or quality_profile()
    res = {"filter": None, "analysis": None, "flags": {}, "article": None, "tokens": [0, 0]}

    from .ai_service import LLM as _ServiceLLM

    def call(model, prompt, msg, schema, effort=None, islem=None):
        if isinstance(llm, _ServiceLLM):        # merkezi servis: işlem ve haber no kaydedilir
            out, tin, tout = llm.parse(model, prompt, msg, schema, reasoning_effort=effort, islem=islem, ref=row["id"])
        else:                                   # testlerdeki sahte istemciler
            out, tin, tout = llm.parse(model, prompt, msg, schema, reasoning_effort=effort)
        res["tokens"][0] += tin
        res["tokens"][1] += tout
        return out

    body = row["body"] or ""
    if row["source"] == "kap":
        # Rutin KAP konuları zaten kuralla atlandı (config.KAP_SKIP_SUBJECTS); kalanlar şirketin
        # kendi özel durum açıklamaları. Ön eleme bunları fazla katı eliyordu → doğrudan analiz.
        res["filter"] = FilterResult(onemli=True, neden="KAP özel durum açıklaması")
    else:
        res["filter"] = call(config.MODEL_FILTER, FILTER_PROMPT,
                             _user_message(row, universe, config.FILTER_BODY_CHARS, stats), FilterResult,
                             config.FILTER_REASONING_EFFORT, islem="on_eleme")
        if not res["filter"].onemli:
            return res
        article = fetch_article(row["url"]) if row["url"] else ""  # özet yerine tam metin (adres yoksa denenmez)
        if len(article) > len(body):
            res["article"] = article
            body = f"{row['body'] or ''}\n\n[TAM METİN]\n{article}"

    # Önemli konularda (pay alım teklifi, birleşme...) daha uzun metin okunur; diğerleri varsayılan sınırda.
    body_chars = int(config.reading_limits(row["subject"] or "")["body_chars"] * q["body_factor"])
    msg = _user_message(row, universe, body_chars, stats, body)
    a = call(config.MODEL_ANALYSIS, ANALYSIS_PROMPT, msg, FullAnalysis, q["reasoning"], islem="tam_analiz")
    if q["second_opinion"] and _needs_second_opinion(a, q["second_min_impact"]):
        a2 = call(config.MODEL_ANALYSIS, ANALYSIS_PROMPT, msg, FullAnalysis, q["reasoning"], islem="ikinci_gorus")
        a, res["flags"] = _reconcile(a, a2)
    res["analysis"] = a
    return res


def is_ust_siniri(llm, row, universe: Dict[str, str], stats: Optional[Dict[str, dict]], q: dict) -> float:
    """O3: bir haber işinin (_work) TOPLAM muhafazakâr üst sınırı: KAP dışı haberde ön eleme + tam analiz + profil
    ikinci görüş istiyorsa ikinci görüş + desteği bilinmeyen parametreler yüzünden olası ek denemeler. Henüz indirilmemiş
    tam metin, okuma sınırı (karakter) × 4 bayt ile ayrılır (UTF-8'de bir karakter en çok 4 bayt). KAP bildiriminde
    ya da adresi olmayan haberde metin önceden bellidir: mesaj birebir kurulup bayt sayısı kullanılır."""
    from . import harcama
    toplam, enbuyuk = 0.0, {}

    def ekle(model, effort, system, user, schema, ek_bayt=0):
        nonlocal toplam
        u = harcama.cagri_ust_sinir(system, user, schema, ek_bayt)
        toplam += u
        enbuyuk[(model, effort)] = max(enbuyuk.get((model, effort), 0.0), u)
    if row["source"] != "kap":
        ekle(config.MODEL_FILTER, config.FILTER_REASONING_EFFORT, FILTER_PROMPT,
             _user_message(row, universe, config.FILTER_BODY_CHARS, stats), FilterResult)
    body_chars = int(config.reading_limits(row["subject"] or "")["body_chars"] * q["body_factor"])
    url = row["url"] if "url" in row.keys() else None
    if row["source"] == "kap" or not url:          # _work tam metin indirmez: mesaj birebir bu
        msg, ek_bayt = _user_message(row, universe, body_chars, stats, row["body"] or ""), 0
    else:                                          # indirilecek metin bilinmiyor: okuma sınırı × 4 bayt
        msg, ek_bayt = _user_message(row, universe, body_chars, stats, ""), 4 * body_chars
    for _ in range(2 if q["second_opinion"] else 1):
        ekle(config.MODEL_ANALYSIS, q["reasoning"], ANALYSIS_PROMPT, msg, FullAnalysis, ek_bayt)
    ek = getattr(llm, "ek_deneme", None)
    for (model, effort), u in enbuyuk.items():
        toplam += (ek(model, effort) if ek else 0) * u
    return toplam


def _zarfli_work(zarf_id, db_path, llm, row, universe, stats, q):
    """İş parçacığında: çağrılar bu işin zarfından düşer; iş bitince zarfın kullanılmayan kısmı serbest kalır."""
    from . import harcama
    with harcama.zarf_icinde(zarf_id, db_path):
        return _work(llm, row, universe, stats, q)


def _store(conn, row, universe, res, stats) -> None:
    nid = row["id"]
    f, a = res["filter"], res["analysis"]
    stats["input_tokens"] += res["tokens"][0]
    stats["output_tokens"] += res["tokens"][1]
    if res["article"]:
        conn.execute("UPDATE news SET body=? WHERE id=?",
                     (f"{row['body'] or ''}\n\n[TAM METİN]\n{res['article']}", nid))
    if a is None:
        _save(conn, nid, "filter", config.MODEL_FILTER, f, *res["tokens"])
        conn.execute("UPDATE news SET status='filtered_out', note=? WHERE id=?", (f.neden, nid))
        conn.commit()
        stats["filtered_out"] += 1
        return
    _save(conn, nid, "full", config.MODEL_ANALYSIS, a, *res["tokens"])
    conn.execute("DELETE FROM impacts WHERE news_id=?", (nid,))
    written = set()
    for imp in a.etkiler:
        t = imp.hisse.strip().upper().replace(".IS", "")
        if t not in universe:  # uydurma / evren dışı kodları at
            stats["dropped_tickers"] += 1
            continue
        direction = {"pozitif": 1, "negatif": -1, "notr": 0}[imp.yon]
        flag = res["flags"].get(imp.hisse)
        conn.execute(
            "INSERT OR REPLACE INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,"
            "event_type,reason,published_at,effective_date,flag) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (nid, t, direction, max(1, min(5, imp.etki)), max(0.0, min(1.0, a.guven)),
             a.kalicilik, a.olay_tipi, imp.gerekce, row["published_at"], row["effective_date"], flag),
        )
        written.add(t)
        stats["impacts"] += 1
        if flag in ("çelişkili", "etki belirsiz", "tek görüş"):
            stats["flagged"] = stats.get("flagged", 0) + 1
    # Doğrulama: KAP bildiriminde bildirimi yapan şirket mutlaka görünür olsun.
    if row["source"] == "kap":
        for t in (row["candidates"] or "").split(","):
            if t and t in universe and t not in written:
                conn.execute(
                    "INSERT OR REPLACE INTO impacts(news_id,ticker,direction,magnitude,confidence,persistence,"
                    "event_type,reason,published_at,effective_date,flag) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (nid, t, 0, 1, max(0.0, min(1.0, a.guven)), a.kalicilik, a.olay_tipi,
                     "Model bu şirket için yön belirtmedi; bildirimi elle okuyun.",
                     row["published_at"], row["effective_date"], "yorumsuz"))
    conn.execute("UPDATE news SET status='analyzed', note=? WHERE id=?", (a.ozet, nid))
    conn.commit()
    stats["analyzed"] += 1


def status_file():
    return config.DATA / "analiz_durumu.json"


def load_status() -> Dict:
    """Son/çalışan haber analizinin durumu (panel kutusu için; hangi yoldan başlatılırsa başlatılsın)."""
    try:
        return json.loads(status_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_status(st: Dict) -> None:
    if not st.get("_izle"):
        return          # yalnız gerçek kullanım yolları (panel, güncelleme, sabah analizi) yazar; testler yazmaz
    try:
        st["nabiz"] = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        status_file().parent.mkdir(parents=True, exist_ok=True)
        status_file().write_text(json.dumps(st, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass   # durum dosyası yazılamazsa analiz yine sürsün


def _label(row) -> Dict:
    return {"hisse": row["candidates"] or "—", "baslik": (row["title"] or "")[:80],
            "konu": row["subject"] or row["source"]}


def _result_label(conn, row) -> Dict:
    """Biten analizin kısa sonucu: hisse başına yön ve etki (ör. "AKGRT olumlu 4/5")."""
    yon = {1: "olumlu", -1: "olumsuz", 0: "nötr"}
    imps = conn.execute("SELECT ticker, direction, magnitude FROM impacts WHERE news_id=? ORDER BY ticker",
                        (row["id"],)).fetchall()
    st = conn.execute("SELECT status FROM news WHERE id=?", (row["id"],)).fetchone()
    text = ", ".join(f"{i[0]} {yon.get(i[1], '?')} {i[2]}/5" for i in imps) or (
        "önemsiz bulundu" if st and st[0] == "filtered_out" else "hata" if st and st[0] == "error" else "etki yok")
    return dict(_label(row), sonuc=text, saat=datetime.now(config.TR_TZ).strftime("%H:%M:%S"))


DEEP_BODY_FACTOR = 2.0      # derin incelemede okunan metin (normalin 2 katı)
DEEP_COST_FACTOR = 1.6      # maliyet tahmini çarpanı (uzun metin + zorunlu ikinci görüş)


def _impacts_snapshot(conn, news_id: str) -> List[Dict]:
    return [dict(r) for r in conn.execute("SELECT ticker, direction, magnitude, confidence, persistence, event_type, "
                                          "reason, flag FROM impacts WHERE news_id=? ORDER BY ticker", (news_id,))]


def analyzed_rows(conn, news_ids) -> List:
    if not news_ids:
        return []
    q = ",".join("?" * len(news_ids))
    rows = conn.execute(f"SELECT * FROM news WHERE id IN ({q}) AND status='analyzed'", list(news_ids)).fetchall()
    order = {nid: i for i, nid in enumerate(news_ids)}
    return sorted(rows, key=lambda r: order[r["id"]])


def estimate_reanalysis(conn, rows) -> Dict[str, float]:
    est = estimate_cost(conn, rows, "yuksek")
    hi = est["high_usd"] * DEEP_COST_FACTOR
    return {"adet": len(rows), "low_usd": est["high_usd"], "high_usd": hi}


def reanalyze(conn, universe: Dict[str, str], news_ids, llm: Optional[LLM] = None,
              budget_usd: Optional[float] = None, progress: Optional[Callable[[int, int], None]] = None,
              track: bool = False) -> Dict:
    """Analiz edilmiş haberi derin yeniden inceler (kullanıcı isteği 2026-11-09): en yüksek doğruluk profili, ZORUNLU
    ikinci bağımsız görüş, iki kat metin. Önceki sonuç silinmez: reanalysis_log'a (değiştirilemez) yazılır; yeni sonuç
    skor hesabında kullanılır. Habere sonradan gelen fiyat hareketi VERİLMEZ (geriye dönük bilgi karışmasın).
    Bütçe: bu ayın harcaması + her haberin üst tahmini (×DEEP_COST_FACTOR) bütçeyi aşacaksa o haber atlanır."""
    rows = analyzed_rows(conn, news_ids)
    q = quality_profile("yuksek")
    q.update(second_opinion=True, second_min_impact=0, body_factor=q["body_factor"] * DEEP_BODY_FACTOR)
    out = {"istenen": len(news_ids), "incelenen": 0, "hata": 0, "butce_disi": 0, "degisen": 0, "sonuclar": []}
    from . import harcama
    if llm is None:     # O3: üretim yolu her zaman bütçe korumalı (parametre verilmezse Ayarlar'daki bütçe)
        llm = LLM("derin_inceleme", butce=harcama.uretim_butcesi(conn, "haber", budget_usd))
    butce = getattr(llm, "butce", None)
    if budget_usd is not None and butce is None:     # eski tahmin süzgeci (yalnız sahte istemci / test)
        left = budget_usd - month_spend(conn)
        avg, hi_out = _avg_out(conn), _high_out(conn)
        keep = []
        for r in rows:
            hi = row_cost(r, avg, "yuksek", hi_out)[1] * DEEP_COST_FACTOR
            if hi > left:
                break
            keep.append(r)
            left -= hi
        out["butce_disi"] = len(rows) - len(keep)
        rows = keep
    if not rows:
        return out
    spend0 = month_spend(conn)
    st_ = {"_izle": track, "tur": "derin inceleme", "durum": "çalışıyor", "toplam": len(rows), "biten": 0,
           "basladi": datetime.now(config.TR_TZ).isoformat(timespec="seconds")}
    _write_status(st_)
    from .prices import company_stats
    try:
        cstats = company_stats(conn, [c for r in rows for c in (r["candidates"] or "").split(",") if c in universe])
    except Exception:
        cstats = {}
    for i, row in enumerate(rows):
        if budget_usd is not None and butce is None and month_spend(conn) + row_cost(row, _avg_out(conn), "yuksek",
                                                                                     _high_out(conn))[1] \
                * DEEP_COST_FACTOR > budget_usd:     # gerçek harcamayla her haberden önce yeniden kontrol
            out["butce_disi"] += len(rows) - i
            break
        st_["suan"] = [_label(row)]
        _write_status(st_)
        old = _impacts_snapshot(conn, row["id"])
        prev = conn.execute("SELECT input_tokens, output_tokens, created_at FROM analyses WHERE news_id=?",
                            (row["id"],)).fetchone()
        now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
        work_row = {k: row[k] for k in row.keys()}
        if "[TAM METİN]" in (work_row.get("body") or ""):
            work_row["url"] = None          # tam metin zaten eklenmiş: yeniden indirilip iki kez eklenmesin
        zid = None
        try:
            if butce is not None:
                zid = harcama.zarf_ac(butce, is_ust_siniri(llm, work_row, universe, cstats, q), "derin_inceleme",
                                      "is_zarfi", str(row["id"]))
            res = _zarfli_work(zid, butce.db_path if butce else None, llm, work_row, universe, cstats, q)
            if res["analysis"] is None:            # KAP dışı haberde ön eleme "önemsiz" dedi: eski sonuç korunur
                raise RuntimeError("ön eleme bu haberi önemsiz buldu; önceki sonuç korundu")
            stats = {"analyzed": 0, "filtered_out": 0, "errors": 0, "impacts": 0, "dropped_tickers": 0, "flagged": 0,
                     "input_tokens": 0, "output_tokens": 0}
            res["article"] = None if work_row["url"] is None else res["article"]
            _store(conn, work_row, universe, res, stats)
            harcama.kayda_gecti(conn, zarf_id=zid)        # maliyet artık analyses'te: çift sayılmaz
            new = _impacts_snapshot(conn, row["id"])
            conn.execute("INSERT INTO reanalysis_log(news_id, eski_json, yeni_json, input_tokens, output_tokens, durum, "
                         "created_at, eski_input_tokens, eski_output_tokens, eski_ay) VALUES(?,?,?,?,?,'tamam',?,?,?,?)",
                         (row["id"], json.dumps(old, ensure_ascii=False), json.dumps(new, ensure_ascii=False),
                          res["tokens"][0], res["tokens"][1], now, prev["input_tokens"] if prev else 0,
                          prev["output_tokens"] if prev else 0, (prev["created_at"] or "")[:7] if prev else None))
            conn.commit()
            changed = [(o, n) for o in old for n in new if o["ticker"] == n["ticker"] and
                       (o["direction"], o["magnitude"]) != (n["direction"], n["magnitude"])]
            gone = {o["ticker"] for o in old} ^ {n["ticker"] for n in new}
            if changed or gone:
                out["degisen"] += 1
            out["incelenen"] += 1
            out["sonuclar"].append({"news_id": row["id"], "baslik": row["title"], "eski": old, "yeni": new,
                                    "degisti": bool(changed or gone)})
        except ButceYetersiz as e:      # muhafazakâr üst sınır karşılanmadı: iş BAŞLATILMADI, kalanlar da
            conn.rollback()
            out["butce_disi"] += len(rows) - i
            out["butce_durdu"] = str(e)[:200]
            break
        except Exception as e:
            conn.rollback()
            conn.execute("INSERT INTO reanalysis_log(news_id, eski_json, yeni_json, durum, created_at) "
                         "VALUES(?,?,?, 'hata', ?)", (row["id"], json.dumps(old, ensure_ascii=False), str(e)[:300], now))
            conn.commit()
            out["hata"] += 1
            out["sonuclar"].append({"news_id": row["id"], "baslik": row["title"], "hata": str(e)[:200]})
        if progress:
            progress(i + 1, len(rows))
        st_.update(biten=i + 1, harcanan_usd=round(month_spend(conn) - spend0, 4), suan=[],
                   son=([_result_label(conn, row)] + st_.get("son", []))[:8])
        _write_status(st_)
    st_.update(durum="tamamlandı", bitti=datetime.now(config.TR_TZ).isoformat(timespec="seconds"), suan=[],
               sonuc={k: out[k] for k in ("incelenen", "degisen", "hata", "butce_disi")})
    _write_status(st_)
    return out


def test_one(conn, universe: Dict[str, str], llm: Optional[LLM] = None) -> Optional[dict]:
    """Ucuz test analizi: sıradaki en yeni 1 haberi "ekonomik" profille analiz eder, HİÇBİR ŞEY KAYDETMEZ.

    Geliştirici/kullanıcı akışı denemek için kullanır; listeye ve skora karışmaz, haber sırada kalır.
    """
    rows = pending(conn, 1)
    if not rows:
        return None
    row = rows[0]
    from . import harcama
    if llm is None:     # O3: ucuz test de bütçe korumalı; maliyeti başka kayda yazılmaz → defterde sayılmaya devam eder
        llm = LLM("ucuz_test", butce=harcama.uretim_butcesi(conn, "haber"))
    butce, q = getattr(llm, "butce", None), quality_profile(config.TEST_QUALITY)
    zid = harcama.zarf_ac(butce, is_ust_siniri(llm, row, universe, {}, q), "ucuz_test", "is_zarfi",
                          str(row["id"])) if butce is not None else None
    res = _zarfli_work(zid, butce.db_path if butce else None, llm, row, universe, {}, q)
    tin, tout = res["tokens"]
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    return {"row": dict(row), "filter": res["filter"], "analysis": res["analysis"], "input_tokens": tin,
            "output_tokens": tout, "usd": tin * INPUT_USD_PER_TOKEN + tout * OUTPUT_USD_PER_TOKEN}


def analyze(conn, universe: Dict[str, str], limit: Optional[int] = None, llm: Optional[LLM] = None,
            progress: Optional[Callable[[int, int], None]] = None, quality: Optional[str] = None,
            rows=None, budget_usd: Optional[float] = None, max_age_days: Optional[int] = None,
            track: bool = False, modul: str = "haber_analizi", on_eleme: bool = True,
            gunluk_butce_usd: Optional[float] = None, kilit: bool = True,
            butcesiz_izin: bool = False) -> Dict[str, int]:
    """Bekleyen haberleri analiz eder. LLM çağrıları paralel, veritabanı yazımı ana iş parçacığında.

    quality: "yuksek" | "dengeli" | "ekonomik" (panel ayarı). Boşsa yüksek doğruluk.
    rows: kullanıcının seçtiği haberler (verilmezse öncelik sırası). budget_usd: aylık bütçe — bu ayın harcaması +
    her haberin ÜST tahmini bütçeyi aşacaksa o haber ve sonrakiler analiz edilmez (2026-11-09).
    on_eleme (2026-11-14, Aşama 3, kullanıcı onayı): Python ön elemesi rutin haberleri YZ'ye göndermeden 'skipped'
    yapar. Kullanıcının panelde KENDİ seçtiği haberlerde kapalıdır (seçimine saygı).
    O3 (16.11.2026): budget_usd verildiğinde günlük sınır (gunluk_butce_usd; None → Ayarlar, varsayılan 0,50 $) da
    uygulanır, kısıtlayıcı olan geçerli. Aynı anda tek analiz (haber_kapsam.analiz_kilidi): kilit alınamazsa HİÇ çağrı
    yapılmaz. Kapsam (son iki işlem günü) dışındaki haber analiz edilirse etkileri 'sonradan_analiz' işaretlenir.
    Dönüşte tahmini (üst sınır) ve gerçekleşen maliyet ayrı.
    O3 düzeltmesi: aylık bütçe verilmemesi SINIRSIZ demek değildir → Ayarlar'daki üretim bütçesi kullanılır. Tek açık
    istisna butcesiz_izin=True (yalnız testlerdeki sahte istemciler; gerçek istemci rezervasyonsuz hiç çağrı yapmaz).
    Her haber işi başlamadan toplam muhafazakâr üst sınırı (is_ust_siniri) iş zarfı olarak ayrılır; yetmezse iş ve
    sıradakiler başlatılmaz.
    """
    from . import haber_kapsam
    if budget_usd is None and not butcesiz_izin:
        from .pipeline import news_budget
        budget_usd = news_budget()
    if not kilit:
        return _analyze(conn, universe, limit, llm, progress, quality, rows, budget_usd, max_age_days, track, modul,
                        on_eleme, gunluk_butce_usd)
    try:
        with haber_kapsam.analiz_kilidi():
            return _analyze(conn, universe, limit, llm, progress, quality, rows, budget_usd, max_age_days, track, modul,
                            on_eleme, gunluk_butce_usd)
    except haber_kapsam.AnalizSuruyor as e:
        return {"analyzed": 0, "kilitli": str(e)}


def _analyze(conn, universe, limit, llm, progress, quality, rows, budget_usd, max_age_days, track, modul, on_eleme,
             gunluk_butce_usd) -> Dict[str, int]:
    from . import haber_kapsam
    q = quality_profile(quality)
    stats = {"analyzed": 0, "filtered_out": 0, "errors": 0, "impacts": 0, "dropped_tickers": 0,
             "flagged": 0, "input_tokens": 0, "output_tokens": 0}
    from . import prefilter
    if rows is None:
        if on_eleme:
            n = prefilter.apply(conn)["rutin"]        # bütün sıra (ucuz); sınır rutin haberlere harcanmasın
            if n:
                stats["rutin"] = n
        rows = pending(conn, limit, max_age_days=max_age_days)
    else:
        if on_eleme:
            rows, n = prefilter.split(conn, rows)
            if n:
                stats["rutin"] = n
        if limit:
            rows = list(rows)[:limit]
    from .dedupe import filter_duplicates    # 2026-11-14: aynı içerik/başlık bir daha YZ'ye gönderilmez
    rows, dup = filter_duplicates(conn, rows)
    if dup:
        stats["tekrar"] = dup
    rows, over = within_budget(conn, rows, budget_usd, quality, gunluk_butce_usd)
    if over:
        stats["butce_disi"] = over
        bd = haber_kapsam.butce_durumu(conn, budget_usd, gunluk_butce_usd)
        stats["butce_kalan_usd"] = round(bd["kalan"], 4)
        stats["butce_sinirlayan"] = bd["sinirlayan"]
    if not rows:
        return stats
    kapsam_bas = haber_kapsam.kapsam_baslangici()["baslangic_iso"]
    stats["tahmini_ust_usd"] = 0.0
    from . import harcama
    if llm is None:
        llm = LLM(modul, butce=harcama.uretim_butcesi(conn, "haber", budget_usd, gunluk_butce_usd))
    butce = getattr(llm, "butce", None)
    spend0 = month_spend(conn)
    st_ = {"_izle": track, "tur": "haber analizi", "durum": "çalışıyor", "toplam": len(rows), "biten": 0,
           "basladi": datetime.now(config.TR_TZ).isoformat(timespec="seconds")}
    _write_status(st_)
    # Şirket büyüklüğü bağlamı (piyasa değeri, son fiyat) — tutarları ölçeklemek için
    from .prices import company_stats
    try:
        cstats = company_stats(conn, [c for r in rows for c in (r["candidates"] or "").split(",") if c in universe])
    except Exception:
        cstats = {}
    done = 0
    # Bütçe denetimli sıra (2026-11-09): bir haber ancak GERÇEK harcama + çalışan haberlerin üst tahmini + bu haberin
    # üst tahmini bütçeye sığıyorsa başlatılır; her biten haberden sonra gerçek harcama yeniden okunur.
    avg_o, hi_o = _avg_out(conn), _high_out(conn)
    hi_of = {r["id"]: row_cost(r, avg_o, quality, hi_o)[1] for r in rows}
    queue = list(rows)
    # O3 (16.11.2026, testte bulundu): üst tahmin gerçek maliyetin altında kalabilir (uzun çıktı). Bütçeli çalışmada
    # ilk gerçek maliyet görülene kadar TEK iş yürütülür; sonra her haberin tahmini, bu çalışmada gözlenen en yüksek
    # gerçek haber maliyetiyle büyütülür. Kalan aşım riski: ilk haberin tahmin hatası kadar (raporlandı).
    from .pipeline import INPUT_USD_PER_TOKEN as _IN, OUTPUT_USD_PER_TOKEN as _OUT
    gozlenen = [0.0]
    ust = lambda r: max(hi_of[r["id"]], gozlenen[0])
    with ThreadPoolExecutor(max_workers=config.ANALYSIS_WORKERS) as ex:
        futures, zarf_of = {}, {}

        def fill():
            while queue and len(futures) < config.ANALYSIS_WORKERS:
                if butce is not None:     # KESİN koruma: işin toplam üst sınırı atomik ayrılır (süreçler arası)
                    try:
                        zu = is_ust_siniri(llm, queue[0], universe, cstats, q)
                        zid = harcama.zarf_ac(butce, zu, modul, "is_zarfi", str(queue[0]["id"]))
                    except ButceYetersiz as e:
                        stats["butce_disi"] = stats.get("butce_disi", 0) + len(queue)
                        stats["butce_durdu"] = str(e)[:200]
                        queue.clear()
                        return
                    r = queue.pop(0)
                    stats["tahmini_ust_usd"] += zu
                    f = ex.submit(_zarfli_work, zid, butce.db_path, llm, r, universe, cstats, q)
                    futures[f], zarf_of[f] = r, zid
                    continue
                if budget_usd is not None:    # sahte istemci (test): eski tahmin süzgeci
                    if futures and not gozlenen[0]:
                        break                                   # ilk gerçek maliyet bekleniyor
                    running = sum(ust(futures[f]) for f in futures)
                    kalan = haber_kapsam.butce_durumu(conn, budget_usd, gunluk_butce_usd)["kalan"]
                    if running + ust(queue[0]) > kalan:
                        stats["butce_disi"] = stats.get("butce_disi", 0) + len(queue)
                        queue.clear()
                        return
                r = queue.pop(0)
                stats["tahmini_ust_usd"] += ust(r)
                futures[ex.submit(_work, llm, r, universe, cstats, q)] = r
            st_["suan"] = [_label(x) for x in futures.values()]
            _write_status(st_)

        fill()
        while futures:
            fut = next(as_completed(list(futures)))
            row = futures.pop(fut)
            zid = zarf_of.pop(fut, None)
            done += 1
            if progress:
                progress(done, len(rows))
            try:
                _res = fut.result()
                gozlenen[0] = max(gozlenen[0], _res["tokens"][0] * _IN + _res["tokens"][1] * _OUT)
                _store(conn, row, universe, _res, stats)
                harcama.kayda_gecti(conn, zarf_id=zid)        # maliyet artık analyses'te: çift sayılmaz
                if (row["published_at"] or "") < kapsam_bas:      # geçmişe dönük analiz: geçmişte BİLİNMİYORDU
                    conn.execute("UPDATE impacts SET flag=CASE WHEN flag IS NULL OR flag='' THEN 'sonradan_analiz' "
                                 "ELSE flag || ',sonradan_analiz' END WHERE news_id=?", (row["id"],))
                    conn.commit()
                    stats["sonradan_analiz"] = stats.get("sonradan_analiz", 0) + 1
                st_["son"] = ([_result_label(conn, row)] + st_.get("son", []))[:8]
            except ButceYetersiz as e:
                # Çağrı zarfa / bütçeye sığmadı: o çağrı YAPILMADI. Haber hatalı sayılmaz (sırada kalır); yapılmış
                # önceki çağrıların maliyeti defterde sayılmaya devam eder. Sıradakiler başlatılmaz.
                conn.rollback()
                stats["butce_disi"] = stats.get("butce_disi", 0) + 1 + len(queue)
                stats["butce_durdu"] = str(e)[:200]
                queue.clear()
            except (AuthenticationError, PermissionDeniedError, RateLimitError) as e:
                # Hesap/kota sorunu: haberleri hatalı işaretleme, kalanları iptal et.
                conn.rollback()
                print(f"[durdu] OpenAI hesap/kota sorunu: {e}")
                for other in futures:
                    other.cancel()
                queue.clear()
                stats["stopped"] = str(e)[:300]
                break
            except Exception as e:  # tek bir haber tüm akışı durdurmasın
                conn.rollback()
                conn.execute("UPDATE news SET status='error', note=? WHERE id=?", (str(e)[:500], row["id"]))
                conn.commit()
                stats["errors"] += 1
                print(f"[hata] {row['id']}: {e}")
            st_.update(biten=done, harcanan_usd=round(month_spend(conn) - spend0, 4),
                       suan=[_label(x) for x in futures.values()])
            _write_status(st_)
            fill()
    if stats.get("butce_disi"):
        bd = haber_kapsam.butce_durumu(conn, budget_usd, gunluk_butce_usd)
        stats["butce_kalan_usd"] = round(bd["kalan"], 4) if bd["kalan"] is not None else None
        stats["butce_sinirlayan"] = bd["sinirlayan"]
    stats["tahmini_ust_usd"] = round(stats["tahmini_ust_usd"], 4)
    stats["gerceklesen_usd"] = round(month_spend(conn) - spend0, 4)
    st_.update(durum="durdu" if stats.get("stopped") else "tamamlandı", suan=[],
               bitti=datetime.now(config.TR_TZ).isoformat(timespec="seconds"),
               harcanan_usd=round(month_spend(conn) - spend0, 4),
               sonuc={k: stats.get(k, 0) for k in ("analyzed", "filtered_out", "errors", "butce_disi")},
               neden=stats.get("stopped"))
    _write_status(st_)
    return stats
