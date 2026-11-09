"""Takip Listem ve bekçi ekranları (2026-11-09). Arayüz yalnız gösterir/ayar yazar; takip işini arka plandaki bekçi
(tracker.tick, okuyucu süreci) yapar. Aşama 3'te ayrı sayfalara taşınacak; işlevler bu yüzden ayrı dosyada."""
from datetime import datetime

import pandas as pd
import streamlit as st

from . import config, notify, pipeline, tracker

STATE_TR = {"bekliyor": "⏳ giriş bekleniyor", "açık": "🟢 açık", "açık (TP1 görüldü)": "🟢 açık (TP1 görüldü)",
            "kapandı": "🏁 kapandı", "iptal": "⌛ süresi doldu", "geçersiz": "⛔ geçersiz"}


def _flash(kind: str, text: str) -> None:
    st.session_state.setdefault("_flash", []).append((kind, text))


def _rerun(conn) -> None:
    """Sayfayı yenilemeden önce bağlantıyı bırak (panelin diğer düğmeleriyle aynı; açık kalırsa dosya kilitli kalır)."""
    conn.close()
    st.rerun()


def follow_button(conn, ticker: str, key: str) -> None:
    """Hisse kartı ve analiz ekranı için "+ Takibe Al" / "Takipte" düğmesi."""
    if tracker.is_watched(conn, ticker):
        if st.button(f"⭐ {ticker} takipte — takipten çıkar", key=f"unf_{key}",
                     help="Yeni bildirimler durur; senaryolar ve olay geçmişi silinmez."):
            tracker.remove(conn, ticker)
            _flash("info", f"{ticker} takipten çıkarıldı (geçmiş kayıtları duruyor).")
            _rerun(conn)
    elif st.button(f"+ Takibe Al ({ticker})", key=f"fol_{key}", type="primary",
                   help="Senaryoları bekçiye kaydedilir; bekçi koşulları kendisi izler ve Telegram'dan bildirir."):
        _add(conn, ticker)


def _add(conn, ticker: str) -> None:
    try:
        res = tracker.add(conn, ticker)
    except ValueError as e:
        _flash("error", str(e))
        _rerun(conn)
    if res.get("uyari"):
        _flash("warning", f"{ticker}: " + res["uyari"])
    if res["yeni"]:
        _flash("success", f"⭐ {ticker} takibe alındı; {len(res['yeni'])} senaryo bekçiye kaydedildi: "
               + ", ".join(tracker.NAMES.get(s["senaryo"], s["senaryo"]) for s in res["yeni"]) + ".")
    else:
        _flash("warning", f"⭐ {ticker} takibe alındı ama şu an kaydedilecek senaryo yok: {res.get('neden', '')} "
               "Bekçi her kapanıştan sonra yeniden hesaplar; senaryo oluşunca bildirir.")
    _rerun(conn)


def watcher_status(conn) -> None:
    st_ = tracker.load_state()
    now = datetime.now(config.TR_TZ)
    beat = st_.get("nabiz")
    age = (now - datetime.fromisoformat(beat)).total_seconds() / 60 if beat else None
    if age is None:
        st.warning("🛡️ Bekçi henüz çalışmadı. Halley açıkken arka planda kendiliğinden başlar (birkaç dakika içinde).")
    elif age > 10:
        st.error(f"🛡️ Bekçi {age:.0f} dakikadır çalışmıyor. Halley'i kapatıp yeniden açın; Halley kapalıyken takip "
                 "yapılmaz.")
    else:
        st.success(f"🛡️ Bekçi çalışıyor (son kontrol {beat[11:16]}).")
    bits = []
    if st_.get("kapanis_gunu"):
        k = st_.get("kapanis_sonuc") or {}
        bits.append(f"son kapanış kontrolü {st_['kapanis_gunu']} ({k.get('hisse', 0)} hisse, {k.get('olay', 0)} olay)")
    if st_.get("gunici_son"):
        bits.append(f"son gün içi kontrol {st_['gunici_son'][11:16]}")
    for part in ("kapanis_sonuc", "gunici_sonuc"):
        miss = (st_.get(part) or {}).get("veri_yok") or []
        if miss:
            bits.append(f"veri gelmeyen (olay üretilmedi): {', '.join(miss)}")
    if bits:
        st.caption(" · ".join(bits))
    if st_.get("hata"):
        st.warning(f"Bekçinin son hatası ({st_.get('hata_zaman', '')[:16].replace('T', ' ')}): {st_['hata']}")
    tg = notify.configured() and pipeline.load_settings().get("takip_bildirim", True)
    st.caption(("📨 Telegram bildirimleri açık." if tg else
                "📨 Telegram kapalı ya da ayarlanmamış: olaylar yalnız burada kaydedilir (⚙️ Ayarlar → Telegram).")
               + " Gün içi kontroller ~5 dakikada bir, Yahoo verisi ~15 dakika gecikmelidir; günlük kapanış "
                 "gerektiren koşullar kapanıştan 20 dakika sonra teyit edilir.")


