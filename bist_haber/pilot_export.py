"""Pilotun ekrandaki tablolarını API çağrısı yapmadan birlikte dışa aktarır."""
import io
import json
import zipfile

import pandas as pd

from . import backtest

RESULT_COLUMNS = ["bildirim", "hisse", "yön", "vade", "giriş", "çıkış", "getiri_%",
                  "net_getiri_%", "endekse_göre_%", "en_düşük_%", "eksik", "uygulanabilirlik"]
SUMMARY_COLUMNS = ["vade", "olay_sayısı", "farklı_hisse", "net_yükseliş_oranı",
                   "ortalama_net_getiri", "medyan_net_getiri", "ortalama_endekse_göre"]


def positive_summary(frame):
    usable = frame[(frame["yön"] == 1) & (frame["eksik"] == "")]
    if usable.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    return usable.groupby("vade").agg(
        olay_sayısı=("bildirim", "count"), farklı_hisse=("hisse", "nunique"),
        net_yükseliş_oranı=("net_getiri_%", lambda s: (s > 0).mean() * 100),
        ortalama_net_getiri=("net_getiri_%", "mean"),
        medyan_net_getiri=("net_getiri_%", "median"),
        ortalama_endekse_göre=("endekse_göre_%", "mean")).reset_index()


def document_gaps(conn):
    rows = conn.execute("SELECT n.id,n.title,d.issues FROM news n "
                        "JOIN pilot_selection s ON s.news_id=n.id "
                        "LEFT JOIN pilot_documents d ON d.news_id=n.id "
                        "WHERE d.issues IS NULL OR d.issues!='[]' ORDER BY n.published_at,n.id").fetchall()
    records = []
    for row in rows:
        issues = json.loads(row["issues"]) if row["issues"] is not None else ["Belge henüz denetlenmedi."]
        records.append({"bildirim": row["id"], "başlık": row["title"], "eksikler": " | ".join(issues)})  # mesajların içinde ";" olabiliyor
    return pd.DataFrame(records, columns=["bildirim", "başlık", "eksikler"])


def csv_bytes(frame):
    return frame.to_csv(index=False).encode("utf-8-sig")


def zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, data in files.items():
            archive.writestr(filename, data)
    return buffer.getvalue()


def build_report(conn, results, cost_bps=20):
    frame = pd.DataFrame(results, columns=RESULT_COLUMNS)
    summary = positive_summary(frame)
    gaps = document_gaps(conn)
    selection = backtest.metadata(conn).get("selection", {})
    missing_prices = int((frame["eksik"] != "").sum())
    methods = [
        "HALLEY — GEÇMİŞ KAP OLAY PİLOTU",
        "Dönem: {} – {}".format(selection.get("start", "?"), selection.get("end", "?")),
        "Seçilen bildirim: {}".format(selection.get("selected", "?")),
        "Sonuçlarda farklı bildirim: {}".format(frame["bildirim"].nunique()),
        "Olay/vade satırı: {}; fiyat sonucu eksik satır: {}".format(len(frame), missing_prices),
        "Eksik veya denetlenmemiş belge: {}".format(len(gaps)),
        "Sonuçlardaki 'eksik' yalnızca fiyat/ileri dönem kapsamını anlatır; bütün belgelerin "
        "eksiksiz okunduğunu göstermez. Belge eksikleri ayrı CSV'dedir.",
        "Toplam alış+satış maliyeti varsayımı: %{:.2f}".format(cost_bps / 100),
        "'endekse_göre_%' = net getiri (maliyet düşülmüş) − aynı günlerdeki XU100 getirisi.",
        "'uygulanabilirlik' sütunu: giriş veya çıkış günü açılış=en yüksek=en düşük=kapanış ise "
        "(çoğunlukla tavan/taban kilidi) işlem fiilen gerçekleşmeyebilirdi; getiri yine hesaplanır ama "
        "bu satırlar dikkatle yorumlanmalıdır. Kilitli satır: {}".format(
            int((frame["uygulanabilirlik"].fillna("") != "").sum())),
        "Giriş: yayın gününden sonraki ilk endeks işlem gününün açılışı. Giriş günü birinci "
        "işlem günüdür; 1/3/5/10. işlem günü kapanışı ölçülür.",
        "Pozitif özet yalnızca yön=1 ve fiyat sonucu tam olayları içerir. Negatif/nötr olaylar "
        "ana sonuç dosyasında kalır; açığa satış kârı hesaplanmaz.",
        "Oranlar ve getiri sütunları yüzde birimindedir. Boş özet dosyası, koşullara uyan pozitif "
        "olay bulunmadığını gösterir.",
        "Her bildirim dört vadede tekrar görünür; {} satır {} bağımsız olay anlamına gelmez "
        "({} farklı bildirim).".format(len(frame), len(frame), frame["bildirim"].nunique()),
        "Küçük örnekle eşik seçilmez veya yatırım kararı verilmez. Bu çıktı yatırım tavsiyesi değildir.",
        "YÖNTEMİN DİĞER SINIRLARI:",
    ] + ["- " + item for item in backtest.LIMITATIONS]
    files = {
        "halley_pilot.csv": csv_bytes(frame),
        "halley_pozitif_ozet.csv": csv_bytes(summary),
        "halley_belge_eksikleri.csv": csv_bytes(gaps),
        "halley_yontem.txt": ("\n\n".join(methods) + "\n").encode("utf-8-sig"),
    }
    return {"frame": frame, "summary": summary, "gaps": gaps, "files": files}
