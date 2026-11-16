"""Komut satırı: python -m bist_haber <komut>

  init      Veritabanını kur, KAP şirket listesini indir
  collect   KAP bildirimleri + RSS haberlerini topla
  analyze   Yeni haberleri OpenAI ile analiz et (--dry-run: maliyet tahmini)
  prices    Etkisi olan hisselerin fiyatlarını güncelle
  report    Günlük sinyal tablosu (+ CSV)
  run       collect → analyze → prices → report
  status    Veritabanı özeti
"""
import argparse
import sys
from datetime import datetime

from . import analyzer, config, db, kap, prices, report, rss
from .universe import Matcher, load_universe, refresh_companies


def _universe(conn):
    if not conn.execute("SELECT 1 FROM companies LIMIT 1").fetchone():
        print("Şirket listesi boş, KAP'tan indiriliyor...")
        refresh_companies(conn)
    return load_universe(conn)


def cmd_init(conn, args):
    n = refresh_companies(conn)
    print(f"Veritabanı: {config.DB_PATH}\nKAP şirket listesi: {n} kod. Takip edilen evren: {len(load_universe(conn))} hisse.")


def cmd_collect(conn, args):
    uni = _universe(conn)
    print("KAP:", kap.collect(conn, uni, days=args.days))
    if not args.no_rss:
        print("RSS:", rss.collect(conn, Matcher(uni)))


def cmd_analyze(conn, args):
    uni = _universe(conn)
    if args.retry_errors:
        conn.execute("UPDATE news SET status='new' WHERE status='error'")
        conn.commit()
    rows = analyzer.pending(conn, args.limit)
    f_tok, a_tok = analyzer.estimate(rows)
    print(f"Analiz bekleyen haber: {len(rows)}  |  tahmini girdi token: ön eleme ~{f_tok:,}, "
          f"derin analiz en fazla ~{a_tok:,} (modeller: {config.MODEL_FILTER} / {config.MODEL_ANALYSIS})")
    if args.dry_run or not rows:
        return
    try:
        from bist_haber import harcama
        llm = analyzer.LLM("komut_satiri", butce=harcama.uretim_butcesi(conn, "haber"))
    except Exception as e:
        sys.exit(f"OpenAI istemcisi kurulamadı: {e}\n.env dosyasına OPENAI_API_KEY ekleyin (bkz. .env.example).")
    print(analyzer.analyze(conn, uni, args.limit, llm))


def cmd_prices(conn, args):
    tickers = [r["ticker"] for r in conn.execute("SELECT DISTINCT ticker FROM impacts")]
    print(f"Fiyat satırı: {prices.update(conn, tickers)} ({len(tickers)} hisse)")


def cmd_report(conn, args):
    uni = _universe(conn)
    as_of = datetime.now(config.TR_TZ).date()
    rows = report.build(conn, uni, days=getattr(args, "report_days", args.days), as_of=as_of)
    report.print_table(rows, args.top)
    if rows:
        print("CSV:", report.save_csv(rows, as_of))


def cmd_status(conn, args):
    for r in conn.execute("SELECT source LIKE 'rss:%' AS is_rss, status, COUNT(*) c FROM news GROUP BY 1,2 ORDER BY 1,2"):
        print(f"{'RSS' if r['is_rss'] else 'KAP'} {r['status']:<13} {r['c']}")
    t = conn.execute("SELECT COALESCE(SUM(input_tokens),0) i, COALESCE(SUM(output_tokens),0) o FROM analyses").fetchone()
    print(f"Toplam OpenAI token: girdi {t['i']:,} / çıktı {t['o']:,}")


def cmd_run(conn, args):
    cmd_collect(conn, args)
    cmd_analyze(conn, args)
    if not args.dry_run:
        cmd_prices(conn, args)
    cmd_report(conn, args)


def main(argv=None):
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(prog="bist_haber", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    sub.add_parser("status")
    sub.add_parser("prices")
    sub.add_parser("okuyucu", help="Eksik KAP sayfalarını arka planda tamamlayan bekçi (baslat.bat başlatır)")
    for name in ("collect", "analyze", "report", "run"):
        sp = sub.add_parser(name)
        if name in ("collect", "run"):
            sp.add_argument("--days", type=int, default=1, help="KAP için kaç günlük bildirim (varsayılan 1)")
            sp.add_argument("--no-rss", action="store_true", help="RSS haberlerini atla")
        if name in ("analyze", "run"):
            sp.add_argument("--limit", type=int, help="En fazla kaç haber analiz edilsin")
            sp.add_argument("--dry-run", action="store_true", help="API çağırmadan sadece tahmin göster")
            sp.add_argument("--retry-errors", action="store_true", help="Hatalı haberleri tekrar dene")
        if name in ("report", "run"):
            sp.add_argument("--top", type=int, default=30)
        if name == "report":
            sp.add_argument("--days", type=int, default=7, help="Kaç günlük etki toplansın")
    args = p.parse_args(argv)
    if args.cmd == "okuyucu":
        from . import kap_worker
        kap_worker.serve()
        return
    if args.cmd == "run":
        args.report_days = 7
    conn = db.connect()
    {"init": cmd_init, "collect": cmd_collect, "analyze": cmd_analyze, "prices": cmd_prices,
     "report": cmd_report, "run": cmd_run, "status": cmd_status}[args.cmd](conn, args)


if __name__ == "__main__":
    main()
