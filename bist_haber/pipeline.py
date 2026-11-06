"""Arayüzün kullandığı tek adımlık güncelleme akışı: topla → analiz et → fiyatları güncelle."""
import os
from typing import Callable, Dict, Optional

from . import analyzer, config, kap, prices, rss
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


def update_all(conn, days: int = 1, progress: Optional[Progress] = None, analyze: bool = True) -> Dict[str, dict]:
    say = progress or (lambda msg, p: None)
    uni = universe(conn)
    out = {}
    say("KAP bildirim listesi alınıyor...", 0.02)
    out["kap"] = kap.collect(conn, uni, days=days, fetch_bodies=False)
    say("Ekonomi haberleri (RSS) alınıyor...", 0.05)
    out["rss"] = rss.collect(conn, Matcher(uni))
    out["kap"].update(kap.fetch_missing_bodies(
        conn, lambda i, n: say(f"KAP bildirim metinleri okunuyor ({i + 1}/{n})...", 0.08 + 0.42 * i / max(n, 1))))
    if analyze and has_api_key():
        say("Yapay zekâ haberleri analiz ediyor...", 0.5)
        out["analyze"] = analyzer.analyze(
            conn, uni, progress=lambda i, n: say(f"Yapay zekâ haberleri analiz ediyor ({i}/{n})...",
                                                 0.5 + 0.42 * i / max(n, 1)))
    elif analyze:
        out["analyze"] = {"atlandı": "OpenAI anahtarı yok"}
    say("Fiyatlar güncelleniyor...", 0.94)
    tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM impacts")]
    try:
        out["prices"] = {"rows": prices.update(conn, tickers)}
    except Exception as e:  # fiyat servisi çökerse analiz sonuçları yine görünsün
        out["prices"] = {"hata": str(e)}
    say("Tamamlandı.", 1.0)
    return out
