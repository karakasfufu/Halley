"""Arayüzün kullandığı tek adımlık güncelleme akışı: topla → analiz et → fiyatları güncelle."""
import os
from typing import Callable, Dict, Optional

from . import analyzer, config, kap, prices, rss, technical
from .universe import Matcher, load_universe, refresh_companies

Progress = Callable[[str, float], None]  # (mesaj, 0..1)


def has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def save_api_key(key: str) -> None:
    """Anahtarı .env dosyasına yazar (kodun içine değil, Dipnot 10)."""
    env = config.ROOT / ".env"
    lines = [l for l in (env.read_text(encoding="utf-8").splitlines() if env.exists() else [])
             if not l.startswith("OPENAI_API_KEY=")]
    lines.insert(0, f"OPENAI_API_KEY={key.strip()}")
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ["OPENAI_API_KEY"] = key.strip()


def universe(conn) -> Dict[str, str]:
    if not conn.execute("SELECT 1 FROM companies LIMIT 1").fetchone():
        refresh_companies(conn)
    return load_universe(conn)


def update_all(conn, days: int = 1, progress: Optional[Progress] = None, analyze: bool = True,
               analysis_limit: int = 10, quality: Optional[str] = None) -> Dict[str, dict]:
    if not isinstance(analysis_limit, int) or not 1 <= analysis_limit <= config.MAX_ANALYSIS_PER_RUN:
        raise ValueError(f"Bir güncellemede en fazla {config.MAX_ANALYSIS_PER_RUN} haber analiz edilebilir.")
    say = progress or (lambda msg, p: None)
    uni = universe(conn)
    out = {}
    say("KAP bildirim listesi alınıyor...", 0.02)
    out["kap"] = kap.collect(conn, uni, days=days, fetch_bodies=False)
    try:  # uygulama birkaç gün açılmadıysa aradaki günleri takvim için doldur (yalnız liste, yapay zekâ yok)
        from . import kap_history
        say("Takvim için eksik günler kontrol ediliyor...", 0.04)
        out["takvim_boslugu"] = kap_history.fill_gaps(conn, uni)
    except Exception as e:  # KAP sınırı vb.: güncelleme yine sürsün
        out["takvim_boslugu"] = {"hata": str(e)[:200]}
    say("Ekonomi haberleri (RSS) alınıyor...", 0.05)
    out["rss"] = rss.collect(conn, Matcher(uni))
    out["kap"].update(kap.fetch_missing_bodies(
        conn, lambda i, n: say(f"KAP bildirim metinleri okunuyor ({i + 1}/{n})...", 0.08 + 0.42 * i / max(n, 1))))
    if out["kap"].get("rate_limited"):
        # Yarım kalan metinleri arka plan okuyucu KAP sınırına göre bekleyerek tamamlar (kullanıcı tekrar basmaz).
        from . import kap_worker
        kap_worker.note_rate_limited()
    from . import prefilter        # 2026-11-14 Aşama 3: rutin haberler sıradan çıkar (YZ'siz, anahtar olmasa da)
    out["rutin"] = prefilter.apply(conn)["rutin"]
    if analyze and has_api_key():
        say("Yapay zekâ haberleri analiz ediyor...", 0.5)
        # O3 (16.11.2026): kapsam son iki BIST işlem günü (takvim günü yerine); günlük + aylık bütçe; tek analiz kilidi
        from . import haber_kapsam
        bas = haber_kapsam.kapsam_baslangici()["baslangic_iso"]
        out["analyze"] = analyzer.analyze(
            conn, uni, limit=analysis_limit, quality=quality, budget_usd=news_budget(), track=True,
            rows=_kapsam_sirasi(conn, analysis_limit, bas),
            progress=lambda i, n: say(f"Yapay zekâ haberleri analiz ediyor ({i}/{n})...", 0.5 + 0.42 * i / max(n, 1)))
        out["analyze"]["waiting"] = len(analyzer.pending(conn, bas_zamani=bas))
        out["analyze"]["eski_bekleyen"] = len(analyzer.pending(conn)) - out["analyze"]["waiting"]
    elif analyze:
        out["analyze"] = {"atlandı": "OpenAI anahtarı yok"}
    say("Fiyatlar güncelleniyor...", 0.94)
    tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM impacts")]
    tickers.append(technical.BENCHMARK)  # endekse göre güç için XU100 (ücretsiz)
    try:
        out["prices"] = {"rows": prices.update(conn, tickers)}
    except Exception as e:  # fiyat servisi çökerse analiz sonuçları yine görünsün
        out["prices"] = {"hata": str(e)}
    say("Tamamlandı.", 1.0)
    return out


