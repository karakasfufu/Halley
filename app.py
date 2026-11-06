"""Halley — BIST haber paneli. Başlatmak için: baslat.bat (çift tıkla).

Sade düzen (2026-11-06): tek "Haberleri güncelle" düğmesi, 3 özet kutusu, olumlu/olumsuz hisse listeleri.
Ayarlar katlanır bölümde; durum ve geçmiş veri pilotu "Gelişmiş" sekmesinde.
"""
from datetime import datetime
from html import escape as esc

import pandas as pd
import streamlit as st

from bist_haber import config, db, pipeline, report

st.set_page_config(page_title="Halley", page_icon="📡", layout="wide", initial_sidebar_state="collapsed")

st.markdown("""
<style>
.block-container {padding-top: 3.5rem; max-width: 1100px;}
div[data-testid="stMetric"] {background: #fff; border: 1px solid #E5E7EB; border-radius: 12px; padding: 12px 16px;}
.news-card {background:#fff; border:1px solid #E5E7EB; border-radius:12px; padding:12px 16px; margin-bottom:8px;}
.news-meta {color:#6B7280; font-size:0.82rem;}
.chip {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.78rem; font-weight:600; margin-right:6px;}
.warn {background:#FEF3C7; color:#92400E;} .pos {background:#DCFCE7; color:#166534;}
.neg {background:#FEE2E2; color:#991B1B;} .neu {background:#F3F4F6; color:#374151;}
.disclaimer {color:#6B7280; font-size:0.8rem; margin-top:2rem;}
</style>
""", unsafe_allow_html=True)

conn = db.connect()
uni = pipeline.universe(conn)

WARN_FLAGS = ("çelişkili", "etki belirsiz", "tek görüş", "yorumsuz")
FLAG_TR = {"teyitli": "✅ İki analiz aynı sonuca vardı", "çelişkili": "⚠️ Analizler çelişti, haberi okuyun",
           "etki belirsiz": "⚠️ Etki büyüklüğü belirsiz", "tek görüş": "⚠️ Tek analiz gördü",
           "yorumsuz": "⚠️ Yapay zekâ yorum yapmadı, haberi okuyun"}
DIR_TR = {1: ("pos", "Olumlu"), -1: ("neg", "Olumsuz"), 0: ("neu", "Nötr")}
EVENT_TR = {
    "finansal_sonuc": "Finansal sonuç", "temettu": "Temettü", "bedelli_sermaye_artirimi": "Bedelli sermaye artırımı",
    "bedelsiz_sermaye_artirimi": "Bedelsiz sermaye artırımı", "pay_geri_alim": "Pay geri alımı",
    "yeni_is_sozlesme_ihale": "Yeni iş / ihale", "yatirim_kapasite": "Yatırım", "birlesme_satin_alma": "Birleşme / satın alma",
    "ortaklik_yapisi_degisikligi": "Ortaklık yapısı", "iceriden_pay_alim_satim": "Yönetici/ortak alım-satımı",
    "yonetim_degisikligi": "Yönetim değişikliği", "hukuki_ceza_sorusturma": "Hukuki / ceza",
    "kredi_derecelendirme": "Derecelendirme", "borclanma_finansman": "Finansman", "sektorel_makro": "Sektörel / makro",
    "diger": "Diğer",
}
PERSIST_TR = {"kisa": "birkaç gün", "orta": "birkaç hafta", "uzun": "aylar"}


def impact_word(magnitude: int) -> str:
    return "yüksek" if magnitude >= 4 else ("orta" if magnitude == 3 else "düşük")


def check_badge(flags: str) -> str:
    fl = [f.strip() for f in (flags or "").split(",") if f.strip()]
    if any(f in WARN_FLAGS for f in fl):
        return "⚠️ Kontrol et"
    return "✅ Teyitli" if "teyitli" in fl else ""


def last_update_text() -> str:
    if "last_update" in st.session_state:
        return st.session_state["last_update"]
    row = conn.execute("SELECT MAX(created_at) FROM analyses").fetchone()[0]
    if not row:
        return "—"
    stamp = datetime.fromisoformat(row).astimezone(config.TR_TZ)
    today = datetime.now(config.TR_TZ).date()
    return stamp.strftime("%H:%M") if stamp.date() == today else stamp.strftime("%d.%m %H:%M")


# ---------------- Başlık ve ana düğme ----------------
h1, h2 = st.columns([3, 1])
h1.markdown("## 📡 Halley")
h1.caption("Bugün haberi çıkan hisseler · KAP ve ekonomi haberleri yapay zekâ ile okunur")

