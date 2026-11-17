"""Yayından sonra: eski kararlı sürüm (v202611152318) kurulumu GERÇEK GitHub adresinden kendi güncelleyicisiyle yeni sürümü
bulur, indirir, doğrular ve kurar (müşterinin yolu). Gerçek API anahtarı yok."""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

S = Path(sys.argv[1])
H = S / "gercek_adres_test" / "Halley"
PORT = 8515
if H.parent.exists():
    shutil.rmtree(H.parent)
H.parent.mkdir(parents=True)
subprocess.run([str(S / "eski_surum" / "Halley_Kurulum.exe"), "/sessiz", f"/hedef={H}", "/kisayolsuz", "/baslatma"],
               timeout=900, check=True)
(H / "app" / "data").mkdir(parents=True, exist_ok=True)
(H / "app" / "data" / "ayarlar.json").write_text(json.dumps({"deneme": "gercek_adres"}), encoding="utf-8")
env = {k: v for k, v in os.environ.items() if k not in ("HALLEY_OFFLINE",)}
env.update(PYTHONUTF8="1")
kod = r"""
import sys, json; sys.path.insert(0, '.')
from bist_haber import guncelleme as g
k = g.kontrol(zorla=True)
print(json.dumps({k2: k.get(k2) for k2 in ('durum', 'kurulu', 'yeni', 'notlar', 'boyut_mb')}, ensure_ascii=False))
if k.get('durum') == 'yeni':
    print(json.dumps(g.hazirla(g.manifest())))
"""
r = subprocess.run([str(H / "python" / "python.exe"), "-c", kod], cwd=str(H / "app"), capture_output=True, text=True,
                   env=env, timeout=600)
rapor = {"eski_guncelleyici": (r.stdout.strip() or r.stderr.strip()[-500:])}
subprocess.Popen([str(H / "Halley.exe"), "--yeniden-baslat", "--pencere-yok", "--port", str(PORT)], cwd=str(H),
                 env=dict(env, HALLEY_OFFLINE="1"))
t0, ok = time.time(), None
while time.time() - t0 < 240:
    try:
        if urllib.request.urlopen(f"http://127.0.0.1:{PORT}/_stcore/health", timeout=3).read() == b"ok":
            ok = round(time.time() - t0)
            break
    except Exception:
        time.sleep(2)
time.sleep(8)
rapor["acilis_sn"] = ok
rapor["surum"] = (H / "surum.txt").read_text(encoding="utf-8").strip()
rapor["son_islem"] = json.loads((H / "guncelleme" / "son_islem.json").read_text(encoding="utf-8-sig")) \
    if (H / "guncelleme" / "son_islem.json").exists() else None
rapor["ayarlar_korundu"] = json.loads((H / "app" / "data" / "ayarlar.json").read_text(encoding="utf-8-sig")).get("deneme")
rapor["onceki"] = (H / "guncelleme" / "onceki" / "app.py").exists()
subprocess.run([str(H / "Halley.exe"), "--kapat"], timeout=90)
print(json.dumps(rapor, ensure_ascii=False, indent=1))
