"""Yapay zekâ yorumu (W6, 2026-11-07) — kullanıcı onayıyla; aylık bütçe 5–10 $ kabul edildi.

Üç kullanım (her biri panelde ayrı kutu, varsayılan KAPALI):
1. Akşam raporu yorumu   2. Sabah raporu yorumu   3. Kaçırılan fırsat açıklaması (akşam, en fazla 5 hisse)

Kurallar:
- Model gpt-5-mini (config.MODEL_ANALYSIS); mevcut analyzer.LLM istemcisi kullanılır.
- Girdi YALNIZ kodun hesapladığı rapor / o an bilinen haberler. Yapay zekâ yeni sayı üretmemeli: yorumdaki her sayı
  girdide aranır, bulunamayanlar "doğrulanamadı" diye gösterilir. Kodla hesaplanan bölümler değişmez.
- Aylık bütçe (Ayarlar, varsayılan 10 $): çağrının EN KÖTÜ durum maliyeti bütçeyi aşacaksa çağrı yapılmaz.
  Bütçe yalnız bu yorumlara uygulanır (haber analizi maliyeti ayrı).
- Her çağrı (token, $) değiştirilemez `ai_comments` tablosuna yazılır. Aynı kaçırılan fırsat ikinci kez açıklanmaz.

Maliyet tahmini (2026-11-07 ölçümü, bu bilgisayardaki gerçek gpt-5-mini çağrıları): Türkçe ~1,7 karakter/token;
tam haber analizinde çıktı medyanı 4.815, en fazla 12.961 token (düşünme tokenları dahil). Yorumlarda düşünme
seviyesi "low"; tahmin yine de temkinli olarak 2.000–13.000 çıktı tokenı aralığıyla yapılır.
"""
import json
import re
from datetime import datetime, timedelta
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from . import config

REASONING = "low"
CHARS_PER_TOKEN = 1.7
OUT_TOKENS = (2000, 13000)
MAX_INPUT_CHARS = 24000
MAX_MISSED = 5
DEFAULT_BUDGET_USD = 10.0
NEWS_BODY_CHARS = 1500
EXPLAIN_SKIP = {"HABER_YOK", "TEKNIK_VERI_YOK", "VERI_KRITIK", "LIKIDITE"}   # kodun açıklaması yeterli / metin yok


class ReportComment(BaseModel):
    ozet: str = Field(description="3-5 cümlelik sade Türkçe genel değerlendirme")
    dikkat: List[str] = Field(description="Kullanıcının dikkat etmesi gereken en fazla 5 madde")
    riskler: List[str] = Field(description="Rapordaki risk ve belirsizliklerden en fazla 4 madde")


class MissedExplain(BaseModel):
    aciklama: str = Field(description="Botun bu hisseyi neden kaçırdığının 2-4 cümlelik açıklaması")
    o_an_bilinebilir_miydi: Literal["evet", "hayir", "kismen"]
    sorumlu_modul: str = Field(description="haber eşleştirme / ön eleme / haber yorumu / puan eşiği / teknik filtre / "
                                           "giriş seviyesi / botun kapsamı dışında")
    oneri: str = Field(description="Tek cümlelik ihtiyatlı iyileştirme önerisi")


COMMON = ("Kullanıcı Python bilmiyor; sade Türkçe yaz. Yatırım tavsiyesi verme, 'al'/'sat' deme; emirleri kullanıcı "
          "kendisi verir. YENİ SAYI UYDURMA: yalnız sana verilen metindeki sayıları aynen kullan; hesap yapma, hedef "
          "fiyat ya da olasılık uydurma. Bilgi yoksa 'bilinmiyor' de.")

REPORT_PROMPT = ("Sen Halley adlı BIST haber botunun rapor yorumcususun. Sana kodla hesaplanmış günlük bir rapor "
                 "verilecek. Raporu özetle, kullanıcının dikkat etmesi gerekenleri ve riskleri sırala. Az örnek / "
                 "güvenilir değil uyarılarını mutlaka vurgula. Kaçırılan fırsatlar varsa en önemlilerini ve "
                 "nedenlerini kısaca an. " + COMMON)

MISSED_PROMPT = ("Sen Halley adlı BIST haber botunun denetçisisin. Bot bir hisseyi önermedi (ya da önerdi ama giriş "
                 "oluşmadı) ve hisse sonraki günlerde ciddi yükseldi. Sana karar anında bilinen haberler, botun karar "
                 "gerekçesi ve sonraki fiyat hareketi verilecek. 'KARAR ANINDAN SONRA' işaretli bilgileri botun hatası "
                 "sayma; o an bilinemezdi. Görev: neden kaçtığını açıkla, o an bilinebilir miydi söyle, sorumlu modülü "
                 "seç ve ihtiyatlı bir iyileştirme önerisi yaz (tek örnekle eşik değiştirmeyi önerme). " + COMMON)


