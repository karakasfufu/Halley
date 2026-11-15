"""Aşama 7: Kronos ile her plan için olası 30 günlük fiyat yolları → yolların kaçında TP1 SL'den önce görülüyor?
Ayrı araştırma ortamında çalışır (%USERPROFILE%\\.venvs\\halley-arastirma; Halley'e eklenmez). Yapay zekâ (OpenAI) yok.
Yol üretimi Kronos'un auto_regressive_inference'ının aynısıdır; tek fark, örnek yolların ORTALAMASI alınmaz.
Her yol, işlem günlüğünün aynı çıkış kurallarıyla (journal.evaluate; giriş = yolun 1. gün açılışı, azami giriş üstü
girişsiz) değerlendirilir. Kaldığı yerden devam eder (çıktı CSV'ye satır satır eklenir).
Kullanım: python kronos_yol.py <repo> <kronos_kod> <arastirma.db> <planlar.csv> <cikti.csv> [model] [yol] [paket] [gün] [dönem başına plan]
15.11 bulgu: Kronos-small, fiyatı yılda ~3 kat artmış hisselerde (MOBTL, ASELS) ertesi gün −%30…−%40 öngörüyor (BIST
günlük sınırı ±%10) → varsayılan Kronos-mini (makul ve ~5 kat hızlı). İlk günü ±%11'i aşan yol geçersiz sayılır.
"""
import csv
import os
import sqlite3
import sys
import time
from datetime import timedelta

import numpy as np
import pandas as pd
import torch

repo, kod, dbp, plans_p, out_p = sys.argv[1:6]
MODEL = sys.argv[6] if len(sys.argv) > 6 else "NeoQuasar/Kronos-mini"
TOK = "NeoQuasar/Kronos-Tokenizer-2k" if MODEL.endswith("mini") else "NeoQuasar/Kronos-Tokenizer-base"
S = int(sys.argv[7]) if len(sys.argv) > 7 else 16          # plan başına yol sayısı
BATCH = int(sys.argv[8]) if len(sys.argv) > 8 else 4       # aynı anda plan sayısı
CTX, CLIP = 250, 5
H = int(sys.argv[9]) if len(sys.argv) > 9 else 20       # yol uzunluğu (işlem günü)
N_DONEM = int(sys.argv[10]) if len(sys.argv) > 10 else 1000   # dönem başına plan
sys.path.insert(0, kod)
sys.path.insert(0, repo)
from model import Kronos, KronosTokenizer  # noqa: E402
from model.kronos import calc_time_stamps, sample_from_logits  # noqa: E402
from bist_haber import journal  # noqa: E402

torch.set_num_threads(max(1, (os.cpu_count() or 4)))
print("iş parçacığı", torch.get_num_threads(), flush=True)
torch.manual_seed(7)
tok = KronosTokenizer.from_pretrained(TOK).eval()
mdl = Kronos.from_pretrained(MODEL).eval()


def paths(x, xs, ys):
    """x: (B, L, 6) normalize; xs: (B, L, 5); ys: (B, H, 5) → (B, S, H, 6) normalize uzayında yollar."""
    with torch.no_grad():
        B, L = x.shape[0], x.shape[1]
        x = torch.clip(x, -CLIP, CLIP).repeat_interleave(S, 0)
        xs, ys = xs.repeat_interleave(S, 0), ys.repeat_interleave(S, 0)
        pre, post = tok.encode(x, half=True)
        stamp = torch.cat([xs, ys], 1)
        for i in range(H):
            n = L + i
            st = max(0, n - 512)
            s1, ctx = mdl.decode_s1(pre[:, st:n], post[:, st:n], stamp[:, st:n].contiguous())
            a = sample_from_logits(s1[:, -1, :], temperature=1.0, top_k=0, top_p=0.9, sample_logits=True)
            s2 = mdl.decode_s2(ctx, a)
            b = sample_from_logits(s2[:, -1, :], temperature=1.0, top_k=0, top_p=0.9, sample_logits=True)
            pre, post = torch.cat([pre, a], 1), torch.cat([post, b], 1)
        st = max(0, L + H - 512)
        z = tok.decode([pre[:, st:].contiguous(), post[:, st:].contiguous()], half=True)
        return z[:, -H:, :].reshape(B, S, H, -1).numpy()


