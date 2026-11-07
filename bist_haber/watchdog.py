"""Akıllı Piyasa Bekçisi (W, 2026-11-07): botun kararlarını kaydeder, denetler, raporlar.

Kullanıcı isteği: sabah (borsa açılmadan) ve akşam (kapanıştan sonra) analizleri — kullanıcı ELLE başlatır; otomatik
emir YOK, ayarları kendiliğinden DEĞİŞTİRMEZ (öneriler kullanıcı onayına sunulur). Rutin kontrollerde yapay zekâ yok.

W1 — sinyal geçmişi: her çalıştırmada evrendeki her hisse için karar izi (önerildi / önerilmedi + neden + modül).
Kayıtlar yalnız eklenir (veritabanı tetikleyicileri değiştirmeyi/silmeyi reddeder): kaçırılan fırsat analizi o gün
botun BİLDİĞİ ile yapılır, geriye dönük bilgi karışmaz.
"""
import json
from collections import Counter
from datetime import date, datetime
from typing import Dict, Optional

from . import config, report, signals


def log_run(conn, universe: Dict[str, str], kind: str, window: int = 7, today: Optional[date] = None,
            ctx: Optional[signals.Context] = None) -> Dict:
    """Bir çalıştırmanın tüm kararlarını tek işlemde kaydeder; özet döndürür."""
    if kind not in ("sabah", "aksam", "guncelleme"):
        raise ValueError("Geçersiz çalıştırma türü")
    ctx = ctx or signals.Context(conn, today)
    rows = report.build(conn, universe, days=window, as_of=ctx.today)
    decisions = signals.decisions_all(conn, universe, rows, window=window, ctx=ctx)
    counts = Counter(d["neden_kodu"] for d in decisions)
    summary = {"hisse": len(decisions), "onerilen": counts.get("ONERILDI", 0), "nedenler": dict(counts),
               "pencere_gun": window}
    now = datetime.now(config.TR_TZ).isoformat(timespec="seconds")
    with conn:  # hepsi ya da hiçbiri
        cur = conn.execute("INSERT INTO watch_runs(kind, day, started_at, summary_json) VALUES(?,?,?,?)",
                           (kind, ctx.today.isoformat(), now, json.dumps(summary, ensure_ascii=False)))
        run_id = cur.lastrowid
        conn.executemany(
            "INSERT INTO signal_log(run_id,ticker,karar,neden_kodu,modul,neden,haber_skoru,haber_sayisi,son_fiyat,"
            "fiyat_gunu,senaryo,giris,sl,tp1,tp2,risk_seviyesi,detay_json) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            [(run_id, d["ticker"], d["karar"], d["neden_kodu"], d.get("modul"), d.get("neden"), d.get("haber_skoru"),
              d.get("haber_sayisi"), d.get("son_fiyat"), d.get("fiyat_gunu"), d.get("senaryo"), d.get("giris"),
              d.get("sl"), d.get("tp1"), d.get("tp2"), d.get("risk_seviyesi"),
              json.dumps(d.get("detay") or {}, ensure_ascii=False)) for d in decisions])
    summary["run_id"] = run_id
    return summary


def decision_on(conn, ticker: str, day: str) -> Optional[Dict]:
    """O GÜN (ya da öncesindeki en son çalıştırmada) bu hisse için verilen karar — kaçırılan fırsat analizi için."""
    r = conn.execute("SELECT s.*, w.kind, w.day, w.started_at FROM signal_log s JOIN watch_runs w ON w.run_id=s.run_id "
                     "WHERE s.ticker=? AND w.day<=? ORDER BY w.day DESC, w.run_id DESC LIMIT 1", (ticker, day)).fetchone()
    return dict(r) if r else None