# ---------------------------------------------------------------- maliyet ve bütçe
def _usd(tin: float, tout: float) -> float:
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    return tin * INPUT_USD_PER_TOKEN + tout * OUTPUT_USD_PER_TOKEN


def estimate(input_chars: int, system_chars: int = len(REPORT_PROMPT)) -> Dict[str, float]:
    tin = (min(input_chars, MAX_INPUT_CHARS) + system_chars) / CHARS_PER_TOKEN
    return {"low": _usd(tin, OUT_TOKENS[0]), "high": _usd(tin, OUT_TOKENS[1]), "input_tokens": round(tin)}


def month_spend(conn, now: Optional[datetime] = None) -> float:
    now = now or datetime.now(config.TR_TZ)
    r = conn.execute("SELECT COALESCE(SUM(usd),0) FROM ai_comments WHERE substr(created_at,1,7)=?",
                     (now.strftime("%Y-%m"),)).fetchone()
    return float(r[0] or 0)


def budget(settings: Dict) -> float:
    try:
        b = float(settings.get("yz_butce_usd", DEFAULT_BUDGET_USD))
    except (TypeError, ValueError):
        b = DEFAULT_BUDGET_USD
    return max(0.0, b)


def _record(conn, kind, ref, tin, tout, result, unverified):
    usd = _usd(tin, tout)
    with conn:
        conn.execute("INSERT INTO ai_comments(kind, ref, model, input_tokens, output_tokens, usd, result_json, "
                     "dogrulanamayan_json, created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (kind, ref, config.MODEL_ANALYSIS, tin, tout, usd, json.dumps(result, ensure_ascii=False),
                      json.dumps(unverified, ensure_ascii=False),
                      datetime.now(config.TR_TZ).isoformat(timespec="seconds")))
    return usd


# ---------------------------------------------------------------- sayı denetimi
_NUM = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*")


def _candidates(tok: str) -> List[float]:
    t = tok.lstrip("+-")
    out = []
    for s in (t.replace(",", "."), t.replace(".", "").replace(",", "."), t.replace(",", "")):
        try:
            out.append(float(s))
        except ValueError:
            pass
    return out


def unverified_numbers(text: str, source: str) -> List[str]:
    """Yorumda geçip kaynakta bulunamayan sayılar (0–10 arası tam sayılar hariç).
    2026-11-09: birim dönüşümü tanınır (kaynakta "1.324.948.123 TL" → yorumda "1.324,9 mn TL" ya da "1,3 mlr TL"; bin /
    milyon / milyar ölçekleri) ve yıl kısaltması ("3Ç'26") sayı sayılmaz. Bunlar önceden yanlışlıkla
    "bulunamadı" çıkıyordu (142 haberlik denetimde 26 sayının çoğu)."""
    src = set()
    for tok in _NUM.findall(source):
        for v in _candidates(tok):
            for scale in (1, 1e3, 1e6, 1e9):
                w = v / scale
                src.update({round(w, 2), round(w, 1), round(w)})
    bad = []
    for m in _NUM.finditer(text):
        tok = m.group(0)
        if len(tok) == 2 and tok.isdigit() and m.start() > 0 and text[m.start() - 1] in "'’":
            continue                                                     # yıl kısaltması: 3Ç'26
        cands = _candidates(tok)
        if not cands:
            continue
        if all(float(v).is_integer() and 0 <= v <= 10 for v in cands):
            continue
        if not any(round(v, 2) in src or round(v, 1) in src for v in cands):
            if tok not in bad:
                bad.append(tok)
    return bad


# ---------------------------------------------------------------- 1–2: rapor yorumu
def comment_report(conn, kind: str, ref: str, report_md: str, settings: Dict, llm=None) -> Dict:
    if kind not in ("sabah", "aksam"):
        raise ValueError("Geçersiz rapor türü")
    est = estimate(len(report_md))
    spent, cap = month_spend(conn), budget(settings)
    if spent + est["high"] > cap:
        return {"ok": False, "hata": f"Aylık yapay zekâ bütçesi yetmiyor (bu ay {spent:.2f} $ harcandı, bütçe {cap:.2f} $, "
                                     f"bu çağrı en fazla {est['high']:.3f} $). Bütçe Ayarlar'dan değiştirilebilir."}
    try:
        from .analyzer import LLM
        llm = llm or LLM("rapor_yorumu")
        out, tin, tout = llm.parse(config.MODEL_ANALYSIS, REPORT_PROMPT, report_md[:MAX_INPUT_CHARS], ReportComment,
                                   reasoning_effort=REASONING)
    except Exception as e:  # rapor yine de arşivlenir
        return {"ok": False, "hata": f"Yapay zekâ yorumu alınamadı: {e}"}
    res = out.model_dump() if hasattr(out, "model_dump") else dict(out)
    text = " ".join([res["ozet"], *res["dikkat"], *res["riskler"]])
    bad = unverified_numbers(text, report_md)
    usd = _record(conn, kind, ref, tin, tout, res, bad)
    return {"ok": True, "yorum": res, "dogrulanamayan": bad, "usd": usd, "input_tokens": tin, "output_tokens": tout}


