"""FAZ 3 Ek I2: geçici köken kanıtlarını kalıcı proje arşivine kopyalar (Git'e EKLENMEZ; büyük veri). Kaynak dosyalar
silinmez/değiştirilmez; kopyalar dosya zamanı korunarak alınır, SHA-256 kaynak ve kopyada ayrı ayrı doğrulanır.
Manifest (parmak izi, boyut, satır sayısı, dosya zamanı) arşive ve Git'teki sonuç klasörüne yazılır.
Oturum günlüğünden model kaydı komutu ve çıktısı ayrı metin dosyası olarak saklanır.
Kullanım: python kanit_arsivle.py <eski_a6_klasoru> <faz2_klasoru> <oturum_gunlugu.jsonl> <arsiv_klasoru> <manifest.json>"""
import hashlib
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

A6 = ["etiket.csv", "etiket.log", "etiket2.csv", "etiket2.log", "etiket3.csv", "etiketle.py", "model.py", "sonuc.json",
      "egit_sonuc.json", "indir.py", "indir.log", "deneme.csv", "deneme.json", "deneme2.csv", "kap.log", "kap2.log",
      "kap3.log", "arastirma_5y_yedek.db", "arastirma_5y_yedek2.db"]
FAZ2 = ["planlar_seviyeli.csv", "etiketle.log"]
GUNLUK_ANLARI = ("2026-11-15T08:50:38.125Z", "2026-11-15T08:55:19.640Z")


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def satir(p):
    if p.suffix not in (".csv", ".log", ".py", ".json"):
        return None
    with open(p, "rb") as f:
        return sum(1 for _ in f)


def main():
    a6, faz2, gunluk, arsiv, manifest = map(Path, sys.argv[1:6])
    arsiv.mkdir(parents=True, exist_ok=True)
    kayit = {"olusturuldu": datetime.now().astimezone().isoformat(timespec="seconds"), "arsiv": str(arsiv),
             "not": "Dosya zamanı tek başına hangi etiketle eğitildiğinin kanıtı değildir. Kanıt: oturum günlüğü komut "
                    "kaydı (gunluk_model_kaydi.txt) + tp1_v1 tablo grup sayılarının etiket dosyasıyla birebirliği.",
             "dosyalar": []}
    for kaynak_k, adlar, alt in ((a6, A6, "a6_15kasim"), (faz2, FAZ2, "faz2_16kasim")):
        (arsiv / alt).mkdir(exist_ok=True)
        for ad in adlar:
            s = kaynak_k / ad
            if not s.exists():
                kayit["dosyalar"].append({"dosya": f"{alt}/{ad}", "durum": "kaynakta yok"})
                continue
            h = sha(s)
            d = arsiv / alt / ad
            shutil.copy2(s, d)
            h2 = sha(d)
            st = s.stat()
            kayit["dosyalar"].append({"dosya": f"{alt}/{ad}", "kaynak": str(s), "boyut": st.st_size, "satir": satir(s),
                                      "degistirilme": datetime.fromtimestamp(st.st_mtime).astimezone().isoformat(
                                          timespec="seconds"), "sha256": h, "kopya_ayni": h == h2})
    parca = []
    satirlar = [json.loads(x) for x in open(gunluk, encoding="utf-8") if x.strip().startswith("{")]
    ids = {}
    for o in satirlar:
        if o.get("timestamp") in GUNLUK_ANLARI:
            for c in (o.get("message") or {}).get("content") or []:
                if isinstance(c, dict) and c.get("type") == "tool_use":
                    ids[c["id"]] = o["timestamp"]
                    parca.append(f"=== KOMUT {o['timestamp']} ===\n{c['input'].get('command', '')[-600:]}\n")
    for o in satirlar:
        cont = (o.get("message") or {}).get("content")
        for c in cont if isinstance(cont, list) else []:
            if isinstance(c, dict) and c.get("type") == "tool_result" and c.get("tool_use_id") in ids:
                cc = c.get("content")
                txt = cc if isinstance(cc, str) else "\n".join(x.get("text", "") for x in cc if isinstance(x, dict))
                parca.append(f"=== ÇIKTI {o.get('timestamp')} (komut {ids[c['tool_use_id']]}) ===\n{txt[:3000]}\n")
    (arsiv / "gunluk_model_kaydi.txt").write_text(
        f"Kaynak: {gunluk}\nOturum günlüğünden alıntı (değiştirilmeden).\n\n" + "\n".join(parca), encoding="utf-8")
    kayit["gunluk_alintisi"] = {"dosya": "gunluk_model_kaydi.txt", "sha256": sha(arsiv / "gunluk_model_kaydi.txt"),
                                "kaynak_gunluk": str(gunluk)}
    kayit["hepsi_dogru_kopyalandi"] = all(x.get("kopya_ayni", True) for x in kayit["dosyalar"])
    for p in (arsiv / "manifest.json", manifest):
        p.write_text(json.dumps(kayit, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"dosya": len(kayit["dosyalar"]), "tamam": kayit["hepsi_dogru_kopyalandi"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
