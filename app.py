"""BIST Haber Radarı — web arayüzü. Başlatmak için: baslat.bat (çift tıkla)."""
from datetime import datetime
from html import escape as esc

import pandas as pd
import streamlit as st

from bist_haber import config, db, pipeline, report

st.set_page_config(page_title="BIST Haber Radarı", page_icon="📡", layout="wide")

st.markdown("""
<style>
.block-container {padding-top: 2rem; max-width: 1400px;}
div[data-testid="stMetric"] {background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 14px 18px;}
.news-card {background:#fff; border:1px solid #E5E7EB; border-radius:12px; padding:14px 18px; margin-bottom:10px;}
.news-meta {color:#6B7280; font-size:0.82rem; margin-bottom:4px;}
.chip {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; margin-right:6px;}
.warn {background:#FEF3C7; color:#92400E;}
.pos {background:#DCFCE7; color:#166534;} .neg {background:#FEE2E2; color:#991B1B;} .neu {background:#F3F4F6; color:#374151;}
.disclaimer {color:#6B7280; font-size:0.8rem; margin-top:2rem;}
</style>
""", unsafe_allow_html=True)

conn = db.connect()
uni = pipeline.universe(conn)

SIGNAL_CHIP = {"GÜÇLÜ POZİTİF": "pos", "POZİTİF": "pos", "İZLE": "neu", "NEGATİF": "neg", "GÜÇLÜ NEGATİF": "neg"}
FLAG_TR = {"teyitli": "✅ iki analiz teyit etti", "çelişkili": "⚠️ analizler çelişti — elle okuyun",
           "etki belirsiz": "⚠️ etki büyüklüğü belirsiz", "tek görüş": "⚠️ tek analiz gördü",
           "yorumsuz": "⚠️ model yorum yapmadı — elle okuyun"}
WARN_FLAGS = ("çelişkili", "etki belirsiz", "tek görüş", "yorumsuz")


def _warn_text(flags: str) -> str:
    fl = [f.strip() for f in (flags or "").split(",") if f.strip()]
    if any(f in WARN_FLAGS for f in fl):
        return "⚠️ kontrol et"
    return "✅ teyitli" if "teyitli" in fl else ""


SIGNAL_ICON = {"GÜÇLÜ POZİTİF": "🟢🟢", "POZİTİF": "🟢", "İZLE": "⚪", "NEGATİF": "🔴", "GÜÇLÜ NEGATİF": "🔴🔴"}
DIR_CHIP = {1: ("pos", "Pozitif"), -1: ("neg", "Negatif"), 0: ("neu", "Nötr")}
EVENT_TR = {
    "finansal_sonuc": "Finansal sonuç", "temettu": "Temettü", "bedelli_sermaye_artirimi": "Bedelli SA",
    "bedelsiz_sermaye_artirimi": "Bedelsiz SA", "pay_geri_alim": "Geri alım", "yeni_is_sozlesme_ihale": "Yeni iş / ihale",
    "yatirim_kapasite": "Yatırım", "birlesme_satin_alma": "Birleşme / satın alma",
    "ortaklik_yapisi_degisikligi": "Ortaklık yapısı", "iceriden_pay_alim_satim": "İçeriden alım-satım",
    "yonetim_degisikligi": "Yönetim", "hukuki_ceza_sorusturma": "Hukuki / ceza", "kredi_derecelendirme": "Derecelendirme",
    "borclanma_finansman": "Finansman", "sektorel_makro": "Sektörel / makro", "diger": "Diğer",
}

