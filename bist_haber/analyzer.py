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


class LLM:
    def __init__(self):
        self.client = OpenAI()  # OPENAI_API_KEY ortam değişkeninden okunur
        self._unsupported = set()  # (model, parametre) çiftleri

    def parse(self, model: str, system: str, user: str, schema, reasoning_effort: Optional[str] = None):
        kwargs = dict(model=model, response_format=schema,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        # İsteğe bağlı parametreler; model desteklemiyorsa çıkarılıp tekrar denenir.
        # temperature=0: tutarlılık (Dipnot 4). reasoning_effort: düşünme miktarı (token/maliyet).
        optional = {"temperature": 0}
        if reasoning_effort:
            optional["reasoning_effort"] = reasoning_effort
        for k, v in optional.items():
            if (model, k) not in self._unsupported:
                kwargs[k] = v
        while True:
            try:
                resp = self.client.chat.completions.parse(**kwargs)
                break
            except BadRequestError as e:
                bad = [k for k in optional if k in kwargs and k in str(e)]
                if not bad:
                    raise
                for k in bad:
                    self._unsupported.add((model, k))
                    kwargs.pop(k)
        msg = resp.choices[0].message
        if msg.refusal:
            raise RuntimeError(f"model reddetti: {msg.refusal}")
        u = resp.usage
        return msg.parsed, (u.prompt_tokens if u else 0), (u.completion_tokens if u else 0)


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


def pending(conn, limit: Optional[int] = None) -> List:
    # body NULL: KAP metni henüz alınamadı → metin gelene kadar bekle.
    # En yeni haber önce (2026-11-06, kullanıcı isteği): swing için taze haber daha değerli; güncelleme başına
    # adet sınırı olduğundan eski haberler sırada bekleyebilir (çok eskiler zaten RSS_MAX_AGE_DAYS ile atlanır).
    sql = ("SELECT * FROM news WHERE status='new' AND body IS NOT NULL "
           "AND LENGTH(TRIM(body, char(9)||char(10)||char(13)||' '))>0 ORDER BY published_at DESC, id")
    return conn.execute(sql + (f" LIMIT {int(limit)}" if limit else "")).fetchall()


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

    def call(model, prompt, msg, schema, effort=None):
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
                             config.FILTER_REASONING_EFFORT)
        if not res["filter"].onemli:
            return res
        article = fetch_article(row["url"])  # özet yerine tam metin
        if len(article) > len(body):
            res["article"] = article
            body = f"{row['body'] or ''}\n\n[TAM METİN]\n{article}"

    # Önemli konularda (pay alım teklifi, birleşme...) daha uzun metin okunur; diğerleri varsayılan sınırda.
    body_chars = int(config.reading_limits(row["subject"] or "")["body_chars"] * q["body_factor"])
    msg = _user_message(row, universe, body_chars, stats, body)
    a = call(config.MODEL_ANALYSIS, ANALYSIS_PROMPT, msg, FullAnalysis, q["reasoning"])
    if q["second_opinion"] and _needs_second_opinion(a, q["second_min_impact"]):
        a2 = call(config.MODEL_ANALYSIS, ANALYSIS_PROMPT, msg, FullAnalysis, q["reasoning"])
        a, res["flags"] = _reconcile(a, a2)
    res["analysis"] = a
    return res


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


def test_one(conn, universe: Dict[str, str], llm: Optional[LLM] = None) -> Optional[dict]:
    """Ucuz test analizi: sıradaki en yeni 1 haberi "ekonomik" profille analiz eder, HİÇBİR ŞEY KAYDETMEZ.

    Geliştirici/kullanıcı akışı denemek için kullanır; listeye ve skora karışmaz, haber sırada kalır.
    """
    rows = pending(conn, 1)
    if not rows:
        return None
    row = rows[0]
    llm = llm or LLM()
    res = _work(llm, row, universe, {}, quality_profile(config.TEST_QUALITY))
    tin, tout = res["tokens"]
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    return {"row": dict(row), "filter": res["filter"], "analysis": res["analysis"], "input_tokens": tin,
            "output_tokens": tout, "usd": tin * INPUT_USD_PER_TOKEN + tout * OUTPUT_USD_PER_TOKEN}


def analyze(conn, universe: Dict[str, str], limit: Optional[int] = None, llm: Optional[LLM] = None,
            progress: Optional[Callable[[int, int], None]] = None, quality: Optional[str] = None) -> Dict[str, int]:
    """Bekleyen haberleri analiz eder. LLM çağrıları paralel, veritabanı yazımı ana iş parçacığında.

    quality: "yuksek" | "dengeli" | "ekonomik" (panel ayarı). Boşsa yüksek doğruluk.
    """
    q = quality_profile(quality)
    llm = llm or LLM()
    stats = {"analyzed": 0, "filtered_out": 0, "errors": 0, "impacts": 0, "dropped_tickers": 0,
             "flagged": 0, "input_tokens": 0, "output_tokens": 0}
    rows = pending(conn, limit)
    if not rows:
        return stats
    # Şirket büyüklüğü bağlamı (piyasa değeri, son fiyat) — tutarları ölçeklemek için
    from .prices import company_stats
    try:
        cstats = company_stats(conn, [c for r in rows for c in (r["candidates"] or "").split(",") if c in universe])
    except Exception:
        cstats = {}
    done = 0
    with ThreadPoolExecutor(max_workers=config.ANALYSIS_WORKERS) as ex:
        futures = {ex.submit(_work, llm, row, universe, cstats, q): row for row in rows}
        for fut in as_completed(futures):
            row = futures[fut]
            done += 1
            if progress:
                progress(done, len(rows))
            try:
                _store(conn, row, universe, fut.result(), stats)
            except (AuthenticationError, PermissionDeniedError, RateLimitError) as e:
                # Hesap/kota sorunu: haberleri hatalı işaretleme, kalanları iptal et.
                conn.rollback()
                print(f"[durdu] OpenAI hesap/kota sorunu: {e}")
                for other in futures:
                    other.cancel()
                stats["stopped"] = str(e)[:300]
                break
            except Exception as e:  # tek bir haber tüm akışı durdurmasın
                conn.rollback()
                conn.execute("UPDATE news SET status='error', note=? WHERE id=?", (str(e)[:500], row["id"]))
                conn.commit()
                stats["errors"] += 1
                print(f"[hata] {row['id']}: {e}")
    return stats
