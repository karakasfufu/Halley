"""Telegram bildirimleri (2026-11-09 kullanıcı isteği: "telegram üzerinden bildirim göndersin bize").

Ücretsizdir (Telegram Bot API), yapay zekâ KULLANMAZ. Bot anahtarı ve sohbet numaraları .env dosyasında durur
(kodda/GitHub'da/veri aktarma dosyasında DEĞİL, Dipnot 10). Bildirim yalnız bilgi verir; emir vermez.
Gönderim hatası analizi asla bozmaz: sonuç {"ok": False, "hatalar": [...]} olarak döner ve ekrana yazılır.
"""
import os
from typing import Callable, Dict, List, Optional

import requests

from . import config

API = "https://api.telegram.org/bot{token}/{method}"
MAX_LEN = 4000          # Telegram sınırı 4096 karakter
TOKEN_KEY, CHAT_KEY = "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"
FOOT = "\nℹ️ Bilgi amaçlıdır, yatırım tavsiyesi değildir. Emirleri Midas'tan siz verirsiniz."


def token() -> str:
    return os.getenv(TOKEN_KEY, "").strip()


def chat_ids() -> List[str]:
    return [c.strip() for c in os.getenv(CHAT_KEY, "").replace(";", ",").split(",") if c.strip()]


def configured() -> bool:
    return bool(token() and chat_ids())


def save(tok: Optional[str] = None, chats: Optional[List[str]] = None) -> None:
    """Bot anahtarını ve/veya sohbet numaralarını .env'e yazar; diğer satırlara (OpenAI anahtarı) dokunmaz."""
    env = config.ROOT / ".env"
    lines = env.read_text(encoding="utf-8-sig").splitlines() if env.exists() else []
    for key, val in ((TOKEN_KEY, tok), (CHAT_KEY, None if chats is None else ",".join(chats))):
        if val is None:
            continue
        lines = [l for l in lines if not l.startswith(key + "=")]
        if val.strip():
            lines.append(f"{key}={val.strip()}")
        os.environ[key] = val.strip()
    env.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _call(method: str, tok: str, post: Callable, **payload) -> Dict:
    if os.environ.get("HALLEY_OFFLINE"):
        raise RuntimeError("çevrimdışı deneme kipinde Telegram'a bağlanılmaz")
    r = (post or requests.post)(API.format(token=tok, method=method), json=payload, timeout=15)
    try:
        body = r.json()
    except ValueError:
        body = {}
    if not body.get("ok"):
        desc = str(body.get("description") or f"HTTP {getattr(r, 'status_code', '?')}")
        if "Unauthorized" in desc or getattr(r, "status_code", 0) == 401:
            raise RuntimeError("bot anahtarı geçersiz (BotFather'dan aldığınız anahtarı kontrol edin)")
        if "chat not found" in desc:
            raise RuntimeError("sohbet bulunamadı (önce Telegram'da bota /start yazın)")
        if "blocked" in desc:
            raise RuntimeError("bot bu kişi tarafından engellenmiş")
        raise RuntimeError(desc)
    return body


def _nice(e: Exception, tok: str) -> str:
    msg = str(e)
    if "HTTPSConnectionPool" in msg or "Max retries" in msg or "timed out" in msg.lower():
        msg = "api.telegram.org adresine bağlanılamadı (internet bağlantısını kontrol edin)"
    return msg.replace(tok, "***") if tok else msg


def find_chats(tok: Optional[str] = None, post: Optional[Callable] = None) -> List[Dict]:
    """Bota son günlerde mesaj yazan kişi/grupları listeler (sohbet numarasını elle aramaya gerek kalmasın)."""
    tok = tok or token()
    try:
        body = _call("getUpdates", tok, post)
    except Exception as e:
        raise RuntimeError(_nice(e, tok)) from None
    seen = {}
    for u in body.get("result", []):
        msg = u.get("message") or u.get("my_chat_member") or u.get("channel_post") or {}
        ch = msg.get("chat") or {}
        if "id" in ch:
            name = ch.get("title") or " ".join(x for x in (ch.get("first_name"), ch.get("last_name")) if x) \
                or ch.get("username") or "?"
            seen[str(ch["id"])] = {"id": str(ch["id"]), "ad": name, "tur": ch.get("type", "")}
    return list(seen.values())


def send(text: str, tok: Optional[str] = None, chats: Optional[List[str]] = None,
         post: Optional[Callable] = None) -> Dict:
    """Her sohbete ayrı gönderir; biri başarısız olsa da diğerleri gider. Asla istisna fırlatmaz."""
    tok = tok if tok is not None else token()
    chats = chats if chats is not None else chat_ids()
    if not tok or not chats:
        return {"ok": False, "gonderilen": 0, "hatalar": ["Telegram ayarlanmamış (⚙️ Ayarlar → 📨 Telegram)"]}
    if len(text) > MAX_LEN:
        text = text[:MAX_LEN - 60].rstrip() + "\n… (devamı panelde, 📋 Raporlar)"
    sent, errs = 0, []
    for c in chats:
        try:
            _call("sendMessage", tok, post, chat_id=c, text=text, disable_web_page_preview=True)
            sent += 1
        except Exception as e:  # ağ hatası dahil: analiz bozulmasın
            errs.append(f"{c}: {_nice(e, tok)}")
    return {"ok": sent == len(chats), "gonderilen": sent, "hatalar": errs}