# ---------------- Kenar çubuğu ----------------
with st.sidebar:
    st.markdown("## 📡 BIST Haber Radarı")
    st.caption("Haberleri yapay zekâ ile okuyup hisse bazında skorlar.")

    if not pipeline.has_api_key():
        st.warning("Yapay zekâ analizi için OpenAI API anahtarı gerekli.")
        key = st.text_input("OpenAI API anahtarı", type="password", placeholder="sk-...")
        if st.button("Anahtarı kaydet", use_container_width=True) and key.strip():
            pipeline.save_api_key(key)
            st.success("Kaydedildi.")
            st.rerun()
    else:
        st.success("OpenAI bağlantısı hazır", icon="✅")

    days = st.select_slider("KAP: kaç günlük bildirim taransın?", options=[1, 2, 3, 5, 7], value=1)
    analysis_limit = st.selectbox("Güncellemede en fazla kaç haber analiz edilsin?", [1, 3, 5, 10], index=3,
                                  help="KAP ve haber siteleri birlikte bu adede dahildir. Kalan haberler bekler; "
                                       "bu adet sınırıdır, parasal tavan değildir.", key="live_analysis_limit")
    st.caption("KAP + " + ", ".join(config.RSS_SOURCE_LABELS.get(n, n) for n in config.RSS_FEEDS))
    if st.button("🔄 Verileri güncelle", type="primary", use_container_width=True):
        bar = st.progress(0.0, text="Başlıyor...")
        try:
            res = pipeline.update_all(conn, days=days, analysis_limit=analysis_limit,
                                      progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
            st.session_state["last_update"] = datetime.now(config.TR_TZ).strftime("%H:%M")
            st.session_state["last_result"] = res
        except Exception as e:
            st.error(f"Güncelleme hatası: {e}")
        st.rerun()
    if "last_update" in st.session_state:
        st.caption(f"Son güncelleme: {st.session_state['last_update']}")
        kap_res = st.session_state.get("last_result", {}).get("kap", {})
        if kap_res.get("rate_limited"):
            st.warning(f"KAP geçici olarak istek sınırı uyguladı; {kap_res.get('bodies_pending', 0)} bildirimin "
                       "metni sonraki güncellemede okunacak. Birkaç dakika sonra tekrar deneyin.")
        an = st.session_state.get("last_result", {}).get("analyze", {})
        if an.get("waiting"):
            st.caption(f"{an['waiting']} haber sonraki analiz turunu bekliyor.")
        if st.session_state.get("last_result", {}).get("rss", {}).get("failed_feeds"):
            st.warning("Bazı haber kaynakları okunamadı. Kaynak ayrıntıları Durum sekmesinde.")
        if an.get("errors"):
            st.error(f"{an['errors']} haber analiz edilemedi (Durum sekmesine bakın).")
    st.caption("KAP sınırı yüzünden bildirim metinleri ~1 sn/bildirim hızında okunur; ilk güncelleme birkaç dakika sürebilir.")

    st.divider()
    window = st.slider("Sinyal penceresi (gün)", 3, 30, 7, help="Son kaç günün haberleri skora katılsın")

# ---------------- Üst özet ----------------
st.markdown("### Günün tablosu")
legacy_empty = conn.execute("SELECT COUNT(*) FROM news WHERE source='kap' AND status='analyzed' "
                            "AND LENGTH(TRIM(COALESCE(body,''), char(9)||char(10)||char(13)||' '))=0").fetchone()[0]
if legacy_empty:
    st.warning(f"Önceki sürümden {legacy_empty} KAP analizinin tam metni yok. "
               "Bu kayıtlar skora katılmıyor; eski analizler ayrıca gözden geçirilmeli.")
rows = report.build(conn, uni, days=window)
counts = dict(conn.execute("SELECT status, COUNT(*) FROM news GROUP BY status").fetchall())
waiting = conn.execute("SELECT COUNT(*) FROM news WHERE status='new'").fetchone()[0]
c1, c2, c3, c4 = st.columns(4)
c1.metric("Analiz edilen haber", counts.get("analyzed", 0))
c2.metric("Pozitif sinyal", sum(1 for r in rows if r["score"] >= 1.5))
c3.metric("Negatif sinyal", sum(1 for r in rows if r["score"] <= -1.5))
c4.metric("Analiz bekleyen", waiting)

tab_sig, tab_news, tab_state, tab_backtest = st.tabs(["📈 Sinyaller", "📰 Haber akışı", "⚙️ Durum", "🧪 Geçmiş veri pilotu"])

# ---------------- Sinyaller ----------------
with tab_sig:
    if not rows:
        st.info("Henüz sinyal yok. Soldan **Verileri güncelle**'ye basın.")
    else:
        f1, f2 = st.columns([2, 3])
        flt = f1.segmented_control("Göster", ["Tümü", "Pozitif", "Negatif"], default="Tümü")
        q = f2.text_input("Hisse ara", placeholder="ör. THYAO", label_visibility="collapsed")
        df = pd.DataFrame(rows)
        if flt == "Pozitif":
            df = df[df.score > 0]
        elif flt == "Negatif":
            df = df[df.score < 0]
        if q:
            df = df[df.ticker.str.contains(q.strip().upper()) | df.name.str.upper().str.contains(q.strip().upper())]
        df["warn"] = df["flags"].map(_warn_text)
        view = df[["ticker", "name", "signal", "score", "warn", "news_count", "chg_1d", "chg_5d", "last_news"]].copy()
        view["signal"] = view["signal"].map(lambda s: f"{SIGNAL_ICON.get(s, '')} {s}")
        view = view.reset_index(drop=True)

        def _color(v):
            if pd.isna(v) or v == 0:
                return "color:#6B7280"
            return "color:#15803D;font-weight:600" if v > 0 else "color:#B91C1C;font-weight:600"

        num = view[["score", "chg_1d", "chg_5d"]].astype(float)
        shown = view.copy()
        for c, fmt in (("score", "{:+.2f}"), ("chg_1d", "{:+.1f}"), ("chg_5d", "{:+.1f}")):
            shown[c] = num[c].map(lambda v, f=fmt: "–" if pd.isna(v) else f.format(v))
        styled = shown.style.apply(lambda col: [_color(v) for v in num[col.name]],
                                   subset=["score", "chg_1d", "chg_5d"])
        sel = st.dataframe(
            styled, hide_index=True, use_container_width=True, on_select="rerun", selection_mode="single-row",
            column_config={
                "ticker": st.column_config.TextColumn("Hisse", width="small"),
                "name": st.column_config.TextColumn("Şirket", width="medium"),
                "signal": st.column_config.TextColumn("Sinyal", width="medium"),
                "score": st.column_config.TextColumn("Skor", width="small"),
                "news_count": st.column_config.NumberColumn("Haber", width="small"),
                "chg_1d": st.column_config.TextColumn("1G %", width="small"),
                "chg_5d": st.column_config.TextColumn("5G %", width="small"),
                "warn": st.column_config.TextColumn("Kontrol", width="small",
                                                    help="✅ iki bağımsız analiz aynı sonuca vardı · ⚠️ analizler çelişti "
                                                         "ya da etki belirsiz, haberi elle okuyun"),
                "last_news": st.column_config.TextColumn("Son haber", width="large"),
            })
        st.download_button("⬇️ Listeyi indir (Excel uyumlu CSV)", view.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"sinyaller_{datetime.now(config.TR_TZ).date()}.csv", mime="text/csv")

        picked = sel.selection.rows if sel and sel.selection else []
        if picked:
            t = view.iloc[picked[0]]["ticker"]
            st.markdown(f"#### {t} · {uni.get(t, '')}")
            st.caption("Bu hisseyi etkileyen haberler (yeniden eskiye). Emir vermeden önce haberin kendisini okuyun.")
            for r in conn.execute(
                    "SELECT i.*, n.title, n.url, n.source, n.note FROM impacts i JOIN news n ON n.id=i.news_id "
                    "WHERE i.ticker=? ORDER BY i.published_at DESC LIMIT 20", (t,)):
                cls, lbl = DIR_CHIP[r["direction"]]
                st.markdown(
                    f"<div class='news-card'><div class='news-meta'>{r['published_at'][:16].replace('T', ' ')} · "
                    f"{esc(r['source'])} · işlem günü {r['effective_date']}</div>"
                    f"<span class='chip {cls}'>{lbl} · etki {r['magnitude']}/5</span>"
                    f"<span class='chip neu'>{EVENT_TR.get(r['event_type'], r['event_type'])}</span>"
                    f"<span class='chip neu'>güven {r['confidence']:.0%}</span>"
                    f"<span class='chip neu'>kalıcılık: {r['persistence']}</span>"
                    + (f"<span class='chip {'pos' if r['flag'] == 'teyitli' else 'warn'}'>"
                       f"{FLAG_TR.get(r['flag'], r['flag'])}</span>" if r["flag"] else "")
                    + ""
                    f"<div style='margin-top:8px'><b>{esc(r['title'])}</b></div>"
                    f"<div>{esc(r['note'] or '')}</div><div class='news-meta' style='margin-top:6px'>Gerekçe: {esc(r['reason'] or '-')}"
                    f" · <a href='{esc(r['url'])}' target='_blank'>kaynağı aç</a></div></div>",
                    unsafe_allow_html=True)
        else:
            st.caption("Ayrıntı için tablodan bir satır seçin.")

# ---------------- Haber akışı ----------------
with tab_news:
    news = conn.execute(
        "SELECT n.*, GROUP_CONCAT(i.ticker || ':' || i.direction) AS imp FROM news n "
        "LEFT JOIN impacts i ON i.news_id=n.id WHERE n.status='analyzed' "
        "GROUP BY n.id ORDER BY n.published_at DESC LIMIT 100").fetchall()
    if not news:
        st.info("Analiz edilmiş haber yok.")
    for n in news:
        chips = ""
        for part in (n["imp"] or "").split(","):
            if ":" in part:
                tk, d = part.split(":")
                chips += f"<span class='chip {DIR_CHIP[int(d)][0]}'>{tk}</span>"
        st.markdown(
            f"<div class='news-card'><div class='news-meta'>{n['published_at'][:16].replace('T', ' ')} · {esc(n['source'])}</div>"
            f"{chips}<div style='margin-top:6px'><b>{esc(n['title'])}</b></div><div>{esc(n['note'] or '')}</div>"
            f"<div class='news-meta' style='margin-top:6px'><a href='{esc(n['url'])}' target='_blank'>kaynağı aç</a></div></div>",
            unsafe_allow_html=True)

# ---------------- Durum ----------------
with tab_state:
    labels = {"new": "Analiz bekliyor", "analyzed": "Analiz edildi", "filtered_out": "Önemsiz bulundu (ön eleme)",
              "skipped": "Atlandı (ilgisiz/eski)", "error": "Hata"}
    st.markdown("**Haber durumu**")
    st.dataframe(pd.DataFrame([{"Durum": labels.get(k, k), "Adet": v} for k, v in counts.items()]),
                 hide_index=True, use_container_width=False)
    tok = conn.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses").fetchone()
    st.markdown(f"**OpenAI kullanımı:** girdi {tok[0]:,} token · çıktı {tok[1]:,} token "
                f"(modeller: `{config.MODEL_FILTER}` / `{config.MODEL_ANALYSIS}`). Tutarı OpenAI hesabınızdan takip edin.")
    st.markdown(f"**Takip edilen hisse sayısı:** {len(uni)} (listeyi daraltmak için `data/universe.txt`)")
    if "last_result" in st.session_state:
        sources = st.session_state["last_result"].get("rss", {}).get("sources", {})
        if sources:
            st.markdown("**Son taramada haber kaynakları**")
            state_labels = {"ok": "Okundu", "empty": "Akış boş", "error": "Okunamadı"}
            st.dataframe(pd.DataFrame([{"Kaynak": config.RSS_SOURCE_LABELS.get(name, name),
                                       "Durum": state_labels.get(s["state"], s["state"]),
                                       "Görülen": s["seen"], "Yeni kayıt": s["new"],
                                       "Tarih eksiği": s["undated"], "İleri tarihli": s["future_dated"],
                                       "Açıklama": s["error"]} for name, s in sources.items()]),
                         hide_index=True, use_container_width=True)
        with st.expander("Son güncellemenin ayrıntıları"):
            st.json(st.session_state["last_result"])

conn.close()

with tab_backtest:
    from bist_haber.backtest_ui import render as render_backtest
    render_backtest()

st.markdown("<div class='disclaimer'>Bu araç haberleri otomatik olarak özetler ve skorlar; yatırım tavsiyesi değildir. "
            "Skor eşikleri henüz geçmiş veriyle kalibre edilmedi. Karar ve emir sorumluluğu kullanıcıdadır.</div>",
            unsafe_allow_html=True)

