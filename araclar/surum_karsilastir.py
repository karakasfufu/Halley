"""Canlı klasördeki kod dosyalarını (satır sonları normalize) git commit'lerindeki dosyalarla karşılaştırır. Salt-okur."""
import subprocess
import sys
from pathlib import Path

R, W = Path(sys.argv[1]), Path(sys.argv[2])
commits = sys.argv[3:]
UZ = (".py", ".bat", ".txt", ".toml", ".md")


def git(*a):
    return subprocess.run(["git", "-C", str(R), *a], capture_output=True, check=True).stdout


def norm(b):
    return b.replace(b"\r\n", b"\n")


canli = {}
for p in W.rglob("*"):
    rel = p.relative_to(W).as_posix()
    if p.is_file() and rel.split("/")[0] in ("bist_haber", "tests", "app.py", "requirements.txt", "baslat.bat",
                                             ".streamlit", "paket", "arastirma") and "__pycache__" not in rel \
            and p.suffix in UZ:
        canli[rel] = norm(p.read_bytes())
for c in commits:
    dosyalar = [x for x in git("ls-tree", "-r", "--name-only", c).decode("utf-8").splitlines()
                if x in canli or (x.split("/")[0] in ("bist_haber", "tests", "app.py") and x.endswith(UZ))]
    farkli, eksik_canlida = [], []
    for f in dosyalar:
        if f not in canli:
            eksik_canlida.append(f)
            continue
        if norm(git("show", f"{c}:{f}")) != canli[f]:
            farkli.append(f)
    yalniz_canli = sorted(set(k for k in canli if k.split("/")[0] in ("bist_haber", "tests", "app.py")) - set(dosyalar))
    print(f"{c}: farklı={len(farkli)} commit'te olup canlıda yok={len(eksik_canlida)} yalnız canlıda={len(yalniz_canli)}")
    for x in farkli[:30]:
        print("   farklı:", x)
    for x in eksik_canlida[:30]:
        print("   canlıda yok:", x)
    for x in yalniz_canli[:30]:
        print("   yalnız canlıda:", x)