# ---------------------------------------------------------------- mesaj metinleri (yalnız kayıtlı veri)
def _n(v, f="{:.2f}"):
    return "—" if v is None else f.format(v)


def _changes(out, keep=lambda c: True) -> List[str]:
    names = {"açık": "girişi gerçekleşti", "açık (TP1 görüldü)": "TP1'e ulaştı (yarısı satıldı, stop girişe)",
             "iptal": "süresi doldu (giriş olmadı)", "bekliyor": "kırılım teyidi; ertesi gün açılışta alış"}
    lines = []
    for c in (out.get("gunluk") or {}).get("degisenler", []):
        if not keep(c):
            continue
        tur = "gerçek" if c.get("kaynak") == "gercek" else "sanal"
        yeni = c.get("yeni")
        what = f"kapandı — {c.get('sonuc') or '?'}" if yeni == "kapandı" else names.get(yeni, yeni)
        net = f" · net %{c['net_%']:+.2f}" if c.get("net_%") is not None and yeni == "kapandı" else ""
        lines.append(f"• #{c['id']} {c['hisse']} ({tur}): {what}{net}")
    return lines


def session_message(kind: str, out: Dict, data: Dict, watch=None) -> str:
    """watch: takip listesi (2026-11-09 kullanıcı isteği: Telegram yalnız takip edilen hisseler için). Verilirse
    öneriler ve sanal işlemler takip listesine daraltılır; GERÇEK işlemleriniz her zaman yazılır."""
    when = (out.get("zaman") or {}).get("zaman", "")
    head = {"sabah": "🌅 Halley sabah analizi", "aksam": "🌙 Halley akşam analizi"}[kind]
    t = f"{head} — {when[8:10]}.{when[5:7]} {when[11:16]}\n"
    warn = (out.get("zaman") or {}).get("uyari")
    if warn:
        t += f"⚠️ {warn}\n"
    if kind == "aksam":
        ms = data.get("piyasa") or {}
        if ms.get("xu100") is not None:
            t += f"BIST 100: {_n(ms.get('xu100'))} ({_n(ms.get('xu100_%'), '{:+.2f}')}%)\n"
    rec = data.get("onerilen") or []
    others = 0
    if watch is not None:
        others = len([r for r in rec if r["ticker"] not in watch])
        rec = [r for r in rec if r["ticker"] in watch]
        t += (f"\n📈 Takip listenizde önerilen senaryolar ({len(rec)}):\n" if rec else
              "\n📈 Takip listenizde bugün uygun giriş senaryosu yok.\n")
    else:
        t += f"\n📈 Önerilen senaryolar ({len(rec)}):\n" if rec else "\n📈 Bugün uygun giriş senaryosu yok.\n"
    for r in rec[:10]:
        t += (f"• {r['ticker']} — {r.get('senaryo') or '?'} · giriş {_n(r.get('giris'))} · SL {_n(r.get('sl'))} · "
              f"TP1 {_n(r.get('tp1'))} · TP2 {_n(r.get('tp2'))} · risk {r.get('risk_seviyesi') or '—'}\n")
    if len(rec) > 10:
        t += f"  … ve {len(rec) - 10} tane daha (panelde)\n"
    if others:
        t += f"ℹ️ Takip listeniz dışında {others} hissede daha önerilen senaryo var (panelde).\n"
    if kind == "sabah":
        news_watch = [r for r in data.get("takip") or [] if watch is None or r["ticker"] in watch]
        if news_watch:
            t += f"👀 Haberi olan, henüz önerilmeyen: {', '.join(r['ticker'] for r in news_watch[:12])}\n"
        for r in data.get("riskli") or []:
            if watch is not None and r["hisse"] not in watch and r.get("tur") != "Gerçek":
                continue
            d = r.get("stop_uzaklik_%")
            t += (f"⚠️ #{r['no']} {r['hisse']}: stopa yalnız %{d:.1f} kaldı\n" if d is not None and d >= 0 else
                  f"⚠️ #{r['no']} {r['hisse']}: son kapanış stopun altında — Midas'ta kontrol edin\n")
    ch = _changes(out, (lambda c: True) if watch is None else
                  (lambda c: c.get("hisse") in watch or c.get("kaynak") == "gercek"))
    if ch:
        t += "\n📒 İşlem günlüğü:\n" + "\n".join(ch) + "\n"
    if kind == "aksam":
        m = (data.get("metrikler") or {}).get("otomatik") or {}
        if m.get("kapanan"):
            t += (f"\nSanal toplam: {m['kapanan']} kapanan, kazanma %{m.get('kazanma_orani_%')}"
                  + ("" if m.get("yeterli_ornek") else " (örnek az, güvenilir değil)") + "\n")
        miss = ((data.get("kacirilan") or {}).get("ham") or {}).get("liste") or []
        if miss:
            t += f"🔎 Kaçırılan fırsat: {len(miss)} hisse (ayrıntı raporda)\n"
    if out.get("rapor"):
        t += f"\n📋 Rapor: {out['rapor']}"
    return t + FOOT