# Tahmin için fiyat varsayımı (gpt-5-mini, 2026-11-06): 1M girdi tokenı 0.25 USD, 1M çıktı tokenı 2 USD.
INPUT_USD_PER_TOKEN = 0.25 / 1_000_000
OUTPUT_USD_PER_TOKEN = 2.0 / 1_000_000


def _kapsam_sirasi(conn, limit: int, bas: str):
    """Kapsamdaki (son iki işlem günü) bekleyen haberler, öncelik sırasıyla; rutin ön eleme analyze() içinde."""
    from . import prefilter
    prefilter.apply(conn)
    return analyzer.pending(conn, limit, bas_zamani=bas)


def estimate_next_run(conn, analysis_limit: int = 10, quality: Optional[str] = None) -> Dict[str, float]:
    """Bir sonraki "Haberleri güncelle"nin yaklaşık maliyeti. Yapay zekâ çağrılmaz.

    Girdi tokenı metin uzunluğundan, çıktı tokenı bu bilgisayardaki geçmiş analizlerin ortalamasından
    (yoksa ihtiyatlı 4000) tahmin edilir. Alt sınır ikinci görüşsüz, üst sınır her habere ikinci görüş
    alınmış ve tüm haber siteleri ön elemeyi geçmiş gibi hesaplanır.
    """
    from . import haber_kapsam
    bas = haber_kapsam.kapsam_baslangici()["baslangic_iso"]
    rows = analyzer.pending(conn, analysis_limit, bas_zamani=bas)
    rows, over = analyzer.within_budget(conn, rows, news_budget(), quality)
    est = analyzer.estimate_cost(conn, rows, quality)
    return {"next_count": len(rows), "waiting": len(analyzer.pending(conn, bas_zamani=bas)),
            "low_usd": est["low_usd"], "high_usd": est["high_usd"], "butce_disi": over}


def news_budget() -> float:
    """Haber analizi aylık bütçesi (Ayarlar; varsayılan config.NEWS_BUDGET_USD)."""
    try:
        return max(0.0, float(load_settings().get("haber_butce_usd", config.NEWS_BUDGET_USD)))
    except (TypeError, ValueError):
        return config.NEWS_BUDGET_USD


def free_check(conn, days: int = 1, progress: Optional[Progress] = None, analysis_limit: int = 10,
               quality: Optional[str] = None) -> Dict[str, dict]:
    """Ücretsiz deneme: haberleri ve fiyatları toplar, yapay zekâyı HİÇ çağırmaz.

    Toplama (KAP, haber siteleri) ve fiyat servisi ücretsizdir; OpenAI kredisi harcanmaz. Sonunda
    bir sonraki gerçek güncellemede kaç haberin analiz edileceği ve yaklaşık maliyeti gösterilir.
    """
    out = update_all(conn, days=days, progress=progress, analyze=False, analysis_limit=analysis_limit)
    out["estimate"] = estimate_next_run(conn, analysis_limit, quality)
    out["free"] = True
    return out


SETTINGS_FILE = config.DATA / "ayarlar.json"  # panel ayarları; git'e eklenmez


def load_settings() -> dict:
    """Paneldeki seçimler (ör. analiz kalitesi). Dosya yoksa/bozuksa varsayılanlar."""
    import json
    try:
        data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8-sig"))   # Not Defteri BOM eklese de okunur
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_settings(**values) -> None:
    import json
    data = load_settings()
    data.update(values)
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
