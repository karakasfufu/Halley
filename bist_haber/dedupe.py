"""İçerik özeti ve tekrarlanan haber ayıklama (2026-11-14, plan Aşama 2). Yapay zekâ KULLANILMAZ.

- content_hash: başlık + metin (Türkçe katlanmış, boşluklar sadeleştirilmiş) SHA-256. Aynı içerik analiz edildiyse
  (başka kayıt numarasıyla gelse bile) yeniden yapay zekâya GÖNDERİLMEZ: haber 'duplicate' olur, notunda ilk kaydın
  numarası yazar.
- Haber siteleri (RSS): aynı başlık (katlanmış) 3 gün içinde başka kaynaktan geldiyse tekrar sayılır.
- Güvenlik: yeni kaydın aday hisseleri ilk kaydınkilerin İÇİNDE değilse tekrar SAYILMAZ (ör. aynı metni iki farklı
  şirket ayrı ayrı yayımladıysa her biri analiz edilir; o şirketin etkisi kaybolmasın).
"""
import hashlib
import re
from datetime import datetime, timedelta
from typing import Dict, List, Tuple

from .textutil import tr_fold

TITLE_WINDOW_DAYS = 3


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", tr_fold(text or "")).strip()


def content_hash(row) -> str:
    return hashlib.sha256((_norm(row["title"]) + "\n" + _norm(row["body"])[:20000]).encode("utf-8")).hexdigest()


def title_key(row) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", tr_fold(row["title"] or "")))


def _cands(row) -> set:
    return {c for c in (row["candidates"] or "").split(",") if c}


def filter_duplicates(conn, rows: List) -> Tuple[List, int]:
    """Analiz edilecek haberlerden tekrarları ayıklar ('duplicate' olarak işaretler); kalanların özetini kaydeder."""
    if not rows:
        return list(rows), 0
    if "content_hash" not in {c[1] for c in conn.execute("PRAGMA table_info(news)")}:   # pilot gibi ayrı veritabanları
        conn.execute("ALTER TABLE news ADD COLUMN content_hash TEXT")
    for r in conn.execute("SELECT id, title, body FROM news WHERE status='analyzed' AND content_hash IS NULL").fetchall():
        conn.execute("UPDATE news SET content_hash=? WHERE id=?", (content_hash(r), r["id"]))   # eski kayıtlar bir kez
    seen: Dict[str, Tuple[str, set]] = {
        h: (i, _cands({"candidates": c})) for i, h, c in conn.execute(
            "SELECT id, content_hash, candidates FROM news WHERE status='analyzed' AND content_hash IS NOT NULL")}
    titles: Dict[str, Tuple[str, set, str]] = {}
    oldest = min((r["published_at"] or "") for r in rows)
    since = (datetime.fromisoformat(oldest) - timedelta(days=TITLE_WINDOW_DAYS)).isoformat() if oldest else ""
    for i, t, c, p in conn.execute("SELECT id, title, candidates, published_at FROM news WHERE source LIKE 'rss:%' "
                                   "AND status='analyzed' AND published_at>=?", (since,)):
        titles.setdefault(title_key({"title": t}), (i, _cands({"candidates": c}), p))
    # Aynı PARTİDEKİ tekrar kalıcı işaretlenmez, yalnız bu tur atlanır (2026-11-14 denetimde bulundu: ilk kayıt hata
    # alır ya da bütçeye takılırsa ikincisi "analiz edilmiş kaydın tekrarı" sanılıp hiç analiz edilmeyebilirdi).
    # İlk kayıt gerçekten analiz edilince sonraki turda kalıcı 'duplicate' olur.
    batch_h: Dict[str, Tuple[str, set]] = {}
    batch_t: Dict[str, Tuple[str, set, str]] = {}

    def same_title(r, m) -> bool:
        return abs((datetime.fromisoformat(r["published_at"]) - datetime.fromisoformat(m[2])).days) <= TITLE_WINDOW_DAYS

    kept, dup = [], 0
    for r in rows:
        h = content_hash(r)
        mine = _cands(r)
        rss = str(r["source"]).startswith("rss:")
        tk = title_key(r) if rss else ""
        match, m = seen.get(h), titles.get(tk) if tk else None
        why = None
        if match and mine <= match[1]:
            why = f"aynı içerik {match[0]} kaydıyla analiz edildi"
        elif m and mine <= m[1] and same_title(r, m):
            why = f"aynı başlık başka kaynakta ({m[0]}) analiz edildi"
        if why:
            conn.execute("UPDATE news SET status='duplicate', note=?, content_hash=? WHERE id=?", (why, h, r["id"]))
            dup += 1
            continue
        conn.execute("UPDATE news SET content_hash=? WHERE id=?", (h, r["id"]))
        bm, bt = batch_h.get(h), batch_t.get(tk) if tk else None
        if (bm and mine <= bm[1]) or (bt and mine <= bt[1] and same_title(r, bt)):
            dup += 1            # bu tur atlanır, durumu 'new' kalır
            continue
        batch_h.setdefault(h, (r["id"], mine))
        if tk:
            batch_t.setdefault(tk, (r["id"], mine, r["published_at"]))
        kept.append(r)
    conn.commit()
    return kept, dup
