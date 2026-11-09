"""Fırsat listesi değişim kaydı (2026-11-09 kullanıcı sorusu: "20'den 19'a düştü, neye göre?").

Uygun senaryo listesi kayıtlı veriden her çizimde yeniden hesaplanır; haber skoru haberin yaşıyla azaldığı, fiyatlar
güncellendiği ve yeni haberler analiz edildiği için liste kendiliğinden değişebilir. Liste her değiştiğinde hangi
hissenin girip çıktığı ve NEDENİ (signals.decide — panel ve bekçiyle aynı karar kodu) data/firsat_gecmisi.json'a
yazılır; panel bunu gösterir. Yalnız kayıttır; hiçbir karar ya da eşik değişmez.
"""
import json
from datetime import datetime
from typing import Callable, Dict, List, Optional

from . import config

KEEP = 60


def path():
    return config.DATA / "firsat_gecmisi.json"


def load() -> List[Dict]:
    try:
        return json.loads(path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def record(uygun: List[str], why: Callable[[str], str], now: Optional[datetime] = None) -> Dict:
    """uygun: şu anki uygun hisseler; why(hisse): listede olmayan hisse için neden metni.
    Değişiklik yoksa son kaydı döndürür (dosyaya yazmaz)."""
    now = now or datetime.now(config.TR_TZ)
    hist = load()
    cur = sorted(set(uygun))
    last = hist[-1] if hist else None
    if last and last["hisseler"] == cur:
        return dict(last, degisti=False)
    prev = set(last["hisseler"]) if last else set()
    entry = {"zaman": now.isoformat(timespec="seconds"), "hisseler": cur, "sayi": len(cur),
             "onceki_sayi": len(prev) if last else None,
             "eklenen": sorted(set(cur) - prev) if last else [],
             "cikan": [{"hisse": t, "neden": why(t)} for t in sorted(prev - set(cur))]}
    hist.append(entry)
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(hist[-KEEP:], ensure_ascii=False, indent=1), encoding="utf-8")
    return dict(entry, degisti=True)


def changes(limit: int = 15) -> List[Dict]:
    """Yeniden eskiye, yalnız gerçekten giren/çıkan olan kayıtlar."""
    return [h for h in reversed(load()) if h.get("eklenen") or h.get("cikan")][:limit]