if not pipeline.has_api_key():
    st.warning("Başlamak için OpenAI API anahtarınızı bir kez girin. Anahtar yalnızca bu bilgisayarda saklanır.")
    k1, k2 = st.columns([3, 1])
    key = k1.text_input("OpenAI API anahtarı", type="password", placeholder="sk-...", label_visibility="collapsed")
    if k2.button("Anahtarı kaydet", use_container_width=True) and key.strip():
        pipeline.save_api_key(key)
        conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
        st.rerun()

with st.expander("⚙️ Ayarlar"):
    s1, s2, s3 = st.columns(3)
    days = s1.select_slider("KAP: kaç günlük bildirim taransın?", options=[1, 2, 3, 5, 7], value=1)
    analysis_limit = s2.selectbox("Bir güncellemede en fazla kaç haber analiz edilsin?", [1, 3, 5, 10], index=3,
                                  help="KAP ve haber siteleri birlikte bu adede dahildir. Kalanlar sonraki güncellemeyi "
                                       "bekler. Bu bir adet sınırıdır, para tavanı değildir.", key="live_analysis_limit")
    window = s3.slider("Son kaç günün haberleri listeye katılsın?", 3, 30, 7)
    st.caption("Kaynaklar: KAP + " + ", ".join(config.RSS_SOURCE_LABELS.get(n, n) for n in config.RSS_FEEDS)
               + ". KAP hızlı isteklere sınır koyduğu için ilk güncelleme birkaç dakika sürebilir.")