def render(conn) -> None:
    st.caption("Bot bütün BIST'i taramaya devam eder; Telegram'a yalnız takibe aldığınız hisselerin olayları gider. "
               "Takibe alınan hissenin her uygun senaryosu ayrı izlenir. Emir verilmez.")
    watcher_status(conn)
    names = {r["ticker"]: r["name"] for r in conn.execute("SELECT ticker, name FROM companies ORDER BY ticker")}
    c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
    pick = c1.selectbox("Hisse ekle", [""] + [t for t in names if not tracker.is_watched(conn, t)], key="tk_add_pick",
                        format_func=lambda t: f"{t} — {names[t]}" if t else "Hisse seçin…")
    if c2.button("+ Takibe Al", key="tk_add_btn", type="primary", disabled=not pick, width="stretch"):
        _add(conn, pick)
    items = tracker.watched(conn)
    if not items:
        st.info("Takip listeniz boş. Bir hisse seçip **+ Takibe Al** deyin ya da hisse kartlarındaki düğmeyi kullanın.")
    for w in items:
        tk = w["ticker"]
        act = tracker.scenarios(conn, tk, active_only=True)
        with st.container(border=True, key=f"tk_card_{tk}"):
            h1, h2 = st.columns([4, 1], vertical_alignment="center")
            h1.markdown(f"**⭐ {tk}** · {names.get(tk, '')} · {len(act)} etkin senaryo"
                        + (f" · trend {w['son_trend'].lower()}" if w.get("son_trend") else ""))
            if h2.button("Takipten çıkar", key=f"tk_rm_{tk}", width="stretch"):
                tracker.remove(conn, tk)
                _flash("info", f"{tk} takipten çıkarıldı (geçmiş kayıtları duruyor).")
                _rerun(conn)
            for s in act:
                cols = st.columns([3, 5, 2], vertical_alignment="center")
                cols[0].markdown(f"**{tracker.NAMES.get(s['senaryo'], s['senaryo'])}** #{s['id']}  \n"
                                 f"{STATE_TR.get(s['durum'], s['durum'])}")
                cols[1].caption((f"alarm {s['alarm']:.2f} · " if s.get("alarm") else "")
                                + f"giriş {s['giris']:.2f} · SL {s['sl']:.2f} · TP1 {s['tp1']:.2f} · TP2 {s['tp2']:.2f}"
                                f" · {s['gecerlilik']} işlem günü geçerli · hesap günü {s['signal_day']}")
                on = cols[2].toggle("Bildirim", value=bool(s["bildirim"]), key=f"tk_sw_{s['id']}")
                if on != bool(s["bildirim"]):
                    tracker.set_scenario_alert(conn, s["id"], on)
            if not act:
                st.caption("Şu an etkin senaryo yok; bekçi her kapanıştan sonra yeniden hesaplar.")
            types = st.multiselect("Bu hisse için bildirim türleri", list(tracker.TYPES), default=w["bildirimler"],
                                   format_func=lambda k: tracker.TYPES[k], key=f"tk_types_{tk}")
            if sorted(types) != sorted(w["bildirimler"]):
                tracker.set_types(conn, tk, types)
            ev = tracker.events(conn, tk, 5)
            if ev:
                st.caption("Son olaylar: " + " · ".join(f"{e['zaman'][5:16].replace('T', ' ')} {e['mesaj']}"
                                                        for e in ev))
    st.markdown("#### 🛡️ Bekçi olayları")
    events_table(conn)
    st.markdown("#### 🏁 Takip senaryolarının sonuçları")
    perf = tracker.performance(conn)
    if perf:
        st.dataframe(pd.DataFrame(perf), hide_index=True, width="stretch")
        n = sum(p["Giriş olan"] for p in perf)
        if n < 30:
            st.caption(f"⚠️ Giriş olan yalnız {n} senaryo var: 30'dan azken oranlar güvenilir değildir.")
    else:
        st.caption("Henüz sonuçlanan takip senaryosu yok.")
    old = [w for w in tracker.watched(conn, active_only=False) if not w["aktif"]]
    if old:
        st.caption("Takipten çıkarılanlar (geçmişi saklı): " + ", ".join(w["ticker"] for w in old))


def events_table(conn, limit: int = 100) -> None:
    ev = tracker.events(conn, limit=limit)
    if not ev:
        st.caption("Henüz olay yok.")
        return
    sent = {1: "✅ gönderildi", -1: "— kapalı", 0: "⏳ bekliyor"}
    st.dataframe(pd.DataFrame([{
        "Zaman": e["zaman"][:16].replace("T", " "), "Hisse": e["ticker"], "Tür": tracker.TYPES.get(e["tur"], e["tur"]),
        "Olay": e["mesaj"], "Teyit": "kapanış" if e["kesin"] else "gün içi",
        "Telegram": sent.get(e["gonderildi"], "") + (f" ({e['hata']})" if e.get("hata") else "")} for e in ev]),
        hide_index=True, width="stretch")
