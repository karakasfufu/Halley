"""FAZ 6: izleme kurallarının YAPAY serilerde yanlış alarm ve tespit davranışı (ön kayıt izleme_tanimi.json).
Canlıdaki izleme.olc + izleme.gecis AYNEN kullanılır (günlük kontrol, iki pencere, teyit, bastırma).
Bu ölçüm eşiklerin CANLI veride doğrulandığı anlamına gelmez.
Senaryolar (250 iş günü, günde 1–3 sonuç, aynı gün ortak şok; 100. günden sonra bozulma):
  normal     : gerçek olasılık = p + 0,8·u·p(1−p) (u ~ N(0,1) günlük ortak şok; ortalamada kalibre, p bilgilendirici)
  ayirt_yok  : 100. günden sonra gerçek olasılık p'den bağımsız (eğitim oranı + aynı şok) → ayırt etme kaybı
  kalibrasyon: 100. günden sonra gerçek olasılık 0,6·p → fazla tahmin
Kullanım: python yapay_seri.py <repo> <cikti.json> [tekrar=500]"""
import json
import random
import statistics
import sys
from pathlib import Path

GUN, DEGISIM = 250, 100


def seri(senaryo, rnd, taban):
    kay = []
    for d in range(GUN):
        u = rnd.gauss(0, 1)
        for _ in range(rnd.randint(1, 3)):
            p = rnd.betavariate(2.9, 7.1)
            if senaryo == "ayirt_yok" and d >= DEGISIM:
                q = taban + 0.8 * u * taban * (1 - taban)
            elif senaryo == "kalibrasyon" and d >= DEGISIM:
                q = 0.6 * (p + 0.8 * u * p * (1 - p))
            else:
                q = p + 0.8 * u * p * (1 - p)
            q = min(max(q, 0.001), 0.999)
            kay.append({"gun": f"g{d:04d}", "ticker": f"T{rnd.randint(0, 80)}", "y": int(rnd.random() < q), "p": p,
                        "girdi": {}, "rejim": None})
    return kay


def calistir(izleme, senaryo, tekrar, ref, tohum=20261116):
    rnd = random.Random(f"{tohum}-{senaryo}")
    sonuc = {k: {"alarm": 0, "gecikme": []} for k in
             [f"{p}|{c}" for p in ("birikimli", "son_60_gun") for c in ("P1", "P2", "K1")]}
    for _ in range(tekrar):
        kay = seri(senaryo, rnd, ref["egitim_tp1_orani"])
        durum, ilk_alarm = {}, {}
        for d in range(GUN):
            g_ = f"g{d:04d}"
            simdiye = [x for x in kay if x["gun"] <= g_]
            gunler = sorted({x["gun"] for x in simdiye})
            son = set(gunler[-60:])
            olc = {"birikimli": izleme.olc(simdiye, ref), "son_60_gun": izleme.olc([x for x in simdiye if x["gun"] in son], ref)}
            toplam = len(gunler)
            for pad, o in olc.items():
                for c in ("P1", "P2", "K1"):
                    if o[c]["durum"] == "yetersiz":
                        continue
                    k = f"{pad}|{c}"
                    g = izleme.gecis(durum.get(k), o[c]["durum"] == "esik_asildi", toplam)
                    durum[k] = {a: b for a, b in g.items() if a != "olay"}
                    if g["olay"] == "uyari_acildi" and k not in ilk_alarm:
                        ilk_alarm[k] = d
        for k, d in ilk_alarm.items():
            if senaryo == "normal" or d >= DEGISIM:
                sonuc[k]["alarm"] += 1
                if senaryo != "normal":
                    sonuc[k]["gecikme"].append(d - DEGISIM)
            elif senaryo != "normal":
                sonuc[k].setdefault("degisimden_once_alarm", 0)
                sonuc[k]["degisimden_once_alarm"] = sonuc[k].get("degisimden_once_alarm", 0) + 1
    out = {}
    for k, v in sonuc.items():
        g = v["gecikme"]
        out[k] = {("yanlis_alarm_orani_250_gun" if senaryo == "normal" else "tespit_orani_150_gun"): round(v["alarm"] / tekrar, 3),
                  "gecikme_medyan_gun": statistics.median(g) if g else None,
                  "degisimden_once_alarm_orani": round(v.get("degisimden_once_alarm", 0) / tekrar, 3)}
    return out


def main():
    repo, cikti = sys.argv[1:3]
    tekrar = int(sys.argv[3]) if len(sys.argv) > 3 else 500
    sys.path.insert(0, repo)
    from bist_haber import izleme
    ref = json.loads(izleme.REF_YOLU.read_text(encoding="utf-8"))
    out = {"not": __doc__.split("\n")[2], "tekrar": tekrar, "gun": GUN, "degisim_gunu": DEGISIM, "tohum": 20261116}
    for s in ("normal", "ayirt_yok", "kalibrasyon"):
        out[s] = calistir(izleme, s, tekrar, ref)
        print(s, json.dumps(out[s], ensure_ascii=False), flush=True)
    Path(cikti).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