def report_md(r: Dict) -> str:
    s = "\n## 🤖 Yapay zekâ yorumu\n"
    if not r.get("ok"):
        return s + f"_{r.get('hata', 'Yapılamadı.')}_\n"
    y = r["yorum"]
    s += y["ozet"].strip() + "\n\n"
    if y["dikkat"]:
        s += "**Dikkat edilecekler**\n" + "".join(f"- {x}\n" for x in y["dikkat"][:5]) + "\n"
    if y["riskler"]:
        s += "**Riskler ve belirsizlikler**\n" + "".join(f"- {x}\n" for x in y["riskler"][:4]) + "\n"
    if r["dogrulanamayan"]:
        s += (f"> ⚠️ Yorumdaki şu sayılar raporda bulunamadı, güvenmeyin: {', '.join(r['dogrulanamayan'])}\n\n")
    s += (f"_Yorum {config.MODEL_ANALYSIS} ile üretildi ({r['input_tokens']} + {r['output_tokens']} token ≈ "
          f"{r['usd']:.4f} $). Yalnız yukarıdaki kodla hesaplanmış raporu okur; rapordaki bölümler değiştirilmedi. "
          "Yatırım tavsiyesi değildir._\n")
    return s


# ---------------------------------------------------------------- 3: kaçırılan fırsat açıklaması
def _missed_input(conn, item: Dict, run) -> str:
    t, at = item["hisse"], run["started_at"]
    since = (datetime.fromisoformat(at) - timedelta(days=7)).isoformat()
    like = f"%,{t},%"
    lines = [f"Hisse: {t}", f"Karar anı: {at} (baz gün {item['baz_gun']}, kapanış {item['baz_kapanis']})",
             f"Botun kararı: {item['neden_kodu']} — {item['aciklama']}",
             f"Haber skoru: {item.get('haber_skoru')}"]
    if item.get("neden_yok"):
        lines.append(f"Senaryo üretilmeme nedeni: {item['neden_yok']}")
    if item.get("senaryolar"):
        lines.append("Senaryolar: " + "; ".join(f"{s['tur']}: {s['durum']}" for s in item["senaryolar"]))
    if item.get("etiketler"):
        lines.append("Etiketler: " + ", ".join(item["etiketler"]))
    lines.append(f"Sonraki hareket: {item['zirve_gunu']} kapanışı {item['zirve_kapanis']} "
                 f"(%{item['kazanc_%']:.1f}; endeks %{item['endeks_%']:.1f}; endekse göre {item['endekse_gore_atr']:.1f} ATR)")
    rows = conn.execute("SELECT id, source, published_at, title, body, note, status FROM news WHERE status!='context' AND "
                        "published_at<=? AND published_at>=? AND ((','||COALESCE(candidates,'')||',') LIKE ? OR "
                        "(' '||UPPER(title)||' ') LIKE ?) ORDER BY published_at DESC LIMIT 3",
                        (at, since, like, f"% {t} %")).fetchall()
    lines.append("\nKARAR ANINDA BİLİNEN HABERLER:" if rows else "\nKarar anında bu hisseyle ilgili kayıtlı haber yok.")
    for r in rows:
        imp = conn.execute("SELECT direction, magnitude, confidence, reason FROM impacts WHERE news_id=? AND ticker=?",
                           (r["id"], t)).fetchone()
        lines.append(f"- [{r['published_at'][:16]}] ({r['source']}, durum: {r['status']}) {r['title']}")
        if r["body"]:
            lines.append("  Metin: " + " ".join(r["body"].split())[:NEWS_BODY_CHARS])
        if imp:
            lines.append(f"  Botun yorumu: yön {imp['direction']}, etki {imp['magnitude']}, güven {imp['confidence']}, "
                         f"gerekçe: {imp['reason']}")
    later = conn.execute("SELECT published_at, title FROM news WHERE status!='context' AND (','||candidates||',') LIKE ? "
                         "AND published_at>? AND substr(published_at,1,10)<=? ORDER BY published_at LIMIT 3",
                         (like, at, item["zirve_gunu"])).fetchall()
    if later:
        lines.append("\nKARAR ANINDAN SONRA gelen haber başlıkları (o an bilinemezdi):")
        lines += [f"- [{r['published_at'][:16]}] {r['title']}" for r in later]
    return "\n".join(lines)


