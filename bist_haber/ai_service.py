"""Merkezi yapay zekâ servisi (2026-11-14, plan Aşama 2). BÜTÜN OpenAI çağrıları buradan geçer ve kaydedilir.

Her çağrı için ai_calls tablosuna: zaman, modül (haber_analizi, rapor_yorumu, kacirilan_aciklama, pilot, ...),
işlem (on_eleme, tam_analiz, ikinci_gorus, ...), ilgili kayıt (haber no vb.), model, girdi/çıktı tokenı, tahmini
maliyet ($), süre, durum (ok/hata), hata metni ve tekrar sayısı (model bir parametreyi desteklemediğinde parametre
çıkarılıp yeniden denenir). Kayıt başarısız olursa çağrı bozulmaz (yalnız kayıt atlanır).

Model değişmez: config.MODEL_ANALYSIS / MODEL_FILTER (gpt-5-mini). Yapay zekâ olmadan uygulama çalışır; bu servis
yalnız kullanıcı bir YZ işlemi başlattığında kullanılır.
"""
import sqlite3
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS ai_calls (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    zaman         TEXT NOT NULL,
    modul         TEXT NOT NULL,
    islem         TEXT,
    ref           TEXT,
    model         TEXT,
    input_tokens  INTEGER DEFAULT 0,
    output_tokens INTEGER DEFAULT 0,
    usd           REAL DEFAULT 0,
    sure_ms       INTEGER,
    durum         TEXT NOT NULL,          -- ok | hata
    hata          TEXT,
    deneme        INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_ai_calls_zaman ON ai_calls(zaman);
"""
MODULE_TR = {"haber_analizi": "Haber analizi", "derin_inceleme": "Derin yeniden inceleme", "ucuz_test": "Ucuz test",
             "rapor_yorumu": "Rapor yorumu", "kacirilan_aciklama": "Kaçırılan fırsat açıklaması",
             "pilot": "Geçmiş veri pilotu", "takip_haber": "Takip listesi haber analizi",
             "hazir_haber": "Hazır fırsat haber kontrolü", "genel": "Diğer"}
ISLEM_TR = {"on_eleme": "ön eleme", "tam_analiz": "tam analiz", "ikinci_gorus": "ikinci görüş", "yorum": "yorum",
            "aciklama": "açıklama"}


def usd(tin: float, tout: float) -> float:
    from .pipeline import INPUT_USD_PER_TOKEN, OUTPUT_USD_PER_TOKEN
    return (tin or 0) * INPUT_USD_PER_TOKEN + (tout or 0) * OUTPUT_USD_PER_TOKEN


def is_real(client) -> bool:
    """Gerçek OpenAI istemcisi mi? (testlerdeki sahte istemcilerin çağrıları kaydedilmez)"""
    return type(client).__module__.split(".")[0] == "openai"


def record(modul: str, islem: Optional[str], ref: Optional[str], model: Optional[str], tin: int, tout: int,
           durum: str = "ok", hata: Optional[str] = None, deneme: int = 0, sure_ms: Optional[int] = None,
           db_path=None) -> None:
    """Çağrıyı kaydeder (paralel iş parçacıklarından güvenle: her kayıt kendi kısa bağlantısıyla)."""
    try:
        c = sqlite3.connect(db_path or config.DB_PATH, timeout=30)
        try:
            c.executescript(SCHEMA)
            c.execute("INSERT INTO ai_calls(zaman,modul,islem,ref,model,input_tokens,output_tokens,usd,sure_ms,durum,hata,"
                      "deneme) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                      (datetime.now(config.TR_TZ).isoformat(timespec="seconds"), modul, islem, ref, model, tin or 0,
                       tout or 0, usd(tin, tout), sure_ms, durum, (hata or "")[:300] or None, deneme))
            c.commit()
        finally:
            c.close()
    except Exception:
        pass   # kayıt hatası çağrıyı bozmasın


class LLM:
    """OpenAI istemcisi (yapılandırılmış JSON). modul: hangi özelliğin çağırdığı (kullanım ekranında görünür)."""

    def __init__(self, modul: str = "genel", client=None, db_path=None):
        if client is None:
            from openai import OpenAI
            client = OpenAI()       # OPENAI_API_KEY ortam değişkeninden okunur
        self.client = client
        self.modul = modul
        self.db_path = db_path
        self._unsupported = set()   # (model, parametre) çiftleri

    def parse(self, model: str, system: str, user: str, schema, reasoning_effort: Optional[str] = None,
              islem: Optional[str] = None, ref: Optional[str] = None):
        from openai import BadRequestError
        kwargs = dict(model=model, response_format=schema,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        # temperature=0: tutarlılık. reasoning_effort: düşünme miktarı (token/maliyet). Model desteklemiyorsa
        # parametre çıkarılıp yeniden denenir (tekrar sayısı kaydedilir).
        optional = {"temperature": 0}
        if reasoning_effort:
            optional["reasoning_effort"] = reasoning_effort
        for k, v in optional.items():
            if (model, k) not in self._unsupported:
                kwargs[k] = v
        t0, tries = time.time(), 0
        modul, db = getattr(self, "modul", "genel"), getattr(self, "db_path", None)
        if db is None and not is_real(self.client):
            def record(*a, **k):    # sahte istemci (test): gerçek kullanım kaydına yazma
                return None
        else:
            record = globals()["record"]
        while True:
            try:
                resp = self.client.chat.completions.parse(**kwargs)
                break
            except BadRequestError as e:
                bad = [k for k in optional if k in kwargs and k in str(e)]
                if not bad:
                    record(modul, islem, ref, model, 0, 0, "hata", str(e), tries,
                           int((time.time() - t0) * 1000), db)
                    raise
                tries += 1
                for k in bad:
                    self._unsupported.add((model, k))
                    kwargs.pop(k)
            except Exception as e:
                record(modul, islem, ref, model, 0, 0, "hata", str(e), tries, int((time.time() - t0) * 1000),
                       db)
                raise
        msg = resp.choices[0].message
        u = resp.usage
        tin, tout = (u.prompt_tokens if u else 0), (u.completion_tokens if u else 0)
        ms = int((time.time() - t0) * 1000)
        if msg.refusal:
            record(modul, islem, ref, model, tin, tout, "hata", f"model reddetti: {msg.refusal}", tries, ms,
                   db)
            raise RuntimeError(f"model reddetti: {msg.refusal}")
        record(modul, islem, ref, model, tin, tout, "ok", None, tries, ms, db)
        return msg.parsed, tin, tout


# ---------------------------------------------------------------- kullanım özeti (panel)
def _ensure(conn) -> None:
    conn.executescript(SCHEMA)


def usage(conn, now: Optional[datetime] = None) -> Dict:
    """Bugün / bu ay / son 30 gün: çağrı, token, maliyet; modül ve işlem kırılımı; günlük seri; son hatalar."""
    _ensure(conn)
    now = now or datetime.now(config.TR_TZ)
    day, month = now.date().isoformat(), now.strftime("%Y-%m")
    since30 = (now.date() - timedelta(days=29)).isoformat()

    def tot(where: str, args: tuple) -> Dict:
        r = conn.execute(f"SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0), "
                         f"COALESCE(SUM(usd),0), COALESCE(SUM(durum='hata'),0), COALESCE(SUM(deneme),0) FROM ai_calls "
                         f"WHERE {where}", args).fetchone()
        return {"cagri": r[0], "girdi": r[1], "cikti": r[2], "usd": r[3], "hata": r[4], "tekrar": r[5]}

    out = {"bugun": tot("substr(zaman,1,10)=?", (day,)), "ay": tot("substr(zaman,1,7)=?", (month,)),
           "toplam": tot("1=1", ())}
    out["modul"] = [{"Modül": MODULE_TR.get(m, m), "İşlem": ISLEM_TR.get(i, i or "—"), "Çağrı": n, "Girdi token": a,
                     "Çıktı token": b, "Maliyet $": round(u, 4), "Hata": h}
                    for m, i, n, a, b, u, h in conn.execute(
                        "SELECT modul, islem, COUNT(*), SUM(input_tokens), SUM(output_tokens), SUM(usd), SUM(durum='hata') "
                        "FROM ai_calls WHERE substr(zaman,1,7)=? GROUP BY modul, islem ORDER BY SUM(usd) DESC", (month,))]
    out["gunluk"] = [{"Gün": d, "Çağrı": n, "Maliyet $": round(u, 4)} for d, n, u in conn.execute(
        "SELECT substr(zaman,1,10) d, COUNT(*), SUM(usd) FROM ai_calls WHERE substr(zaman,1,10)>=? GROUP BY d ORDER BY d",
        (since30,))]
    out["hatalar"] = [dict(zip(("zaman", "modul", "islem", "hata"), r)) for r in conn.execute(
        "SELECT zaman, modul, islem, hata FROM ai_calls WHERE durum='hata' ORDER BY id DESC LIMIT 10")]
    out["son"] = [dict(zip(("zaman", "modul", "islem", "ref", "girdi", "cikti", "usd", "durum"), r)) for r in conn.execute(
        "SELECT zaman, modul, islem, ref, input_tokens, output_tokens, usd, durum FROM ai_calls ORDER BY id DESC LIMIT 30")]
    # servis öncesi (2026-11-14'ten önce) haber analizi harcaması: analyses tablosundan
    r = conn.execute("SELECT COUNT(*), COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses "
                     "WHERE created_at < COALESCE((SELECT MIN(zaman) FROM ai_calls), '9999')").fetchone()
    out["oncesi"] = {"cagri": r[0], "usd": usd(r[1], r[2])}
    return out


def month_usd(conn, now: Optional[datetime] = None) -> float:
    _ensure(conn)
    now = now or datetime.now(config.TR_TZ)
    return conn.execute("SELECT COALESCE(SUM(usd),0) FROM ai_calls WHERE substr(zaman,1,7)=?",
                        (now.strftime("%Y-%m"),)).fetchone()[0]


def recent_calls(conn, limit: int = 30) -> List[Dict]:
    return usage(conn)["son"][:limit]