def main():
    conn = sqlite3.connect(f"file:{dbp}?mode=ro", uri=True)
    plans = pd.read_csv(plans_p, dtype={"tarih": str})
    plans = plans.groupby("donem", group_keys=False).head(N_DONEM)      # planlar.csv zaten karışık sırada
    done = set()
    if os.path.exists(out_p):
        done = set(pd.read_csv(out_p, dtype={"tarih": str}).apply(lambda r: (r.ticker, r.tarih), axis=1))
    todo = plans[[(a, b) not in done for a, b in zip(plans.ticker, plans.tarih)]]
    print("plan", len(plans), "kalan", len(todo), "model", MODEL, "yol", S, flush=True)
    new = not os.path.exists(out_p)
    f = open(out_p, "a", newline="", encoding="utf-8")
    w = csv.writer(f)
    if new:
        w.writerow(["ticker", "tarih", "k_tp1", "k_sl", "k_giris", "k_R", "k_getiri10", "k_n", "k_gecersiz"])
    t0, k = time.time(), 0
    rows = list(todo.itertuples(index=False))
    for i in range(0, len(rows), BATCH):
        part = rows[i:i + BATCH]
        X, XS, YS, meta = [], [], [], []
        for p in part:
            b = pd.read_sql("SELECT date, open, high, low, close, volume FROM prices WHERE ticker=? AND date<=? "
                            "ORDER BY date DESC LIMIT ?", conn, params=(p.ticker, p.tarih, CTX)).iloc[::-1]
            if len(b) < CTX or b[["open", "high", "low", "close", "volume"]].isna().any().any():
                continue
            b["amount"] = b["volume"] * b[["open", "high", "low", "close"]].mean(axis=1)
            x = b[["open", "high", "low", "close", "volume", "amount"]].values.astype(np.float32)
            mu, sd = x.mean(0), x.std(0)
            ts = pd.to_datetime(b["date"]).reset_index(drop=True)
            fut = pd.Series(pd.bdate_range(ts.iloc[-1] + timedelta(days=1), periods=H))
            X.append((x - mu) / (sd + 1e-5))
            XS.append(calc_time_stamps(ts).values.astype(np.float32))
            YS.append(calc_time_stamps(fut).values.astype(np.float32))
            meta.append((p, mu, sd, fut))
        if not meta:
            continue
        z = paths(torch.tensor(np.stack(X)), torch.tensor(np.stack(XS)), torch.tensor(np.stack(YS)))
        for (p, mu, sd, fut), zz in zip(meta, z):
            px = zz * (sd + 1e-5) + mu                              # (S, H, 6)
            tp1_n = sl_n = ent = bad = 0
            rs, g10 = [], []
            for s in range(S):
                o, h, l, c = px[s, :, 0], px[s, :, 1], px[s, :, 2], px[s, :, 3]
                if abs(c[0] / p.kapanis - 1) > 0.11 or abs(o[0] / p.kapanis - 1) > 0.11:
                    bad += 1                                        # BIST günlük sınırını aşan yol: model hatası
                    continue
                hi, lo = np.maximum.reduce([o, h, c]), np.minimum.reduce([o, l, c])   # tutarlı mum
                if o[0] > p.azami + 1e-9:
                    continue
                ent += 1
                bars = [{"date": d.date().isoformat(), "open": float(o[j]), "high": float(hi[j]), "low": float(lo[j]),
                         "close": float(c[j])} for j, d in enumerate(fut)]
                rec = {"kaynak": "gercek", "gercek_giris_gunu": bars[0]["date"], "gercek_giris_fiyati": float(o[0]),
                       "signal_day": p.tarih, "senaryo": p.tur, "sl": p.sl, "tp1": p.tp1, "tp2": p.tp2,
                       "giris": p.giris, "alarm": None, "gecerlilik": 1}
                res = journal.evaluate(rec, bars, 0.20, 0.10)
                tp1_n += bool(res.get("tp1_goruldu"))
                sl_n += res.get("sonuc") == "SL"
                if res.get("r") is not None:
                    rs.append(res["r"])
                g10.append(float(c[min(9, H - 1)] / p.kapanis - 1) * 100)
            w.writerow([p.ticker, p.tarih, round(tp1_n / ent, 4) if ent else "", round(sl_n / ent, 4) if ent else "",
                        round(ent / S, 4), round(float(np.mean(rs)), 4) if rs else "",
                        round(float(np.median(g10)), 3) if g10 else "", S, bad])
            k += 1
        f.flush()
        if (i // BATCH) % 10 == 0:
            el = time.time() - t0
            print(f"{k}/{len(rows)} plan · {el:.0f} sn · plan başına {el / max(k, 1):.1f} sn", flush=True)
    f.close()
    print("bitti", k, round(time.time() - t0), "sn", flush=True)


if __name__ == "__main__":
    main()