if h2.button("🔄 Haberleri güncelle", type="primary", use_container_width=True):
    bar = st.progress(0.0, text="Başlıyor...")
    try:
        res = pipeline.update_all(conn, days=days, analysis_limit=analysis_limit,
                                  progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
        st.session_state["last_update"] = datetime.now(config.TR_TZ).strftime("%H:%M")
        st.session_state["last_result"] = res
    except Exception as e:
        st.error(f"Güncelleme tamamlanamadı: {e}")
    conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
    st.rerun()

if h2.button("🧪 Ücretsiz dene", use_container_width=True, key="free_check",
             help="Haberleri ve fiyatları toplar ama yapay zekâyı çağırmaz; OpenAI kredisi harcanmaz. "
                  "Bir sonraki gerçek güncellemenin yaklaşık maliyetini gösterir."):
    bar = st.progress(0.0, text="Başlıyor (yapay zekâ kullanılmayacak)...")
    try:
        res = pipeline.free_check(conn, days=days, analysis_limit=analysis_limit,
                                  progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
        st.session_state["last_result"] = res
    except Exception as e:
        st.error(f"Ücretsiz deneme tamamlanamadı: {e}")
    conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
    st.rerun()

last = st.session_state.get("last_result", {})
if last.get("free"):
    est = last.get("estimate", {})
    new_kap = last.get("kap", {}).get("new", 0)
    new_rss = last.get("rss", {}).get("new", 0)
    st.info(f"🧪 Ücretsiz deneme tamamlandı — yapay zekâ çağrılmadı, kredi harcanmadı. "
            f"KAP'ta {new_kap}, haber sitelerinde {new_rss} yeni kayıt bulundu. "
            f"Sırada {est.get('waiting', 0)} haber var; bir sonraki **Haberleri güncelle** bunların "
            f"{est.get('next_count', 0)} tanesini analiz eder (tahmini maliyet "
            f"{est.get('low_usd', 0):.3f}–{est.get('high_usd', 0):.3f} $).")
if last:
    if last.get("kap", {}).get("rate_limited"):
        st.warning("KAP geçici olarak istek sınırı uyguladı; kalan bildirimler bir sonraki güncellemede okunacak.")
    an = last.get("analyze", {})
    if an.get("errors"):
        st.error(f"{an['errors']} haber analiz edilemedi. Ayrıntı: Gelişmiş sekmesi.")
    if an.get("waiting"):
        st.caption(f"{an['waiting']} haber bir sonraki güncellemeyi bekliyor.")
    if last.get("rss", {}).get("failed_feeds"):
        st.caption("Bazı haber siteleri okunamadı. Ayrıntı: Gelişmiş sekmesi.")

# ---------------- Özet ----------------
rows = report.build(conn, uni, days=window)
positives = [r for r in rows if r["score"] >= 1.5]
negatives = [r for r in rows if r["score"] <= -1.5]
neutrals = [r for r in rows if -1.5 < r["score"] < 1.5]
m1, m2, m3 = st.columns(3)
m1.metric("Olumlu haber", f"{len(positives)} hisse")
m2.metric("Olumsuz haber", f"{len(negatives)} hisse")
m3.metric("Son güncelleme", last_update_text())

tab_list, tab_news, tab_adv = st.tabs(["📈 Bugünün listesi", "📰 Haberler", "🔧 Gelişmiş"])


def stock_details(r: dict) -> None:
    """Bir hisseye tıklanınca açılan ayrıntı: skor, fiyat değişimi ve haberler."""
    pct = lambda v: "—" if v is None else f"{v:+.1f}%"
    st.caption(f"Skor {r['score']:+.2f} · son 1 gün {pct(r['chg_1d'])} · son 5 gün {pct(r['chg_5d'])} · "
               f"{r['news_count']} haber. Emir vermeden önce haberin kendisini okuyun.")
    for i in conn.execute("SELECT i.*, n.title, n.url, n.source, n.note FROM impacts i JOIN news n ON n.id=i.news_id "
                          "WHERE i.ticker=? ORDER BY i.published_at DESC LIMIT 5", (r["ticker"],)):
        cls, word = DIR_TR[i["direction"]]
        flag = (f"<span class='chip {'pos' if i['flag'] == 'teyitli' else 'warn'}'>{esc(FLAG_TR.get(i['flag'], i['flag']))}</span>"
                if i["flag"] else "")
        source = esc(config.RSS_SOURCE_LABELS.get(i["source"].replace("rss:", ""), i["source"].upper()))
        st.markdown(
            f"<div class='news-card'><div class='news-meta'>{i['published_at'][:16].replace('T', ' ')} · {source}</div>"
            f"<span class='chip {cls}'>{word} · etki {impact_word(i['magnitude'])}</span>{flag}"
            f"<div style='margin-top:6px'><b>{esc(i['title'])}</b></div>"
            f"<div>{esc(i['note'] or '')}</div>"
            f"<div class='news-meta' style='margin-top:6px'>Neden: {esc(i['reason'] or '-')}</div>"
            f"<div class='news-meta'>{esc(EVENT_TR.get(i['event_type'], i['event_type']))} · güven %{i['confidence'] * 100:.0f}"
            f" · etkisi {PERSIST_TR.get(i['persistence'], i['persistence'])} sürebilir · "
            f"<a href='{esc(i['url'])}' target='_blank'>haberin kaynağını aç</a></div></div>",
            unsafe_allow_html=True)


def stock_list(items: list, empty_text: str) -> None:
    if not items:
        st.caption(empty_text)
        return
    for r in items:
        reason = (r["last_news"] or "").strip()
        reason = reason if len(reason) <= 90 else reason[:88].rstrip() + "…"
        badge = check_badge(r.get("flags", ""))
        with st.expander(f"**{r['ticker']}** · {reason}   {badge}"):
            st.markdown(f"**{esc(r['name'])}**")
            stock_details(r)


# ---------------- Bugünün listesi ----------------
with tab_list:
    if not rows:
        st.info("Henüz liste yok. Yukarıdaki **Haberleri güncelle** düğmesine basın.")
    else:
        st.markdown("#### 🟢 Olumlu haber alanlar")
        stock_list(positives, "Bu dönemde olumlu haber alan hisse yok.")
        st.markdown("#### 🔴 Olumsuz haber alanlar")
        stock_list(negatives, "Bu dönemde olumsuz haber alan hisse yok.")
        if neutrals and st.toggle(f"Etkisi zayıf/nötr haberleri de göster ({len(neutrals)} hisse)", key="show_neutral"):
            st.markdown("#### ⚪ İzlenecekler")
            stock_list(neutrals, "")
        st.caption("Bir hisseye tıklayınca haberin özeti, nedeni ve kaynağı açılır. "
                   "✅ Teyitli: iki ayrı analiz aynı sonuca vardı · ⚠️ Kontrol et: analizler çelişti ya da emin değil.")
        if st.session_state.get("signals_export_ready"):
            frame = pd.DataFrame(rows)
            frame["kontrol"] = frame["flags"].map(check_badge).str.replace("✅ ", "").str.replace("⚠️ ", "")
            frame = frame[["ticker", "name", "signal", "kontrol", "score", "news_count", "chg_1d", "chg_5d", "last_news"]]
            frame.columns = ["Hisse", "Şirket", "Sinyal", "Kontrol", "Skor", "Haber sayısı",
                             "Son 1 gün %", "Son 5 gün %", "Son haber özeti"]
            frame = frame.round({"Skor": 2, "Son 1 gün %": 1, "Son 5 gün %": 1})
            st.download_button("⬇️ Listeyi indir (Excel uyumlu CSV)", frame.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"halley_liste_{datetime.now(config.TR_TZ).date()}.csv", mime="text/csv",
                               key="signals_download")
        elif st.button("⬇️ Listeyi indirmeye hazırla", key="signals_export_prepare"):
            # Dosya yalnızca istenince hazırlanır (indirme yöneticileri hazır dosyayı kendiliğinden indirebiliyor).
            st.session_state["signals_export_ready"] = True
            conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
            st.rerun()

# ---------------- Haberler ----------------
with tab_news:
    news = conn.execute(
        "SELECT n.*, GROUP_CONCAT(i.ticker || ':' || i.direction) AS imp FROM news n "
        "LEFT JOIN impacts i ON i.news_id=n.id WHERE n.status='analyzed' "
        "GROUP BY n.id ORDER BY n.published_at DESC LIMIT 50").fetchall()
    if not news:
        st.info("Analiz edilmiş haber yok.")
    for n in news:
        chips = ""
        for part in (n["imp"] or "").split(","):
            if ":" in part:
                tk, d = part.split(":")
                chips += f"<span class='chip {DIR_TR[int(d)][0]}'>{esc(tk)}</span>"
        source = esc(config.RSS_SOURCE_LABELS.get(n["source"].replace("rss:", ""), n["source"].upper()))
        st.markdown(
            f"<div class='news-card'><div class='news-meta'>{n['published_at'][:16].replace('T', ' ')} · {source}</div>"
            f"{chips}<div style='margin-top:6px'><b>{esc(n['title'])}</b></div><div>{esc(n['note'] or '')}</div>"
            f"<div class='news-meta' style='margin-top:6px'><a href='{esc(n['url'])}' target='_blank'>haberin kaynağını aç</a>"
            f"</div></div>", unsafe_allow_html=True)

# ---------------- Gelişmiş ----------------
with tab_adv:
    st.markdown("#### Durum")
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM news GROUP BY status").fetchall())
    labels = {"new": "Analiz bekliyor", "analyzed": "Analiz edildi", "filtered_out": "Önemsiz bulundu (ön eleme)",
              "skipped": "Atlandı (rutin/ilgisiz/eski)", "error": "Hata"}
    legacy_empty = conn.execute("SELECT COUNT(*) FROM news WHERE source='kap' AND status='analyzed' "
                                "AND LENGTH(TRIM(COALESCE(body,''), char(9)||char(10)||char(13)||' '))=0").fetchone()[0]
    if legacy_empty:
        st.warning(f"Önceki sürümden {legacy_empty} KAP analizinin tam metni yok; bu kayıtlar listeye katılmıyor.")
    a1, a2 = st.columns(2)
    with a1:
        st.dataframe(pd.DataFrame([{"Durum": labels.get(k, k), "Adet": v} for k, v in counts.items()]),
                     hide_index=True, use_container_width=True)
    tok = conn.execute("SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM analyses").fetchone()
    a2.markdown(f"**OpenAI kullanımı:** girdi {tok[0]:,} · çıktı {tok[1]:,} token  \n"
                f"Model: `{config.MODEL_ANALYSIS}` · Tutarı OpenAI hesabınızdan takip edin.  \n"
                f"Takip edilen hisse: {len(uni)}")
    sources = last.get("rss", {}).get("sources", {}) if last else {}
    if sources:
        st.markdown("**Son taramada haber kaynakları**")
        state_labels = {"ok": "Okundu", "empty": "Akış boş", "error": "Okunamadı"}
        st.dataframe(pd.DataFrame([{"Kaynak": config.RSS_SOURCE_LABELS.get(name, name),
                                   "Durum": state_labels.get(s["state"], s["state"]),
                                   "Görülen": s["seen"], "Yeni": s["new"], "Tarih eksiği": s["undated"],
                                   "Açıklama": s["error"]} for name, s in sources.items()]),
                     hide_index=True, use_container_width=True)
    if last:
        with st.expander("Son güncellemenin teknik ayrıntıları"):
            st.json(last)

conn.close()

with tab_adv:
    st.divider()
    st.markdown("### 🧪 Geçmiş veri pilotu")
    from bist_haber.backtest_ui import render as render_backtest
    render_backtest()

st.markdown("<div class='disclaimer'>Halley haberleri otomatik olarak özetler ve puanlar; yatırım tavsiyesi değildir. "
            "Puan eşikleri henüz geçmiş veriyle ayarlanmadı. Karar ve emir sorumluluğu kullanıcıdadır.</div>",
            unsafe_allow_html=True)