def eligible(items: List[Dict]) -> List[Dict]:
    """Yapay zekânın okuyacağı bir haber metni olan kaçırılanlar (haber yok / veri / likidite kodla açık)."""
    return [x for x in items if x["neden_kodu"] not in EXPLAIN_SKIP or "ESLESME" in x.get("etiketler", [])]


def explain_missed(conn, items: List[Dict], settings: Dict, llm=None, limit: int = MAX_MISSED) -> List[Dict]:
    out, paid = [], 0                 # sınır yalnız yeni (ücretli) çağrılara uygulanır; önbellek ücretsiz
    for item in eligible(items):
        ref = f"{item['hisse']}:{item['baz_gun']}"
        old = conn.execute("SELECT result_json, dogrulanamayan_json, usd FROM ai_comments WHERE kind='kacirilan' AND ref=?",
                           (ref,)).fetchone()
        if old:     # daha önce açıklandı: yeniden ücret ödenmez
            out.append({"ok": True, "hisse": item["hisse"], "ref": ref, "yorum": json.loads(old["result_json"]),
                        "dogrulanamayan": json.loads(old["dogrulanamayan_json"]), "usd": 0.0, "onceden": True})
            continue
        if paid >= limit:
            continue
        run = conn.execute("SELECT w.* FROM missed_log m JOIN watch_runs w ON w.run_id=m.run_id WHERE m.baz_gun=? AND "
                           "m.ticker=?", (item["baz_gun"], item["hisse"])).fetchone() or \
            conn.execute("SELECT * FROM watch_runs WHERE run_id=?", (item.get("run_id"),)).fetchone()
        if run is None:
            continue
        msg = _missed_input(conn, item, run)
        est = estimate(len(msg), len(MISSED_PROMPT))
        spent, cap = month_spend(conn), budget(settings)
        if spent + est["high"] > cap:
            out.append({"ok": False, "hisse": item["hisse"], "ref": ref,
                        "hata": f"Aylık bütçe yetmiyor (bu ay {spent:.2f} $ / {cap:.2f} $)."})
            break
        try:
            from .analyzer import LLM
            llm = llm or LLM("kacirilan_aciklama")
            res_, tin, tout = llm.parse(config.MODEL_ANALYSIS, MISSED_PROMPT, msg, MissedExplain,
                                        reasoning_effort=REASONING)
        except Exception as e:
            out.append({"ok": False, "hisse": item["hisse"], "ref": ref, "hata": f"Açıklama alınamadı: {e}"})
            paid += 1
            continue
        res = res_.model_dump() if hasattr(res_, "model_dump") else dict(res_)
        bad = unverified_numbers(" ".join([res["aciklama"], res["oneri"]]), msg)
        usd = _record(conn, "kacirilan", ref, tin, tout, res, bad)
        paid += 1
        out.append({"ok": True, "hisse": item["hisse"], "ref": ref, "yorum": res, "dogrulanamayan": bad, "usd": usd,
                    "input_tokens": tin, "output_tokens": tout})
    return out


def missed_md(results: List[Dict], eligible_total: int) -> str:
    s = "\n## 🤖 Kaçırılan fırsat açıklamaları (yapay zekâ)\n"
    if not results:
        return s + ("_Açıklanacak hisse yok: kaçırılanların nedeni kodla yeterince açık (haber yok / veri / likidite)._\n"
                    if not eligible_total else "_Açıklama yapılamadı._\n")
    label = {"evet": "evet", "hayir": "hayır", "kismen": "kısmen"}
    for r in results:
        if not r.get("ok"):
            s += f"- **{r['hisse']}**: _{r['hata']}_\n"
            continue
        y = r["yorum"]
        s += (f"- **{r['hisse']}** ({r['ref'].split(':')[1]} kararı) — o an bilinebilir miydi: "
              f"**{label.get(y['o_an_bilinebilir_miydi'], y['o_an_bilinebilir_miydi'])}** · modül: {y['sorumlu_modul']}\n"
              f"  {y['aciklama'].strip()}\n  _Öneri:_ {y['oneri'].strip()}\n")
        if r["dogrulanamayan"]:
            s += f"  > ⚠️ Girdide bulunamayan sayılar: {', '.join(r['dogrulanamayan'])}\n"
    total = sum(r.get("usd") or 0 for r in results)
    s += (f"\n_Açıklamalar {config.MODEL_ANALYSIS} ile (bu akşam ≈ {total:.4f} $; daha önce açıklananlar yeniden "
          f"ücretlendirilmez; en fazla {MAX_MISSED} hisse). Öneriler bilgi amaçlıdır; hiçbir ayar değişmez._\n")
    if eligible_total > len(results):
        s += f"_{eligible_total - len(results)} hisse sınır nedeniyle açıklanmadı (sonraki akşam sırası gelir)._\n"
    return s
