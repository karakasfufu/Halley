"""Halley — BIST haber paneli. Başlatmak için: baslat.bat (çift tıkla).

Sade düzen (2026-11-06): tek "Haberleri güncelle" düğmesi, 3 özet kutusu, olumlu/olumsuz hisse listeleri.
Ayarlar katlanır bölümde; durum ve geçmiş veri pilotu "Gelişmiş" sekmesinde.
"""
import json
import os
import re
import time
from datetime import date, datetime, timedelta
from html import escape as esc

import pandas as pd
import streamlit as st

from bist_haber import (analyzer, calendar_sync, config, corp_events, db, earnings, entries, journal, kap_history,
                        kap_worker, macro_calendar, pipeline, report, signals, technical, timeline, tradeplan,
                        trends, watchdog, ai_comment, sectors)

st.set_page_config(page_title="Halley", page_icon="☄️", layout="wide", initial_sidebar_state="collapsed")
_RENDER_T0 = time.time()   # sayfa çizim süresi (otomatik yenileme aralığı buna göre)

# Görünüm (2026-11-09 kullanıcı isteği: "dağınık, önemli bilgiler silik"): koyu ve okunur yazı, kart düzeni, renkli
# bölüm başlıkları. Yalnız sunum; hiçbir hesap değişmez.
st.markdown("""
<style>
:root {--h-ink:#0F172A; --h-sub:#1E293B; --h-muted:#334155; --h-line:#D5DBE8; --h-pos:#16A34A; --h-neg:#DC2626;
       --h-acc:#4F46E5; --h-amber:#D97706; --h-card:#FFFFFF;}
.stApp {background: radial-gradient(1100px 380px at 8% -8%, #E0E7FF 0%, rgba(224,231,255,0) 62%),
        radial-gradient(800px 300px at 100% -4%, #FEF3C7 0%, rgba(254,243,199,0) 58%), #F3F5FA;}
.block-container {padding-top: 3.4rem; max-width: 1180px;}
header[data-testid="stHeader"] {background: transparent;}
/* silik yazılar → okunur */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: var(--h-muted) !important;
  font-size: 0.9rem; line-height: 1.55; opacity: 1 !important;}
[data-testid="stWidgetLabel"] p {color: var(--h-ink); font-weight: 600;}
.stMarkdown p, .stMarkdown li {color: var(--h-sub);}
/* üst bant */
.hero {background: linear-gradient(118deg, #0F172A 0%, #1E1B4B 52%, #3730A3 100%); border-radius: 18px; margin-bottom: 18px;
  padding: 20px 26px 18px; position: relative; overflow: hidden; box-shadow: 0 14px 34px -16px rgba(30,27,75,.55);}
.hero::before {content: ""; position: absolute; right: 70px; top: 34px; width: 210px; height: 3px; transform: rotate(-16deg);
  background: linear-gradient(90deg, rgba(251,191,36,0), rgba(251,191,36,.85)); border-radius: 3px;}
.hero::after {content: ""; position: absolute; right: 52px; top: 12px; width: 18px; height: 18px; border-radius: 50%;
  background: #FDE68A; box-shadow: 0 0 22px 8px rgba(251,191,36,.55);}
.hero .t {color: #FFFFFF; font-size: 2.05rem; font-weight: 800; letter-spacing: -.02em; line-height: 1.1;}
.hero .s {color: #C7D2FE; font-size: .96rem; margin-top: 6px;}
.hero .pills {margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px;}
.hero .pill {background: rgba(255,255,255,.10); border: 1px solid rgba(255,255,255,.22); color: #F1F5F9;
  border-radius: 999px; padding: 3px 12px; font-size: .84rem;}
/* bilgi şeridi (piyasa durumu) */
.strip {background: var(--h-card); border: 1px solid var(--h-line); border-left: 5px solid var(--h-acc); border-radius: 12px;
  padding: 10px 16px; color: var(--h-sub); font-size: .93rem; line-height: 1.55; margin: 6px 0 12px;}
.strip.down {border-left-color: var(--h-neg);} .strip.up {border-left-color: var(--h-pos);}
.strip .lbl {font-weight: 800; color: var(--h-ink); margin-right: 6px;}
/* bölüm başlıkları */
.sec {display: flex; align-items: center; gap: 10px; font-size: 1.22rem; font-weight: 800; color: var(--h-ink);
  margin: 20px 0 10px; padding: 2px 0 2px 12px; border-left: 5px solid var(--h-acc);}
.sec.t-pos {border-left-color: var(--h-pos);} .sec.t-neg {border-left-color: var(--h-neg);} .sec.t-neu {border-left-color: #94A3B8;}
.sec .cnt {font-size: .8rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; background: #EEF2FF; color: #3730A3;}
.sec.t-pos .cnt {background: #DCFCE7; color: #166534;} .sec.t-neg .cnt {background: #FEE2E2; color: #991B1B;}
.sec .note {font-size: .86rem; font-weight: 500; color: var(--h-muted);}
.opt {font-weight: 700; color: var(--h-ink); margin: 8px 0 2px;} .opt span {font-weight: 500; color: var(--h-muted);}
/* kartlar */
.st-key-watch, .st-key-macro {background: var(--h-card); border-radius: 16px; box-shadow: 0 1px 3px rgba(15,23,42,.06);}
.st-key-macro {border: 1px solid var(--h-line); border-left: 5px solid var(--h-amber); padding: 12px 16px;}
div[data-testid="stMetric"] {background: var(--h-card); border: 1px solid var(--h-line); border-radius: 14px; padding: 12px 16px;
  box-shadow: 0 1px 3px rgba(15,23,42,.05);}
[data-testid="stMetricLabel"] p {color: var(--h-muted) !important; font-weight: 700; font-size: .88rem;}
[data-testid="stMetricValue"] {color: var(--h-ink); font-weight: 750;}
[data-testid="stMetricValue"] > div, [data-testid="stMetricDelta"] div {overflow: visible !important; text-overflow: clip !important;}
[data-testid="stMetricDelta"] div {white-space: normal !important;}
[data-testid="stExpander"] [data-testid="stMetricValue"] {font-size: 1.45rem;}
.st-key-kpi div[data-testid="stColumn"]:nth-of-type(1) div[data-testid="stMetric"] {border-top: 5px solid var(--h-pos);}
.st-key-kpi div[data-testid="stColumn"]:nth-of-type(2) div[data-testid="stMetric"] {border-top: 5px solid var(--h-neg);}
.st-key-kpi div[data-testid="stColumn"]:nth-of-type(3) div[data-testid="stMetric"] {border-top: 5px solid var(--h-acc);}
.st-key-kpi div[data-testid="stColumn"]:nth-of-type(1) [data-testid="stMetricValue"] {color: #15803D;}
.st-key-kpi div[data-testid="stColumn"]:nth-of-type(2) [data-testid="stMetricValue"] {color: #B91C1C;}
/* açılır kutular */
[data-testid="stExpander"] details {background: var(--h-card); border: 1px solid var(--h-line); border-radius: 14px;
  box-shadow: 0 1px 3px rgba(15,23,42,.05); transition: box-shadow .15s, border-color .15s;}
[data-testid="stExpander"] details:hover {border-color: #A5B4FC; box-shadow: 0 8px 20px -12px rgba(79,70,229,.5);}
[data-testid="stExpander"] summary p {color: var(--h-ink); font-size: .98rem;}
.st-key-list_pos [data-testid="stExpander"] details {border-left: 5px solid var(--h-pos);}
.st-key-list_neg [data-testid="stExpander"] details {border-left: 5px solid var(--h-neg);}
.st-key-list_neu [data-testid="stExpander"] details {border-left: 5px solid #94A3B8;}
/* sekmeler */
[data-baseweb="tab-list"] {gap: 6px; background: var(--h-card); padding: 6px; border-radius: 14px; border: 1px solid var(--h-line);
  box-shadow: 0 1px 3px rgba(15,23,42,.05); flex-wrap: wrap;}
button[data-baseweb="tab"] {border-radius: 10px; padding: 8px 14px; height: auto;}
button[data-baseweb="tab"] p {font-weight: 700; color: var(--h-muted); font-size: .95rem;}
button[data-baseweb="tab"]:hover {background: #EEF2FF;}
button[data-baseweb="tab"][aria-selected="true"] {background: linear-gradient(118deg, #4F46E5, #7C3AED);}
button[data-baseweb="tab"][aria-selected="true"] p {color: #FFFFFF;}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {display: none;}
/* düğmeler ve uyarılar */
.stButton button, .stDownloadButton button {font-weight: 700; border-radius: 10px;}
.stButton button[kind="primary"] {background: linear-gradient(118deg, #4F46E5, #7C3AED); border: none;
  box-shadow: 0 8px 18px -10px rgba(79,70,229,.8);}
[data-testid="stAlertContainer"] {border-radius: 12px;}
[data-testid="stAlertContainer"] p {font-weight: 500;}
/* fırsat özeti */
.opp {background: linear-gradient(135deg, #ECFDF5, #FFFFFF 70%); border: 1px solid #A7F3D0; border-radius: 16px;
  padding: 14px 18px; margin: 4px 0 8px;}
.opp .h {font-size: 1.05rem; font-weight: 800; color: #065F46;}
.opp .chips {display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 8px;}
.opp .tk {background: #FFFFFF; border: 1px solid var(--h-line); border-radius: 10px; padding: 5px 10px; font-size: .86rem;
  color: var(--h-sub); border-left: 4px solid #94A3B8;}
.opp .tk b {color: var(--h-ink); margin-right: 4px;}
.opp .tk.r-düşük {border-left-color: var(--h-pos);} .opp .tk.r-orta {border-left-color: var(--h-amber);}
.opp .tk.r-yüksek {border-left-color: var(--h-neg);}
.opp .f {font-size: .85rem; color: var(--h-muted);}
/* haber kartları */
.news-card {background: var(--h-card); border: 1px solid var(--h-line); border-radius: 12px; padding: 12px 16px; margin-bottom: 8px;}
.news-meta {color: var(--h-muted); font-size: 0.86rem;}
.chip {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.8rem; font-weight:700; margin-right:6px;}
.warn {background:#FEF3C7; color:#92400E;} .pos {background:#DCFCE7; color:#166534;}
.neg {background:#FEE2E2; color:#991B1B;} .neu {background:#E2E8F0; color:#1E293B;}
.disclaimer {color: var(--h-muted); font-size:0.84rem; margin-top:2rem; border-top: 1px solid var(--h-line); padding-top: 12px;}
</style>
""", unsafe_allow_html=True)

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def section_title(icon: str, text: str, tone: str = "", count=None, note: str = "") -> None:
    """Renkli bölüm başlığı (yalnız görünüm)."""
    st.markdown(f"<div class='sec {'t-' + tone if tone else ''}'><span>{icon}</span>{esc(text)}"
                + (f"<span class='cnt'>{count}</span>" if count is not None else "")
                + (f"<span class='note'>{esc(note)}</span>" if note else "") + "</div>", unsafe_allow_html=True)


def bold_html(text: str) -> str:
    """Metni güvenli hâle getirir; **kalın** işaretlerini <b> yapar."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", esc(text))

conn = db.connect()
try:
    uni = pipeline.universe(conn)
except Exception as e:  # ilk kurulumda şirket listesi KAP'tan indirilir; KAP geçici sınır uygularsa çökme
    st.error("Şirket listesi KAP'tan alınamadı (KAP geçici olarak istek sınırı uyguluyor olabilir). Birkaç dakika "
             f"sonra sayfayı yenileyin. Ayrıntı: {e}")
    conn.close()
    st.stop()

WARN_FLAGS = ("çelişkili", "etki belirsiz", "tek görüş", "yorumsuz")
FLAG_TR = {"teyitli": "✅ İki analiz aynı sonuca vardı", "çelişkili": "⚠️ Analizler çelişti, haberi okuyun",
           "etki belirsiz": "⚠️ Etki büyüklüğü belirsiz", "tek görüş": "⚠️ Tek analiz gördü",
           "yorumsuz": "⚠️ Yapay zekâ yorum yapmadı, haberi okuyun"}
DIR_TR = {1: ("pos", "Olumlu"), -1: ("neg", "Olumsuz"), 0: ("neu", "Nötr")}
from bist_haber.labels import EVENT_TR  # noqa: E402  (panel + gelişim takibi ortak)
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
def nice_err(e: Exception) -> str:
    """Teknik hata metnini sade Türkçeye çevirir (kullanıcı Python bilmiyor). Ayrıntı parantez içinde kısa kalır."""
    raw = str(e)
    m = re.search(r"host='([^']+)'", raw)
    host = m.group(1) if m else None
    net_words = ("Max retries", "ConnectionError", "NewConnectionError", "timed out", "Timeout", "Name or service",
                 "getaddrinfo", "ağ kapalı", "Failed to establish", "Connection aborted", "RemoteDisconnected")
    if host or any(w in raw for w in net_words) or isinstance(e, (ConnectionError, TimeoutError)):
        return (f"{host or 'İnternet'} adresine bağlanılamadı. İnternet bağlantınızı kontrol edip birkaç dakika sonra "
                "yeniden deneyin.")
    if "429" in raw or "Too Many" in raw:
        return "Site çok sık istek nedeniyle geçici olarak yanıt vermiyor; birkaç dakika sonra yeniden deneyin."
    if "database is locked" in raw:
        return "Veritabanı o an başka bir işlemde meşguldü; birkaç saniye sonra yeniden deneyin."
    return raw[:200]


def flash(kind: str, text: str) -> None:
    """Sayfa yenilenmeden (st.rerun) hemen önce yazılan mesaj kaybolmasın: bir sonraki çizimde gösterilir.
    2026-11-09 uçtan uca kontrolde bulundu: düğme hataları ve saat uyarıları kullanıcı göremeden siliniyordu."""
    st.session_state.setdefault("_flash", []).append((kind, text))


for _kind, _text in st.session_state.pop("_flash", []):
    {"error": st.error, "warning": st.warning, "success": st.success}.get(_kind, st.info)(_text)

h1, h2 = st.columns([3, 1], vertical_alignment="center")
_today = datetime.now(config.TR_TZ)
h1.markdown(
    "<div class='hero'><div class='t'>Halley</div>"
    "<div class='s'>Bugün haberi çıkan hisseler · KAP ve ekonomi haberleri yapay zekâ ile okunur</div>"
    f"<div class='pills'><span class='pill'>📅 {_today.day} {['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'][_today.month - 1]} "
    f"{_today.year}, {GUNLER[_today.weekday()]}</span><span class='pill'>🕒 Son güncelleme: {esc(last_update_text())}</span>"
    "<span class='pill'>🔒 Emir vermez · işlemi siz Midas'tan yaparsınız</span></div></div>",
    unsafe_allow_html=True)

if not pipeline.has_api_key():
    st.warning("Başlamak için OpenAI API anahtarınızı bir kez girin. Anahtar yalnızca bu bilgisayarda saklanır.")
    k1, k2 = st.columns([3, 1])
    key = k1.text_input("OpenAI API anahtarı", type="password", placeholder="sk-...", label_visibility="collapsed")
    if k2.button("Anahtarı kaydet", width="stretch") and key.strip():
        pipeline.save_api_key(key)
        conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
        st.rerun()

with st.expander("⚙️ Ayarlar"):
    s1, s2, s3 = st.columns(3)
    days = s1.select_slider("KAP: kaç günlük bildirim taransın?", options=[1, 2, 3, 5, 7], value=1)
    analysis_limit = s2.selectbox("Güncellemede / sabah analizinde en fazla kaç haber analiz edilsin?",
                                  [1, 3, 5, 10, 20, 30], index=3,
                                  help="KAP ve haber siteleri birlikte bu adede dahildir; öncelik sırası: açık işlemler, "
                                       f"likit hisseler… {config.AUTO_ANALYSIS_MAX_AGE_DAYS} günden eski haberler "
                                       "kendiliğinden analiz edilmez (📰 Haberler sekmesinden elle seçilebilir). Para "
                                       "tavanı ayrıca: haber analizi aylık bütçesi.", key="live_analysis_limit")
    window = s3.slider("Son kaç günün haberleri listeye katılsın?", 3, 30, 7)
    # Analiz kalitesi: kullanıcı seçer, seçim bu bilgisayarda saklanır (data/ayarlar.json).
    q_keys = list(config.QUALITY_PROFILES)
    saved_q = pipeline.load_settings().get("analiz_kalitesi", config.DEFAULT_QUALITY)
    quality = st.radio(
        "Analiz kalitesi", q_keys, index=q_keys.index(saved_q) if saved_q in q_keys else 0, horizontal=True,
        format_func=lambda k: f"{config.QUALITY_PROFILES[k]['etiket']} ({config.QUALITY_PROFILES[k]['maliyet']})",
        help="Yüksek doğruluk: model daha uzun düşünür, büyük kararlar ikinci kez kontrol edilir. "
             "Dengeli: orta düşünme, ikinci kontrol yalnız çok büyük kararlarda. Ekonomik: kısa düşünme, "
             "ikinci kontrol yok, daha kısa metin okunur — daha ucuz ama hata payı daha yüksek.",
        key="analysis_quality")
    if quality != saved_q:
        pipeline.save_settings(analiz_kalitesi=quality)
    # Parça C2: işlem günlüğü maliyetleri ve pozisyon hesabı (bu bilgisayarda saklanır; kişiye özel karar kullanıcıda)
    saved = pipeline.load_settings()
    c1, c2, c3, c4 = st.columns(4)
    commission = c1.number_input("Komisyon, alış+satış (%)", 0.0, 2.0, float(saved.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT)),
                                 0.01, format="%.2f", key="commission_pct",
                                 help="İşlem günlüğünde net getiri bu maliyet düşülerek hesaplanır. Midas'ın kendi oranını girin.")
    slippage = c2.number_input("Kayma, alış+satış (%)", 0.0, 2.0, float(saved.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT)),
                               0.01, format="%.2f", key="slippage_pct",
                               help="Emrin beklenen fiyattan biraz kötü gerçekleşmesi (alış-satış farkı vb.).")
    capital = c3.number_input("Sermaye (TL) — pozisyon hesabı için", 0.0, 1e9, float(saved.get("sermaye", 0.0)), 1000.0,
                              format="%.0f", key="capital", help="0 bırakılırsa pozisyon hesabı gösterilmez.")
    risk_pct = c4.number_input("İşlem başına göze alınan risk (%)", 0.0, 100.0, float(saved.get("risk_pct", 0.0)), 0.25,
                               format="%.2f", key="risk_pct", help="SL'ye gelinirse sermayenin en fazla yüzde kaçı kaybedilsin?")
    if (commission, slippage, capital, risk_pct) != (saved.get("komisyon_pct"), saved.get("kayma_pct"),
                                                      saved.get("sermaye"), saved.get("risk_pct")):
        pipeline.save_settings(komisyon_pct=commission, kayma_pct=slippage, sermaye=capital, risk_pct=risk_pct)
    # W6: bekçinin yapay zekâ yorumları için aylık bütçe (haber analizi maliyeti bunun dışında)
    ai_budget = st.number_input("Bekçi yapay zekâ yorumu aylık bütçesi ($)", 0.0, 100.0,
                                float(saved.get("yz_butce_usd", ai_comment.DEFAULT_BUDGET_USD)), 1.0, format="%.2f",
                                key="ai_budget", help="Rapor yorumu ve kaçırılan fırsat açıklamaları bu bütçeyi aşmaz: "
                                                     "bir çağrının en kötü durum maliyeti bütçeyi aşacaksa çağrı yapılmaz.")
    if ai_budget != saved.get("yz_butce_usd"):
        pipeline.save_settings(yz_butce_usd=ai_budget)
    # 2026-11-09 (kullanıcı onayı): haber analizinin de aylık bütçesi — bütçeyi aşacak analiz yapılmaz
    news_budget = st.number_input("Haber analizi aylık bütçesi ($)", 0.0, 500.0,
                                  float(saved.get("haber_butce_usd", config.NEWS_BUDGET_USD)), 1.0, format="%.2f",
                                  key="news_budget", help="Haberleri güncelle, sabah analizi ve 🔬 Haber analizi bu "
                                  "bütçeyi aşmaz: bir haberin en kötü durum maliyeti kalan bütçeyi aşacaksa o haber ve "
                                  "sonrakiler analiz edilmez. Bu ay harcanan 📰 Haberler sekmesinde görünür.")
    if news_budget != saved.get("haber_butce_usd"):
        pipeline.save_settings(haber_butce_usd=news_budget)
    if quality != config.DEFAULT_QUALITY:
        st.caption("⚠️ Bu ayarda maliyet düşer ama analizler daha az ayrıntılı ve hata payı daha yüksek olabilir.")
    st.caption("Kaynaklar: KAP + " + ", ".join(config.RSS_SOURCE_LABELS.get(n, n) for n in config.RSS_FEEDS)
               + ". KAP hızlı isteklere sınır koyduğu için ilk güncelleme birkaç dakika sürebilir.")

if h2.button("🔄 Haberleri güncelle", type="primary", width="stretch"):
    bar = st.progress(0.0, text="Başlıyor...")
    try:
        res = pipeline.update_all(conn, days=days, analysis_limit=analysis_limit, quality=quality,
                                  progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
        st.session_state["last_update"] = datetime.now(config.TR_TZ).strftime("%H:%M")
        st.session_state["last_result"] = res
        if not os.environ.get("HALLEY_OFFLINE"):  # yarım kalan / boşluk sayfalarını arka planda tamamla
            kap_worker.start(force=bool(res.get("kap", {}).get("rate_limited") or res.get("takvim_boslugu", {}).get("eklenen")))
    except Exception as e:
        flash("error", f"Güncelleme tamamlanamadı: {nice_err(e)}")
    conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
    st.rerun()

if h2.button("🧪 Ücretsiz dene", width="stretch", key="free_check",
             help="Haberleri ve fiyatları toplar ama yapay zekâyı çağırmaz; OpenAI kredisi harcanmaz. "
                  "Bir sonraki gerçek güncellemenin yaklaşık maliyetini gösterir."):
    bar = st.progress(0.0, text="Başlıyor (yapay zekâ kullanılmayacak)...")
    try:
        res = pipeline.free_check(conn, days=days, analysis_limit=analysis_limit, quality=quality,
                                  progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
        st.session_state["last_result"] = res
        if not os.environ.get("HALLEY_OFFLINE"):
            kap_worker.start(force=bool(res.get("kap", {}).get("rate_limited") or res.get("takvim_boslugu", {}).get("eklenen")))
    except Exception as e:
        flash("error", f"Ücretsiz deneme tamamlanamadı: {nice_err(e)}")
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
        st.warning("KAP geçici olarak istek sınırı uyguladı; kalan bildirimler arka planda, sınır kalkınca "
                   "kendiliğinden okunuyor (aşağıdaki durum kutusu). Tekrar basmanız gerekmez.")
    an = last.get("analyze", {})
    if an.get("errors"):
        st.error(f"{an['errors']} haber analiz edilemedi. Ayrıntı: Gelişmiş sekmesi.")
    if an.get("waiting"):
        st.caption(f"{an['waiting']} haber bir sonraki güncellemeyi bekliyor.")
    if last.get("rss", {}).get("failed_feeds"):
        st.caption("Bazı haber siteleri okunamadı. Ayrıntı: Gelişmiş sekmesi.")

with st.expander("❓ Nasıl kullanılır"):
    # Plan 1.3 (2026-11-09): programı kullanacak kişi için güncel kılavuz (KULLANIM.md ile aynı metin)
    _guide = config.ROOT / "KULLANIM.md"
    st.markdown(_guide.read_text(encoding="utf-8") if _guide.exists() else "Kılavuz dosyası (KULLANIM.md) bulunamadı.")

# ---------------- Piyasa bekçisi (W2): sabah / akşam analizi — kullanıcı elle başlatır ----------------
def watch_box() -> None:
    section_title("🛡️", "Piyasa bekçisi", note="sabah borsa açılmadan, akşam kapanıştan sonra bir kez basın")
    w1, w2 = st.columns(2)
    st.markdown("<div class='opt'>✨ Yapay zekâ seçenekleri <span>(isteğe bağlı; işaretlemezseniz ücretsiz)</span></div>",
                unsafe_allow_html=True)
    w3, a1, a2 = st.columns(3)
    use_ai = w3.checkbox("Sabah analizinde yeni haberleri yapay zekâ ile de analiz et", value=False, key="watch_ai",
                         help="Kapalıysa ücretsizdir: haberler toplanır, fiyatlar güncellenir, kayıtlı analizlerle "
                              "rapor hazırlanır. Açıksa Ayarlar'daki sınır kadar haber analiz edilir.")
    if use_ai:
        if pipeline.has_api_key():
            est = pipeline.estimate_next_run(conn, analysis_limit=analysis_limit, quality=quality)
            st.caption(f"Şu an sırada {est['waiting']} haber; bu çalıştırmada en fazla {analysis_limit} haber analiz "
                       f"edilir. Sıradakiler için tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} $ "
                       "(gece gelen yeni haberler toplanınca sıra değişebilir; üst sınır analiz adedidir).")
        else:
            st.caption("API anahtarı yok: yapay zekâ analizi yapılamaz, rapor ücretsiz kısımla hazırlanır.")
    ai_report = a1.checkbox("🤖 Raporu yapay zekâ ile yorumla (sabah/akşam)", value=False, key="watch_ai_report")
    ai_missed = a2.checkbox("🤖 Kaçırılan fırsatları yapay zekâ ile açıkla (akşam, en fazla 5 hisse)", value=False,
                            key="watch_ai_missed")
    if ai_report or ai_missed:
        if pipeline.has_api_key():
            e1 = ai_comment.estimate(6300)
            spent_ = ai_comment.month_spend(conn)
            st.caption(f"Tahmini maliyet: rapor yorumu {e1['low']:.3f}–{e1['high']:.3f} $ / çalıştırma"
                       + (f" · kaçırılan açıklaması {e1['low']:.3f}–{e1['high']:.3f} $ / hisse (en fazla "
                          f"{ai_comment.MAX_MISSED}; daha önce açıklanan ücretlendirilmez)" if ai_missed else "")
                       + f" · bu ay harcanan {spent_:.3f} $ / bütçe {ai_budget:.2f} $")
        else:
            st.caption("API anahtarı yok: yapay zekâ yorumu yapılamaz; rapor kodla hazırlanır.")
    for kind, col, label in (("sabah", w1, "🌅 Sabah analizi"), ("aksam", w2, "🌙 Akşam analizi")):
        tm = watchdog.timing(kind)
        if col.button(label, width="stretch", key=f"watch_{kind}",
                      help=("Borsa açılmadan önce: gece gelen haberler, tüm hisselerin fiyatı, açık işlemler, günün "
                            "fırsatları ve takvim." if kind == "sabah" else
                            "Kapanıştan sonra: günün fiyatları, işlem günlüğü (TP/SL), botun kararları.")):
            if tm["uyari"]:
                flash("warning", tm["uyari"] + " Analiz yine de çalıştırıldı; rapora bu uyarı yazıldı.")
            bar = st.progress(0.0, text="Başlıyor...")
            try:
                out = watchdog.run_session(
                    conn, uni, kind, {"gun": days, "analiz_siniri": analysis_limit, "analiz_kalitesi": quality,
                                      "komisyon_pct": commission, "kayma_pct": slippage, "pencere": window,
                                      "sermaye": capital, "risk_pct": risk_pct, "yz_butce_usd": ai_budget,
                                      "yz_rapor": bool(ai_report and pipeline.has_api_key()),
                                      "yz_kacirilan": bool(ai_missed and pipeline.has_api_key())},
                    ai=bool(use_ai and pipeline.has_api_key()),
                    progress=lambda m, p_: bar.progress(min(max(p_, 0.0), 1.0), text=m))
                st.session_state["watch_last"] = out["rapor"]
                flash("success", f"{label} tamamlandı; rapor arşive kaydedildi ({out['rapor']}).")
                if kind == "sabah":
                    st.session_state["last_update"] = datetime.now(config.TR_TZ).strftime("%H:%M")
                    res = out.get("guncelleme") or {}
                    if not os.environ.get("HALLEY_OFFLINE"):
                        kap_worker.start(force=bool(res.get("kap", {}).get("rate_limited")
                                                    or res.get("takvim_boslugu", {}).get("eklenen")))
            except Exception as e:
                flash("error", f"{label} tamamlanamadı: {nice_err(e)}")
            conn.close()
            st.rerun()
        if tm["uyari"]:
            col.caption("⚠️ " + re.split(r":\s", tm["uyari"], maxsplit=1)[0])
    name = st.session_state.get("watch_last")
    if name:
        path = watchdog.report_dir() / f"{name}.md"
        if path.exists():
            with st.expander(f"📄 Son bekçi raporu: {name} (arşivde saklandı, değiştirilmez)", expanded=True):
                st.markdown(path.read_text(encoding="utf-8"))
                st.download_button("Raporu indir (.md)", path.read_bytes(), file_name=f"{name}.md",
                                   key="watch_dl")


with st.container(border=True, key="watch"):
    watch_box()

# ---------------- Özet ----------------
_pd_key = conn.execute("SELECT MAX(date) FROM prices WHERE ticker='XU100'").fetchone()[0]
if st.session_state.get("_regime_key") != _pd_key:      # fiyat günü değişince yeniden hesapla (her çizimde değil)
    from bist_haber import regime as _regime
    st.session_state["_regime"] = _regime.regime(conn).get("ozet")
    st.session_state["_regime_key"] = _pd_key
if st.session_state.get("_regime"):
    _rg = st.session_state["_regime"]
    _tone = "down" if "trendi **düşüş" in _rg or "trendi düşüş" in _rg else "up" if "trendi **yükseliş" in _rg or "trendi yükseliş" in _rg else ""
    st.markdown(f"<div class='strip {_tone}'><span class='lbl'>📊 Piyasa durumu</span>{bold_html(_rg)} "
                "<span class='news-meta'>(bilgi; kararları değiştirmez)</span></div>", unsafe_allow_html=True)
rows = report.build(conn, uni, days=window)
positives = [r for r in rows if r["score"] >= 1.5]
negatives = [r for r in rows if r["score"] <= -1.5]
neutrals = [r for r in rows if -1.5 < r["score"] < 1.5]
m1, m2, m3 = st.container(key="kpi").columns(3)
m1.metric("Olumlu haber", f"{len(positives)} hisse")
m2.metric("Olumsuz haber", f"{len(negatives)} hisse")
m3.metric("Son güncelleme", last_update_text())

def kap_reader_box() -> None:
    """Arka plan KAP okuyucusunun durumu (kullanıcı isteği: eksik sayfalar kendiliğinden tamamlansın, özet bildirilsin)."""
    s_ = kap_worker.load()
    if not s_:
        return
    total = (s_.get("okunan") or 0) + (s_.get("kalan") or 0)
    if kap_worker.running() or s_.get("durum") == "çalışıyor":
        st.info(f"📥 KAP sayfaları arka planda okunuyor: {s_.get('okunan', 0)}/{total} · {s_.get('mesaj', '')} "
                "Paneli kullanmaya devam edebilirsiniz; bu kutu kendiliğinden yenilenir.")
        if total:
            st.progress(min(1.0, (s_.get("okunan") or 0) / total))
    elif s_.get("durum") == "tamamlandı" and s_.get("bitti", "") >= (datetime.now(config.TR_TZ).date().isoformat()):
        oz = s_.get("ozet") or {}
        text = f"✅ KAP okuması {s_['mesaj'][len('Tamamlandı: '):] if s_['mesaj'].startswith('Tamamlandı: ') else s_['mesaj']}"
        if oz:
            text += (f" Önümüzdeki 15 işlem günü: {oz.get('sirket', 0)} şirkette {oz.get('olay', 0)} olay"
                     + (" — öne çıkanlar: " + "; ".join(oz["onemli"]) if oz.get("onemli") else "") + ".")
        if s_.get("analiz_bekleyen"):
            text += f" {s_['analiz_bekleyen']} haberin metni hazır; analiz için **Haberleri güncelle**."
        st.success(text)
    elif s_.get("durum") == "durdu":
        st.warning("📥 KAP okuyucu durdu: " + s_.get("mesaj", ""))


@st.fragment(run_every=15)
def kap_reader_live() -> None:
    if not os.environ.get("HALLEY_OFFLINE"):
        kap_worker.start()   # panel yeniden başlatıldıysa yarım iş birkaç dakika içinde kendiliğinden sürer
    kap_reader_box()


def analysis_status_box() -> None:
    """Haber analizi ilerlemesi (2026-11-09 kullanıcı geri bildirimi: "ilerleme barı yok"). Hangi yoldan başlatılırsa
    başlatılsın (panel düğmesi, sabah analizi, arka plan) durum dosyasından okunur; sayfa yenilense de kaybolmaz."""
    s_ = analyzer.load_status()
    if not s_:
        return
    beat = datetime.fromisoformat(s_["nabiz"]) if s_.get("nabiz") else None
    fresh = beat and (datetime.now(config.TR_TZ) - beat).total_seconds() < 300
    tur, n, k = s_.get("tur", "haber analizi"), s_.get("toplam", 0), s_.get("biten", 0)
    if s_.get("durum") == "çalışıyor" and fresh:
        live = report.build(conn, uni, days=window)
        pos_, neg_ = sum(1 for r in live if r["score"] >= 1.5), sum(1 for r in live if r["score"] <= -1.5)
        st.info(f"🔬 {tur.capitalize()} sürüyor: {k}/{n} haber · şu ana kadar ≈ {s_.get('harcanan_usd', 0):.3f} $ · "
                f"şu an **olumlu {pos_} · olumsuz {neg_} hisse** (canlı). Paneli kullanmaya devam edebilirsiniz; bu kutu "
                "10 sn'de bir, liste ve sayılar yeni sonuç geldikçe en fazla 30 sn'de bir kendiliğinden yenilenir.")
        st.progress(min(1.0, k / max(n, 1)))
        if s_.get("suan"):
            st.caption("⏳ Şu an inceleniyor: " + " · ".join(f"**{x['hisse']}** — {x['konu']}: {x['baslik'][:60]}"
                                                            for x in s_["suan"]))
        if s_.get("son"):
            st.caption("✅ Son biten: " + " · ".join(f"{x['saat'][:5]} {x['sonuc']}" for x in s_["son"][:6]))
    elif s_.get("durum") == "çalışıyor":
        st.warning(f"🔬 {tur.capitalize()} yarıda kaldı ({k}/{n}; program kapanmış olabilir). Analiz edilen haberler "
                   "kaydedildi; kalanlar bekleyen listesinde.")
    elif (s_.get("bitti") or "")[:10] == datetime.now(config.TR_TZ).date().isoformat():
        r_ = s_.get("sonuc") or {}
        if tur == "derin inceleme":
            text_ = f"{r_.get('incelenen', 0)} haber yeniden incelendi, {r_.get('degisen', 0)} haberde sonuç değişti"
        else:
            text_ = (f"{r_.get('analyzed', 0)} haber analiz edildi, {r_.get('filtered_out', 0)} haber önemsiz bulundu"
                     + (f", {r_['errors']} hata" if r_.get("errors") else "")
                     + (f", {r_['butce_disi']} haber bütçe nedeniyle bekliyor" if r_.get("butce_disi") else ""))
        (st.warning if s_.get("durum") == "durdu" else st.success)(
            f"🔬 Son {tur} ({s_['bitti'][11:16]}): {text_} · gerçek maliyet ≈ {s_.get('harcanan_usd', 0):.3f} $"
            + (f" · durdu: {s_['neden']}" if s_.get("neden") else ""))


@st.fragment(run_every=10)
def analysis_status_live() -> None:
    """Her 10 sn durum dosyasını okur (ucuz). Analiz sürerken yeni sonuç geldiyse en fazla 30 sn'de bir, bittiğinde bir
    kez TÜM sayfayı yeniler: üstteki olumlu/olumsuz sayıları ve Bugünün listesi kullanıcı yenilemeden güncellenir."""
    s_ = analyzer.load_status()
    analysis_status_box()
    key = (s_.get("basladi"), s_.get("biten"), s_.get("durum"))
    seen = st.session_state.get("_an_seen")
    if seen is None:
        st.session_state["_an_seen"] = key
        st.session_state["_an_full_at"] = time.time()
        return
    if key != seen:
        finished = s_.get("durum") != "çalışıyor" and seen[2] == "çalışıyor"
        # aralık: en az 30 sn, sayfa çizimi uzunsa çizim süresinin 3 katı (sürekli yenilenme döngüsü olmasın)
        gap = max(30.0, 3 * st.session_state.get("_render_sec", 0.0))
        if finished or time.time() - st.session_state.get("_an_full_at", 0) >= gap:
            st.session_state["_an_seen"] = key
            st.session_state["_an_full_at"] = time.time()
            st.rerun(scope="app")


analysis_status_live()

if not os.environ.get("HALLEY_OFFLINE"):
    kap_worker.start()   # bekleyen çok sayfa varsa ya da önceki iş yarım kaldıysa kendiliğinden başlar
if kap_worker.running() or kap_worker.load().get("durum") == "çalışıyor":
    kap_reader_live()
else:
    kap_reader_box()

if calendar_sync.due() and not os.environ.get("HALLEY_OFFLINE"):
    # Kullanıcı isteği: takvim her açılışta (günde en fazla bir kez) resmi kaynaklardan kontrol edilsin.
    with st.spinner("Takvim resmi kaynaklardan kontrol ediliyor (günde bir kez, birkaç saniye)..."):
        calendar_sync.auto_check()

tab_list, tab_journal, tab_reports, tab_trend, tab_news, tab_adv = st.tabs(
    ["📈 Bugünün listesi", "📒 İşlem günlüğü", "📋 Raporlar", "🧭 Gelişim", "📰 Haberler", "🔧 Gelişmiş"])


# W1: panel ve bekçi aynı hesabı kullanır (bist_haber/signals.py)
CTX = signals.Context(conn)


def tech(ticker: str):
    """Teknik göstergeler (kodla hesaplanır, kredi harcamaz). Sayfa çiziminde bir kez hesaplanır."""
    return CTX.tech(ticker)


def _n(v, fmt="{:.2f}"):
    return "—" if v is None else fmt.format(v)


def technical_block(t) -> None:
    st.markdown("**📊 Teknik görünüm** <span class='news-meta'>(fiyat verisinden hesaplanır; haber skoruna katılmaz)</span>",
                unsafe_allow_html=True)
    if not t:
        st.caption("Bu hisse için yeterli fiyat geçmişi yok (en az 30 işlem günü gerekir). "
                   "Bir sonraki güncellemede 1 yıllık fiyat indirilir.")
        return
    pct = lambda v: _n(v, "{:+.1f}%")
    rows_ = [
        ("Trend", t["trend"], "Fiyatın 50 ve 200 günlük ortalamalara göre konumu"),
        ("Son fiyat", f"{_n(t['son_fiyat'])} TL ({t['tarih']})", "Fiyatlar gecikmelidir"),
        ("50 günlük ortalamaya göre", pct(t["fiyat_sma50_%"]), f"Ortalama {_n(t['sma50'])} TL"),
        ("200 günlük ortalamaya göre", pct(t["fiyat_sma200_%"]), f"Ortalama {_n(t['sma200'])} TL"),
        ("RSI (14 gün)", _n(t["rsi14"], "{:.0f}"), "70 üstü aşırı alım, 30 altı aşırı satım bölgesi"),
        ("MACD ivmesi", "olumlu" if (t["macd_hist"] or 0) > 0 else ("zayıf" if t["macd_hist"] is not None else "—"),
         "MACD çizgisi sinyal çizgisinin üstünde mi?"),
        ("Hacim", _n(t["hacim_orani"], "{:.1f} kat"), "Son 5 günün ortalaması / önceki 20 günün ortalaması"),
        ("52 haftalık zirveye uzaklık", pct(t["zirveye_uzaklik_%"]), f"Zirve {_n(t['zirve_52h'])} TL"),
        ("52 haftalık dibe uzaklık", pct(t["dibe_uzaklik_%"]), f"Dip {_n(t['dip_52h'])} TL"),
        ("Destek / direnç (20 gün)", f"{_n(t['destek_20g'])} / {_n(t['direnc_20g'])} TL", "Son 20 günün en düşük / en yüksek fiyatı"),
        ("Günlük oynaklık", pct(t["atr_%"]).replace("+", ""), "Ortalama günlük fiyat aralığı (ATR 14)"),
        ("Üstel ortalamalar 20 / 50 / 200", f"{_n(t['ema20'])} / {_n(t['ema50'])} / {_n(t['ema200'])} TL",
         "EMA: son günlere daha çok ağırlık verir"),
        ("Trend gücü (ADX 14)", _n(t["adx"], "{:.0f}") + (f" · +DI {t['arti_di']:.0f} / −DI {t['eksi_di']:.0f}" if t["adx"] is not None else ""),
         "20 altı zayıf, 25 üstü güçlü trend; yönü +DI/−DI gösterir"),
        ("Bollinger bantları", f"{_n(t['bb_alt'])} – {_n(t['bb_ust'])} TL" + (" · sıkışma" if t["bb_sikisma"] else ""),
         "20 gün ± 2 standart sapma; sıkışma = bant son 120 günün en dar %20'sinde"),
        ("OBV (20 gün)", t["obv_egilim"] or "—", "Hacmin yükselen/düşen günlere dağılımı: hareket hacimle destekleniyor mu?"),
        ("Endekse göre güç 20 / 60 gün", f"{pct(t['rs_20g_%'])} / {pct(t['rs_60g_%'])}",
         "Hissenin getirisi XU100'e göre; XU100 fiyatı yoksa boş"),
        ("Ort. günlük işlem hacmi", _n(t["islem_hacmi_tl"] / 1e6 if t["islem_hacmi_tl"] else None, "{:,.0f} milyon TL"),
         "Son 20 gün, fiyat × hacim; düşükse emir gerçekleşmesi zorlaşır"),
        ("Performans 1 / 5 / 20 gün", f"{pct(t['perf_1g_%'])} / {pct(t['perf_5g_%'])} / {pct(t['perf_20g_%'])}", ""),
    ]
    st.dataframe(pd.DataFrame(rows_, columns=["Gösterge", "Değer", "Açıklama"]), hide_index=True,
                 width="stretch")
    if t["notlar"]:
        st.caption("Notlar: " + " · ".join(t["notlar"]) + f" · {t['gun_sayisi']} işlem günü veriyle hesaplandı.")
    for w in t.get("veri_uyarilari", []):
        (st.error if t.get("veri_kritik") else st.warning)("Veri kontrolü: " + w)
    if not t.get("veri_uyarilari"):
        st.caption("✅ Veri kontrolü: fiyat güncel, sınırı aşan sıçrama ya da uzun boşluk yok.")


def news_move_block(ticker: str) -> None:
    """Haber fiyatlanmış mı? Son olumlu/olumsuz haberden önceki ve sonraki fiyat hareketi (yalnız ölçüm)."""
    imp = conn.execute("SELECT published_at, effective_date FROM impacts WHERE ticker=? AND direction!=0 ORDER BY published_at DESC LIMIT 1",
                       (ticker,)).fetchone()
    t = tech(ticker)
    if not imp or not t:
        return
    m = technical.news_moves_for(conn, ticker, imp["effective_date"], t.get("atr"))
    if not m:
        return
    pct = lambda v: "—" if v is None else f"{v:+.1f}%"
    after = pct(m.get("sonra_%")) + (f" ({m['sonra_atr']:+.1f} günlük ortalama hareket)" if m.get("sonra_atr") is not None else "")
    st.caption(f"⏱️ Haber fiyatlanmış mı? Son haber {imp['published_at'][:10]} · haberden önceki 5 işlem günü: "
               f"{pct(m.get('once_5g_%'))} · haberden bu yana: {after}. Haberden önceki büyük hareket beklentiyi ya da "
               "sızıntıyı, sonraki büyük hareket etkinin bir kısmının fiyata yansıdığını gösterebilir (yalnız ölçüm, "
               "yorum eşiği henüz test edilmedi).")


def financial_block(ticker: str) -> None:
    """Hissenin son finansal raporundan kodla hesaplanmış yıllık değişimler (varsa)."""
    row = conn.execute("SELECT published_at, body FROM news WHERE source='kap' AND body LIKE '[FİNANSAL TABLO ÖZETİ%' "
                       "AND (','||candidates||',') LIKE ? ORDER BY published_at DESC LIMIT 1",
                       (f"%,{ticker},%",)).fetchone()
    if not row or "YILLIK DEĞİŞİMLER" not in row["body"]:
        return
    part = row["body"].split("YILLIK DEĞİŞİMLER", 1)[1].split("\n\n", 1)[0]
    lines = [ln for ln in part.splitlines()[1:] if ln.strip()][:8]
    st.markdown(f"**📑 Son finansal rapor** <span class='news-meta'>({row['published_at'][:10]}, "
                "yıllık değişimler kodla hesaplandı)</span>", unsafe_allow_html=True)
    st.markdown("\n".join(f"- {esc(ln)}" for ln in lines))


_TL_CACHE = {}


def macro_risk_line():
    """Parça B4: vade (15 işlem günü) içindeki piyasa geneli olaylar — tüm hisseler için aynı."""
    return CTX.macro_risk()


def ticker_timeline(ticker: str) -> dict:
    if ticker not in _TL_CACHE:
        _TL_CACHE[ticker] = timeline.for_ticker(conn, ticker, datetime.now(config.TR_TZ).date(), 15)
    return _TL_CACHE[ticker]


def timeline_block(ticker: str) -> None:
    tl = ticker_timeline(ticker)
    st.markdown("**📅 Önümüzdeki 15 işlem günü — bu hisse için** <span class='news-meta'>(piyasa geneli + bilanço + "
                "şirket olayları; tarihler resmi takvim ve KAP bildirimlerinden)</span>", unsafe_allow_html=True)
    if not tl["olaylar"]:
        st.caption("Bu dönemde kayıtlı olay yok.")
    else:
        st.dataframe(pd.DataFrame([{"Tarih": f"{x['tarih'][8:10]}.{x['tarih'][5:7]}.{x['tarih'][:4]}",
                                    # hep metin: sayı ve "—" karışınca tablo dönüştürme hatası veriyordu (09.11)
                                    "Kaç işlem günü sonra": str(x["is_gunu_sonra"]) if x["is_gunu_sonra"] else "—",
                                    "Kapsam": x["kapsam"], "Olay": x["olay"], "Ayrıntı": x["ayrinti"]}
                                   for x in tl["olaylar"]]), hide_index=True, width="stretch")
    notes = [n for n in ([("Takvimi henüz bilinmeyen: " + ", ".join(tl["bilinmeyen"])) if tl["bilinmeyen"] else None,
                          tl.get("tatil_notu"), tl.get("kap_boslugu")]) if n]
    if tl.get("okunmamis_notu"):
        st.warning("⏳ " + tl["okunmamis_notu"])
    if notes:
        st.caption(" · ".join(notes))


def corp_event(ticker: str) -> dict:
    """Parça B3: kayıtlı KAP bildirimlerinden genel kurul / kâr payı / sermaye artırımı tarihleri."""
    return CTX.corp(ticker)


def earning(ticker: str) -> dict:
    """Parça B2: bilanço yasal son tarihi ve açıklanıp açıklanmadığı (eldeki kayıtlardan)."""
    return CTX.earning(ticker)


def scenario(r: dict) -> dict:
    """Haber + teknik + risk → SL/TP/vade senaryosu (kodla, kredi harcamaz). Bekçiyle aynı hesap (signals)."""
    return CTX.plan(r)


def dash_cells(df, cols, fmt="{:.2f}"):
    """Boş sayı hücresi tabloda "None" görünmesin: sayılar 2 basamaklı metin, boşlar "—" (2026-11-09 uçtan uca
    kontrolde bulundu: uygulanamayan senaryo ve açık işlem satırları "None" gösteriyordu)."""
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = [("—" if v is None or (isinstance(v, float) and v != v) else fmt.format(v)) for v in df[c]]
    return df


def md(text: str) -> str:
    """Koddan üretilen metni markdown'da güvenli göster: ~ (üstü çizili) ve * _ ` biçimlendirme işaretlerini kaçır."""
    return "".join("\\" + ch if ch in "~*_`" else ch for ch in str(text))


def entry_block(g: dict) -> None:
    """Parça A2: kırılım / geri çekilme / destekten tepki senaryoları (kodla, kredi harcamaz)."""
    st.markdown("**🧭 Giriş senaryoları** <span class='news-meta'>(her zaman mevcut fiyattan alım gerekmez; "
                "yatırım tavsiyesi değildir)</span>", unsafe_allow_html=True)
    items = g.get("senaryolar", [])
    best = next((s for s in items if s["tur"] == g.get("en_uygun")), None)
    if best is None:
        st.caption("Uygun giriş senaryosu yok. " + g.get("neden_yok", ""))
    else:
        st.markdown(f"**En uygun görünen: {md(best['ad'])}** · {md(best['emir'])}")
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Giriş", f"{best['giris']:.2f} TL", f"{best['uzaklik_%']:+.1f}% fiyattan", delta_color="off")
        c2.metric("Zarar durdur (SL)", f"{best['sl']:.2f} TL", f"{best['sl_%']:+.1f}%")
        c3.metric("TP1", f"{best['tp1']:.2f} TL", f"{best['tp1_%']:+.1f}%")
        c4.metric("TP2", f"{best['tp2']:.2f} TL", f"{best['tp2_%']:+.1f}%")
        c5.metric("Risk / getiri", f"1 : {best['rr1']:.1f}", f"TP2'de 1 : {best['rr2']:.1f}", delta_color="off")
        if capital > 0 and risk_pct > 0:
            try:
                ps = journal.position_size(capital, risk_pct, best["giris"], best["sl"], commission + slippage)
                st.caption(f"🧮 Pozisyon hesabı (sizin girdiğiniz sermaye {capital:,.0f} TL ve risk %{risk_pct:g}): "
                           f"**{ps['adet']} adet** ≈ {ps['tutar']:,.0f} TL; SL'ye gelinirse en fazla ≈ {ps['azami_kayip']:,.0f} TL "
                           f"(%{ps['azami_kayip_%']:.2f}, maliyet dahil). Sınırlayan: {ps['sinirlayan']}. Yalnız hesaplamadır.")
            except ValueError as e:
                st.caption(f"🧮 Pozisyon hesaplanamadı: {e}")
        st.caption(f"Bu senaryonun risk seviyesi: **{best.get('risk_seviyesi', '—')}** (ortak risk faktörleri + "
                   "bu senaryonun risk/getirisi) · "
                   f"Kaba vade tahmini: TP1 yaklaşık {best['tp1_gun']}, TP2 yaklaşık {best['tp2_gun']} işlem günü (garanti değil) · "
                   f"senaryo {best['gecerlilik_gun']} işlem günü geçerli · SL dayanağı: {best['sl_dayanak']} · "
                   f"TP1: {best['tp1_dayanak']} · TP2: {best['tp2_dayanak']}")
        st.markdown(f"- **Teyit:** {md(best['teyit'])}\n- **Geçersiz olur:** {md(best['gecersiz'])}\n"
                    f"- **Olumlu senaryo:** {md(best['olumlu'])}\n- **Olumsuz senaryo:** {md(best['olumsuz'])}\n"
                    f"- **Gerçekleşmezse:** {md(best['iptal'])}"
                    + "".join(f"\n- ⚠️ {md(n)}" for n in best["notlar"]))
    if items:
        table = [{"Senaryo": s["ad"],
                  "Durum": s.get("uygulanamaz") or s["kalite"],
                  "Emir": s.get("emir", ""), "Giriş": s.get("giris"), "SL": s.get("sl"), "TP1": s.get("tp1"),
                  "TP2": s.get("tp2"), "Risk/getiri (TP1)": s.get("rr1"), "Risk": s.get("risk_seviyesi", "")}
                 for s in items]
        st.dataframe(dash_cells(pd.DataFrame(table), ["Giriş", "SL", "TP1", "TP2", "Risk/getiri (TP1)"]),
                     hide_index=True, width="stretch")
    st.caption("📏 " + entries.BACKTEST_NOTE)


def scenario_block(p: dict) -> None:
    if p.get("girisler"):
        entry_block(p["girisler"])
    st.markdown("**🎯 Mevcut fiyattan girilirse (referans)** <span class='news-meta'>(tahmini; yatırım tavsiyesi "
                "değildir)</span>", unsafe_allow_html=True)
    if p["durum"] != "senaryo":
        st.caption(p["neden_yok"])
        if p["riskler"]:
            st.markdown("Risk notları:\n" + "\n".join(f"- {esc(x)}" for x in p["riskler"]))
        return
    if p.get("elverissiz"):
        st.warning("Mevcut seviyelerde risk/getiri elverişsiz: olası zarar olası kazançtan büyük.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Referans fiyat", f"{p['giris']:.2f} TL")
    c2.metric("Zarar durdur (SL)", f"{p['sl']:.2f} TL", f"{p['sl_%']:+.1f}%")
    c3.metric("Kâr al (TP)", f"{p['tp']:.2f} TL", f"{p['tp_%']:+.1f}%")
    c4.metric("Risk / getiri", f"1 : {p['rr']:.1f}" if p["rr"] else "—")
    d1, d2 = st.columns(2)
    d1.metric("Tahmini vade", f"{p['vade'][0]}–{p['vade'][1]} işlem günü")
    d2.metric("Risk seviyesi", p["risk_seviyesi"].capitalize())
    st.caption(f"SL dayanağı: {p['sl_dayanak']} · TP dayanağı: {p['tp_dayanak']}")
    st.info(p["aciklama"])
    if p["riskler"] or p["notlar"]:
        st.markdown("**Risk faktörleri**\n" + "\n".join(f"- {esc(x)}" for x in p["riskler"] + p["notlar"]))


def best_entry_columns(p: dict) -> dict:
    g = p.get("girisler") or {}
    s = next((x for x in g.get("senaryolar", []) if x["tur"] == g.get("en_uygun")), None)
    if not s:
        return {"En uygun giriş senaryosu": "yok" if p.get("durum") == "senaryo" else ""}
    return {"En uygun giriş senaryosu": s["ad"], "Giriş emri": s["emir"], "Giriş fiyatı": s["giris"],
            "Giriş SL": s["sl"], "Giriş TP1": s["tp1"], "Giriş TP2": s["tp2"], "Giriş r/g (TP1)": s["rr1"],
            "Giriş risk seviyesi": s.get("risk_seviyesi", ""),
            "Teyit": s["teyit"], "Geçersizlik": s["gecersiz"]}


def stock_details(r: dict) -> None:
    """Bir hisseye tıklanınca açılan ayrıntı: senaryo, teknik görünüm, finansal özet ve haberler."""
    pct = lambda v: "—" if v is None else f"{v:+.1f}%"
    st.caption(f"Haber skoru {r['score']:+.2f} · son 1 gün {pct(r['chg_1d'])} · son 5 gün {pct(r['chg_5d'])} · "
               f"{r['news_count']} haber. Emir vermeden önce haberin kendisini okuyun.")
    scenario_block(scenario(r))
    technical_block(tech(r["ticker"]))
    # D (2026-11-09): sektörüyle birlikte mi, ayrışıyor mu? (KAP sektör listesi; yalnız bilgi)
    st.caption("🏭 Sektör: " + sectors.compare_text(sectors.compare(conn, r["ticker"])))
    news_move_block(r["ticker"])
    st.caption("📑 Bilanço takvimi: " + earnings.describe(earning(r["ticker"])) +
               " (Yasal süreler: SPK II-14.1 Md. 10–11; garanti değil, SPK ek süre verebilir.)")
    timeline_block(r["ticker"])
    financial_block(r["ticker"])
    st.markdown("**📰 Haberler ve analiz**")
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
            f"<a href='{esc(i['url'] or '')}' target='_blank'>haberin kaynağını aç</a></div></div>",
            unsafe_allow_html=True)


def stock_list(items: list, empty_text: str, tone: str = "neu") -> None:
    if not items:
        st.caption(empty_text)
        return
    with st.container(key=f"list_{tone}"):
        _stock_rows(items)


def _stock_rows(items: list) -> None:
    for r in items:
        reason = (r["last_news"] or "").strip()
        reason = reason if len(reason) <= 80 else reason[:78].rstrip() + "…"
        badge = check_badge(r.get("flags", ""))
        with st.expander(f"**{r['ticker']}** · {reason}   {badge} · {technical.short_label(tech(r['ticker']))}"):
            st.markdown(f"**{esc(r['name'])}**")
            stock_details(r)


def macro_block() -> None:
    """Parça B1: piyasa geneli planlı olaylar (PPK, TÜFE). Tarihler yayımlanmış takvimden; tahmin edilmez."""
    today = datetime.now(config.TR_TZ).date()
    u = macro_calendar.upcoming(today, 15)
    tr_date = lambda d: f"{int(d[8:10])} {AYLAR[int(d[5:7]) - 1]}"
    if u["olaylar"]:
        items = "; ".join(f"**{tr_date(e['tarih'])}** {e['ad']}"
                          + ("" if e["tur"] == "tatil" or not e["saat"] else f" saat {e['saat']}" if e["saat"][0].isdigit()
                             else f", {e['saat']}")
                          + (" (bugün)" if e["bugun"] else "" if e["is_gunu_sonra"] is None
                             else f" ({e['is_gunu_sonra']} işlem günü sonra)")
                          + (" — tek kaynak" if e["dogrulama"] == "tek kaynak" else "") for e in u["olaylar"])
        text = f"📅 **Önümüzdeki 15 işlem günü** ({tr_date(u['bitis'])} dahil): {items}."
    else:
        text = f"📅 **Önümüzdeki 15 işlem günü** ({tr_date(u['bitis'])} dahil): piyasa geneli planlı makro olay yok."
    later = sorted((e for e in macro_calendar.next_of_each(today) if not any(x["tarih"] == e.get("tarih") for x in u["olaylar"])),
                   key=lambda e: e["tarih"] or "9999")
    if later:
        text += " Sonraki: " + "; ".join(
            (f"{e['ad'].split(' (')[0]} {tr_date(e['tarih'])} ({macro_calendar.business_days_between(today, date.fromisoformat(e['tarih']))} işlem günü sonra)"
             if e["tarih"] else f"{e['ad']} — sonraki tarih takvimimizde yok (yeni yıl takvimi henüz eklenmedi)") for e in later) + "."
    if u["bilinmeyen"]:
        text += " Bu pencerede takvimi henüz bilinmeyen: " + ", ".join(u["bilinmeyen"]) + "."
    if u.get("tatil_notu"):
        text += " " + u["tatil_notu"]
    st.markdown(text + " <span class='news-meta'>Faiz ve enflasyon açıklamaları tüm piyasayı oynatabilir; "
                "işlem günleri Borsa İstanbul tatilleri düşülerek sayıldı.</span>", unsafe_allow_html=True)
    warn = macro_calendar.stale(today)
    if warn:
        st.caption("🛠️ " + warn)
    st.caption("🔎 " + calendar_sync.summary_line() + " — yenilemek için: Gelişmiş → Takvim kontrolü.")


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# ---------------- Bugünün listesi ----------------
with tab_list:
    with st.container(key="macro"):
        macro_block()
    if not rows:
        st.info("Henüz liste yok. Yukarıdaki **Haberleri güncelle** düğmesine basın.")
    else:
        summary_ = tradeplan.opportunity_summary({r["ticker"]: scenario(r) for r in positives})
        # Parça C1: uygun senaryoları sanal işlem olarak günlüğe yaz (hisse başına tek açık kayıt), sonuçları güncelle
        for r in positives:
            t_rec = tech(r["ticker"])
            if t_rec:
                journal.record_auto(conn, r["ticker"], scenario(r), t_rec["tarih"], r["score"])
        journal.update_all(conn, commission, slippage)
        if summary_["uygun"]:
            st.markdown(
                f"<div class='opp'><div class='h'>🎯 Bugün {len(summary_['uygun'])} hissede uygun görünen giriş senaryosu var</div>"
                "<div class='chips'>" + "".join(
                    f"<span class='tk r-{esc(str(risk))}'><b>{esc(tk)}</b>{esc(name.split(' (')[0].lower())} · risk {esc(str(risk))}</span>"
                    for tk, name, risk in summary_["uygun"])
                + "</div><div class='f'>Kenar rengi risk seviyesini gösterir (yeşil düşük, turuncu orta, kırmızı yüksek). "
                "Ayrıntı için aşağıdan hisseye tıklayın. Bu bir senaryodur, yatırım tavsiyesi değildir.</div></div>",
                unsafe_allow_html=True)
        else:
            st.info("**Bugün uygun işlem fırsatı bulunamadı.** Her gün işlem yapmak gerekmez. "
                    + ("Nedenler: " + "; ".join(f"{k} ({v} hisse)" for k, v in summary_["nedenler"].items()) + "."
                       if summary_["nedenler"] else "Olumlu haber alan hisse yok."))
        section_title("📈", "Olumlu haber alanlar", "pos", len(positives))
        stock_list(positives, "Bu dönemde olumlu haber alan hisse yok.", "pos")
        section_title("📉", "Olumsuz haber alanlar", "neg", len(negatives))
        stock_list(negatives, "Bu dönemde olumsuz haber alan hisse yok.", "neg")
        if neutrals and st.toggle(f"Etkisi zayıf/nötr haberleri de göster ({len(neutrals)} hisse)", key="show_neutral"):
            section_title("👁️", "İzlenecekler", "neu", len(neutrals))
            stock_list(neutrals, "", "neu")
        st.caption("Bir hisseye tıklayınca haberin özeti, nedeni ve kaynağı açılır. "
                   "✅ Teyitli: iki ayrı analiz aynı sonuca vardı · ⚠️ Kontrol et: analizler çelişti ya da emin değil.")
        if st.session_state.get("signals_export_ready"):
            # Detaylı liste: haber analizi + teknik göstergeler (hepsi kayıtlı veriden, kredi harcamaz).
            detail = []
            for r in rows:
                t = tech(r["ticker"]) or {}
                last_imp = conn.execute("SELECT event_type, magnitude, confidence, persistence, reason FROM impacts "
                                        "WHERE ticker=? ORDER BY published_at DESC LIMIT 1", (r["ticker"],)).fetchone()
                detail.append({
                    "Hisse": r["ticker"], "Şirket": r["name"], "Sinyal": r["signal"],
                    "Kontrol": check_badge(r.get("flags", "")).replace("✅ ", "").replace("⚠️ ", ""),
                    "Haber skoru": round(r["score"], 2), "Haber sayısı": r["news_count"],
                    "Olay türü": EVENT_TR.get(last_imp["event_type"], last_imp["event_type"]) if last_imp else "",
                    "Etki": impact_word(last_imp["magnitude"]) if last_imp else "",
                    "Güven %": round(last_imp["confidence"] * 100) if last_imp else None,
                    "Kalıcılık": PERSIST_TR.get(last_imp["persistence"], "") if last_imp else "",
                    "Teknik trend": t.get("trend", ""), "Son fiyat": t.get("son_fiyat"),
                    "RSI 14": t.get("rsi14"), "50g ort. farkı %": t.get("fiyat_sma50_%"),
                    "200g ort. farkı %": t.get("fiyat_sma200_%"), "Hacim oranı": t.get("hacim_orani"),
                    "52h zirveye uzaklık %": t.get("zirveye_uzaklik_%"), "Destek 20g": t.get("destek_20g"),
                    "Direnç 20g": t.get("direnc_20g"), "Günlük oynaklık %": t.get("atr_%"),
                    "Perf. 1g %": t.get("perf_1g_%"), "Perf. 5g %": t.get("perf_5g_%"),
                    "Perf. 20g %": t.get("perf_20g_%"),
                    "EMA 20": t.get("ema20"), "EMA 50": t.get("ema50"), "EMA 200": t.get("ema200"),
                    "ADX 14": t.get("adx"), "+DI": t.get("arti_di"), "-DI": t.get("eksi_di"),
                    "Bollinger alt": t.get("bb_alt"), "Bollinger üst": t.get("bb_ust"),
                    "Bollinger sıkışma": "evet" if t.get("bb_sikisma") else ("hayır" if t else ""),
                    "OBV 20g": t.get("obv_egilim") or "",
                    "Endekse göre 20g %": t.get("rs_20g_%"), "Endekse göre 60g %": t.get("rs_60g_%"),
                    "Ort. işlem hacmi (mn TL)": t["islem_hacmi_tl"] / 1e6 if t.get("islem_hacmi_tl") else None,
                    "Senaryo": ("elverişsiz" if scenario(r).get("elverissiz") else "var")
                    if scenario(r)["durum"] == "senaryo" else "yok",
                    "Referans fiyat": scenario(r).get("giris"), "Zarar durdur (SL)": scenario(r).get("sl"),
                    "Kâr al (TP)": scenario(r).get("tp"), "Risk/getiri (1:x)": scenario(r).get("rr"),
                    "Tahmini vade (işlem günü)": "{}–{}".format(*scenario(r)["vade"]) if scenario(r).get("vade") else "",
                    "Risk seviyesi": scenario(r).get("risk_seviyesi", ""),
                    **best_entry_columns(scenario(r)),
                    "Bilanço durumu": earnings.describe(earning(r["ticker"])),
                    "Şirket olayları": corp_events.describe(corp_event(r["ticker"])),
                    "15 işlem günü takvimi": timeline.compact(ticker_timeline(r["ticker"])),
                    "Risk faktörleri": " | ".join(scenario(r).get("riskler", [])),
                    "Açıklama": scenario(r).get("aciklama", scenario(r).get("neden_yok", "")),
                    "Son haber özeti": r["last_news"],
                    "Neden": last_imp["reason"] if last_imp else "",
                })
            frame = pd.DataFrame(detail).round(2)
            st.download_button("⬇️ Detaylı listeyi indir (Excel uyumlu CSV)", frame.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"halley_liste_{datetime.now(config.TR_TZ).date()}.csv", mime="text/csv",
                               key="signals_download")
        elif st.button("⬇️ Listeyi indirmeye hazırla", key="signals_export_prepare"):
            # Dosya yalnızca istenince hazırlanır (indirme yöneticileri hazır dosyayı kendiliğinden indirebiliyor).
            st.session_state["signals_export_ready"] = True
            conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
            st.rerun()

# ---------------- İşlem günlüğü ----------------
def metrics_block(title: str, m: dict) -> None:
    st.markdown(f"**{title}** — kayıt {m['kayit']} · kapanan {m['kapanan']} · açık/bekleyen {m['acik_bekleyen']} · "
                f"gerçekleşmeyen {m['iptal']}")
    if not m["kapanan"]:
        st.caption("Henüz kapanan işlem yok.")
        return
    a, b, c, d, e, f = st.columns(6)
    a.metric("Kazanma oranı", f"%{m['kazanma_orani_%']:.0f}")
    b.metric("Ortalama net", f"%{m['ortalama_net_%']:+.2f}")
    c.metric("Ortalama R", "—" if m["ortalama_R"] is None else f"{m['ortalama_R']:+.2f}")
    d.metric("Kâr faktörü", "—" if m["kar_faktoru"] is None else f"{m['kar_faktoru']:.2f}")
    e.metric("Maks. düşüş", f"{m['maks_dusus_R']:.2f} R")
    f.metric("Sharpe (işlem başına)", "—" if m["sharpe_islem_basina"] is None else f"{m['sharpe_islem_basina']:.2f}")
    if not m["yeterli_ornek"]:
        st.warning(f"Yalnız {m['kapanan']} kapanan işlem var: {journal.MIN_TRADES_FOR_STATS}'dan az örnekte bu oranlar "
                   "rastlantıdan ayırt edilemez; karar için kullanmayın.")


with tab_journal:
    st.markdown("#### 📒 İşlem günlüğü")
    _pf = sectors.portfolio(conn)
    if _pf["hisse"]:
        st.caption("🧺 Açık/bekleyen işlemlerin sektörleri: " + " · ".join(f"{k}: {', '.join(v)}" for k, v in _pf["ana"].items()))
        if _pf["uyarilar"]:      # görünüm: tek kutuda maddeler (eskiden her uyarı ayrı kutuydu)
            st.warning(f"**🧺 Portföy riski ({len(_pf['uyarilar'])} uyarı)**\n\n"
                       + "\n".join("- " + w_.replace("*", "\\*") for w_ in _pf["uyarilar"]))
    st.caption("Panelde 'uygun' görünen her hissenin en uygun giriş senaryosu kendiliğinden SANAL işlem olarak kaydedilir "
               "ve sonraki günlerin fiyatlarıyla izlenir: giriş gerçekleşti mi, önce TP mi SL mi? Kural: TP1'de yarısı "
               "satılır, stop girişe çekilir, kalan TP2'ye izlenir; en fazla 30 işlem günü. Net getiri komisyon ve "
               "kayma düşülerek (⚙️ Ayarlar). Amaç haber sinyalinin işe yarayıp yaramadığını ölçmek. Geçmiş sonuç "
               "geleceği garanti etmez; yatırım tavsiyesi değildir.")
    metrics_block("Sanal (otomatik) işlemler", journal.metrics(conn, "otomatik"))
    metrics_block("Gerçek işlemleriniz", journal.metrics(conn, "gercek"))
    _sl = journal.slippage_stats(conn)
    if _sl["n"]:
        st.caption(f"Kayma (yalnız alış): {_sl['n']} gerçek alışınızda planlanan girişe göre ortalama "
                   f"%{_sl['ortalama_pct']:+.2f} (medyan %{_sl['medyan_pct']:+.2f}, en kötü %{_sl['en_kotu_pct']:+.2f}; "
                   "pozitif = pahalı alış). Ayarlardaki kayma varsayımı alış+satış toplamı "
                   f"%{slippage:.2f} (alış payı ≈ %{slippage / 2:.2f})."
                   + (" Örnek az: varsayımı değiştirmeden önce daha fazla işlem bekleyin." if _sl["n"] < 10 else ""))
    rows_j = conn.execute("SELECT * FROM trade_journal ORDER BY id DESC LIMIT 200").fetchall()
    if rows_j:
        tbl = []
        for jr in rows_j:
            res = json.loads(jr["sonuc_json"]) if jr["sonuc_json"] else {}
            tbl.append({"No": jr["id"], "Tür": "Gerçek" if jr["kaynak"] == "gercek" else "Sanal", "Hisse": jr["ticker"],
                        "Sinyal günü": jr["signal_day"], "Senaryo": entries.NAMES.get(jr["senaryo"], jr["senaryo"]),
                        "Giriş": jr["giris"], "SL": jr["sl"], "TP1": jr["tp1"], "TP2": jr["tp2"],
                        "Durum": jr["durum"], "Sonuç": res.get("sonuc", ""), "Alış günü": res.get("giris_gunu", ""),
                        "Net %": res.get("net_getiri_pct", res.get("acik_getiri_%")), "R": res.get("r")})
        st.dataframe(dash_cells(pd.DataFrame(tbl), ["Giriş", "SL", "TP1", "TP2", "Net %", "R"]),
                     hide_index=True, width="stretch")
        open_auto = [jr for jr in rows_j if jr["kaynak"] == "otomatik" and jr["durum"] in journal.OPEN_STATES]
        if open_auto:
            with st.expander("✍️ Bu işleme girdim (gerçek işleminizi kaydedin)"):
                choice = st.selectbox("Hangi sanal kayıt?", [jr["id"] for jr in open_auto], key="real_pick",
                                      format_func=lambda i: next(f"#{jr['id']} {jr['ticker']} · {entries.NAMES.get(jr['senaryo'], '')}"
                                                                 f" · giriş {jr['giris']:.2f}" for jr in open_auto if jr["id"] == i))
                g1, g2 = st.columns(2)
                fill_day = g1.date_input("Alış günü", datetime.now(config.TR_TZ).date(), key="real_day")
                fill_px = g2.number_input("Alış fiyatı (TL)", 0.0, 1e7, 0.0, 0.01, format="%.2f", key="real_px")
                if st.button("Kaydet", key="real_save"):
                    try:
                        journal.record_real(conn, int(choice), fill_day.isoformat(), float(fill_px))
                        journal.update_all(conn, commission, slippage)
                        st.success("Gerçek işleminiz kaydedildi; aynı seviyelerle ayrıca izlenecek.")
                    except ValueError as e:
                        st.error(f"Kaydedilemedi: {e}")
                    except Exception as e:   # beklenmeyen hata da paneli çökertmesin
                        conn.rollback()
                        st.error(f"Kaydedilemedi: {nice_err(e)}")
    else:
        st.info("Henüz kayıt yok. Panelde uygun giriş senaryosu çıktığında kendiliğinden eklenir.")


# ---------------- Haberler ----------------
def news_analysis_box() -> None:
    """🔬 Haber analizi (kullanıcı isteği 2026-11-09): kaç haber, hangileri, tahmini maliyet; ve analiz edilmiş haberi
    derin yeniden inceleme. Her ikisi aylık haber analizi bütçesine tabidir."""
    st.markdown("#### 🔬 Haber analizi")
    spent = analyzer.month_spend(conn)
    st.caption(f"Bu ay haber analizine harcanan ≈ {spent:.3f} $ · bütçe {news_budget:.2f} $ · kalan "
               f"{max(0.0, news_budget - spent):.3f} $ (Ayarlar'dan değişir). Tahminler bu bilgisayardaki gerçek analiz "
               "maliyetlerinden hesaplanır; gerçek tutar haberin uzunluğuna göre değişir.")
    if not pipeline.has_api_key():
        st.info("Analiz için OpenAI API anahtarı gerekir (sayfanın üstünden girin).")
    mode = st.radio("Ne yapılsın?", ["🆕 Bekleyen haberleri analiz et", "🔁 Analiz edilmiş haberi derin yeniden incele"],
                    horizontal=True, key="na_mode")
    if mode.startswith("🆕"):
        pend = analyzer.pending(conn)
        if not pend:
            st.info("Analiz bekleyen haber yok.")
            return
        pctx = analyzer.priority_context(conn)
        now_ = datetime.now(config.TR_TZ)
        rows_ = []
        for r in pend:
            age = (now_ - datetime.fromisoformat(r["published_at"])).days
            rows_.append({"Seç": False, "Öncelik": analyzer.PRIORITY_LABELS[analyzer.priority(r, pctx)],
                          "Tarih": r["published_at"][:16].replace("T", " "), "Yaş (gün)": age,
                          "Hisse": r["candidates"] or "—",
                          "Konu / kaynak": r["subject"] or config.RSS_SOURCE_LABELS.get(r["source"][4:], r["source"]),
                          "Başlık": (r["title"] or "")[:90], "_id": r["id"]})
        f1, f2, f3 = st.columns([1, 2, 1])
        tk = f1.text_input("Hisse kodu (süz)", key="na_ticker").strip().upper()
        groups = f2.multiselect("Öncelik grubu", list(analyzer.PRIORITY_LABELS.values()),
                                default=list(analyzer.PRIORITY_LABELS.values())[:2], key="na_groups")
        old_too = f3.checkbox(f"{config.AUTO_ANALYSIS_MAX_AGE_DAYS} günden eski haberler de", value=False, key="na_old")
        view = [x for x in rows_ if (not tk or tk in x["Hisse"].split(",")) and x["Öncelik"] in groups
                and (old_too or x["Yaş (gün)"] <= config.AUTO_ANALYSIS_MAX_AGE_DAYS)]
        st.caption(f"Bekleyen {len(pend)} haber · süzgeçten geçen {len(view)} (öncelik sırasıyla; en üstteki önce)")
        how = st.radio("Hangileri?", ["Listedeki ilk N haber (öncelik sırasıyla)", "Yalnız işaretlediklerim"],
                       horizontal=True, key="na_how")
        if how.startswith("Listedeki"):
            n_ = st.number_input("Kaç haber incelensin?", 1, config.MAX_ANALYSIS_MANUAL, min(30, max(1, len(view))), 1,
                                 key="na_n")
            chosen = [x["_id"] for x in view[:int(n_)]]
            st.dataframe(pd.DataFrame(view[:200]).drop(columns=["Seç", "_id"]) if view else pd.DataFrame(),
                         hide_index=True, width="stretch")
        else:
            edited = st.data_editor(pd.DataFrame(view[:300]) if view else pd.DataFrame(columns=["Seç"]),
                                    hide_index=True, width="stretch", key="na_pick",
                                    disabled=[c for c in (view[0].keys() if view else []) if c != "Seç"],
                                    column_config={"_id": None})
            chosen = [r["_id"] for r in edited.to_dict("records") if r.get("Seç")] if view else []
        sel = [r for r in pend if r["id"] in set(chosen)]
        sel.sort(key=lambda r: chosen.index(r["id"]))
        if not sel:
            st.caption("Seçili haber yok.")
            return
        est = analyzer.estimate_cost(conn, sel, quality)
        fit, over = analyzer.within_budget(conn, sel, news_budget, quality)
        st.info(f"Seçilen {len(sel)} haber · tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} $"
                + (f" · bütçe nedeniyle yalnız ilk {len(fit)} haber analiz edilir ({over} haber kalır)" if over else ""))
        if st.button(f"🔬 {len(fit)} haberi analiz et", key="na_run", disabled=not (fit and pipeline.has_api_key())):
            bar = st.progress(0.0, text="Yapay zekâ haberleri analiz ediyor...")
            before = analyzer.month_spend(conn)
            try:
                res = analyzer.analyze(conn, uni, rows=fit, quality=quality, budget_usd=news_budget, track=True,
                                       progress=lambda i, n: bar.progress(i / max(n, 1), text=f"Analiz ({i}/{n})..."))
                cost = analyzer.month_spend(conn) - before
                flash("success", f"{res.get('analyzed', 0)} haber analiz edildi, {res.get('filtered_out', 0)} haber ön "
                      f"elemede önemsiz bulundu" + (f", {res['errors']} haberde hata" if res.get("errors") else "")
                      + f". Gerçek maliyet ≈ {cost:.3f} $." + (" OpenAI hesabı/kotası nedeniyle durdu: "
                                                              + res["stopped"] if res.get("stopped") else ""))
            except Exception as e:
                flash("error", f"Analiz tamamlanamadı: {nice_err(e)}")
            conn.close()
            st.rerun()
        return
    # 🔁 derin yeniden inceleme
    since_ = (datetime.now(config.TR_TZ) - timedelta(days=14)).isoformat()
    an = conn.execute("SELECT n.id, n.published_at, n.title, n.source, n.subject, "
                      "GROUP_CONCAT(i.ticker || ':' || i.direction || ':' || i.magnitude || ':' || COALESCE(i.flag,''), ';') "
                      "AS imp, MAX(ABS(i.direction)) AS yonlu FROM news n JOIN impacts i ON i.news_id=n.id "
                      "WHERE n.status='analyzed' AND n.published_at>=? GROUP BY n.id ORDER BY n.published_at DESC",
                      (since_,)).fetchall()
    only_dir = st.checkbox("Yalnız olumlu/olumsuz işaretlenmiş haberler", value=True, key="ra_dir")
    only_flag = st.checkbox("Yalnız ⚠️ kontrol gerektirenler (çelişkili / tek görüş / etki belirsiz)", value=False,
                            key="ra_flag")
    yon = {1: "olumlu", -1: "olumsuz", 0: "nötr"}
    rows_ = []
    for r in an:
        parts = [x.split(":") for x in (r["imp"] or "").split(";") if x]
        if only_dir and not r["yonlu"]:
            continue
        if only_flag and not any(p_[3] in ("çelişkili", "tek görüş", "etki belirsiz") for p_ in parts):
            continue
        rows_.append({"Seç": False, "Tarih": r["published_at"][:16].replace("T", " "),
                      "Etki": ", ".join(f"{p_[0]} {yon.get(int(p_[1]), '?')} {p_[2]}/5" + (f" ({p_[3]})" if p_[3] else "")
                                        for p_ in parts),
                      "Başlık": (r["title"] or "")[:90], "_id": r["id"]})
    if not rows_:
        st.info("Son 14 günde bu süzgeçle analiz edilmiş haber yok.")
        return
    st.caption("Derin inceleme: en yüksek doğruluk, ZORUNLU ikinci bağımsız görüş ve iki kat metin. Önceki sonuç silinmez "
               "(geçmişte saklanır), yenisi skor hesabında kullanılır. Habere sonradan gelen fiyat hareketi analize "
               "verilmez (geriye dönük bilgi karışmasın).")
    edited = st.data_editor(pd.DataFrame(rows_), hide_index=True, width="stretch", key="ra_pick",
                            disabled=["Tarih", "Etki", "Başlık", "_id"], column_config={"_id": None})
    chosen = [r["_id"] for r in edited.to_dict("records") if r.get("Seç")]
    sel = analyzer.analyzed_rows(conn, chosen)
    if not sel:
        st.caption("İncelemek için tablodan haber işaretleyin.")
    else:
        est = analyzer.estimate_reanalysis(conn, sel)
        left_ = news_budget - analyzer.month_spend(conn)
        st.info(f"Seçilen {len(sel)} haber · tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} $"
                + (" · kalan bütçe yetmeyebilir; sığmayanlar atlanır" if est["high_usd"] > left_ else ""))
        if st.button(f"🔁 {len(sel)} haberi derin incele", key="ra_run", disabled=not pipeline.has_api_key()):
            bar = st.progress(0.0, text="Derin inceleme...")
            before = analyzer.month_spend(conn)
            try:
                res = analyzer.reanalyze(conn, uni, chosen, budget_usd=news_budget, track=True,
                                         progress=lambda i, n: bar.progress(i / max(n, 1), text=f"İnceleme ({i}/{n})..."))
                st.session_state["ra_last"] = res
                cost = analyzer.month_spend(conn) - before
                flash("success", f"{res['incelenen']} haber yeniden incelendi; {res['degisen']} haberde sonuç değişti"
                      + (f", {res['hata']} haberde hata" if res["hata"] else "")
                      + (f", {res['butce_disi']} haber bütçe nedeniyle atlandı" if res["butce_disi"] else "")
                      + f". Gerçek maliyet ≈ {cost:.3f} $.")
            except Exception as e:
                flash("error", f"İnceleme tamamlanamadı: {nice_err(e)}")
            conn.close()
            st.rerun()
    last_ = st.session_state.get("ra_last")
    if last_ and last_.get("sonuclar"):
        fmt = lambda xs: ", ".join(f"{x['ticker']} {yon.get(x['direction'], '?')} {x['magnitude']}/5" for x in xs) or "etki yok"
        st.markdown("**Son derin incelemenin sonucu (önce → sonra):**")
        st.dataframe(pd.DataFrame([{"Haber": (x.get("baslik") or "")[:70],
                                    "Önce": fmt(x.get("eski", [])) if "eski" in x else "—",
                                    "Sonra": fmt(x["yeni"]) if "yeni" in x else f"hata: {x.get('hata', '')}",
                                    "Değişti mi": "evet" if x.get("degisti") else ("—" if "hata" in x else "hayır")}
                                   for x in last_["sonuclar"]]), hide_index=True, width="stretch")


with tab_news:
    news_analysis_box()
    st.divider()
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
            f"<div class='news-meta' style='margin-top:6px'><a href='{esc(n['url'] or '')}' target='_blank'>haberin kaynağını aç</a>"
            f"</div></div>", unsafe_allow_html=True)

# ---------------- Gelişmiş ----------------
with tab_adv:
    st.markdown("#### Durum")
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM news GROUP BY status").fetchall())
    labels = {"new": "Analiz bekliyor", "analyzed": "Analiz edildi", "filtered_out": "Önemsiz bulundu (ön eleme)",
              "skipped": "Atlandı (rutin/ilgisiz/eski)", "error": "Hata",
              "context": "Takvim için alındı (analiz edilmez)"}
    legacy_empty = conn.execute("SELECT COUNT(*) FROM news WHERE source='kap' AND status='analyzed' "
                                "AND LENGTH(TRIM(COALESCE(body,''), char(9)||char(10)||char(13)||' '))=0").fetchone()[0]
    if legacy_empty:
        st.warning(f"Önceki sürümden {legacy_empty} KAP analizinin tam metni yok; bu kayıtlar listeye katılmıyor.")
    a1, a2 = st.columns(2)
    with a1:
        st.dataframe(pd.DataFrame([{"Durum": labels.get(k, k), "Adet": v} for k, v in counts.items()]),
                     hide_index=True, width="stretch")
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
                     hide_index=True, width="stretch")
    if last:
        with st.expander("Son güncellemenin teknik ayrıntıları"):
            st.json(last)

    st.divider()
    st.markdown("#### 📅 Takvim kontrolü")
    st.caption("TCMB (faiz kararı, PPK özeti, Enflasyon ve Finansal İstikrar raporları) ve Fed takvimleri resmi "
               "sayfalardan okunur; panel açılışında günde bir kez kendiliğinden de kontrol edilir. Sayfa yapısı "
               "değişmişse ya da bir tarih okunamazsa hiçbir şey değiştirilmez. Ücretsizdir, yapay zekâ kullanmaz.")
    if st.button("📅 Takvimi şimdi kontrol et", key="calendar_check"):
        with st.spinner("Resmi sayfalar okunuyor..."):
            try:
                rep_ = calendar_sync.check()
                names_ = {"tcmb": "TCMB", "fed": "Fed", "tuik": "TÜİK"}
                failed_ = [names_[k] for k in names_ if (rep_.get(k) or {}).get("durum") != "güncel"]
                if failed_:
                    st.warning(f"{', '.join(failed_)} sayfası okunamadı (internet bağlantısı ya da sayfa değişikliği). "
                               "Takvim değişmedi: son başarılı kontrolün verisi ve yerleşik takvim kullanılıyor.")
                else:
                    st.success("Takvim resmi kaynaklardan kontrol edildi.")
            except Exception as e:
                st.error(f"Kontrol tamamlanamadı: {nice_err(e)}")
    cal_state = calendar_sync.load()
    st.write(calendar_sync.summary_line())
    cal_rep = cal_state.get("report", {})
    if cal_rep:
        rows_cal = []
        for key, label in (("tcmb", "TCMB takvimi"), ("fed", "Fed (FOMC) takvimi"), ("tuik", "TÜİK TÜFE takvimi")):
            r_ = cal_rep.get(key, {})
            detail = r_.get("neden") or ("; ".join(r_.get("farklar") or []) or "yerleşik takvimle aynı")
            rows_cal.append({"Kaynak": label, "Durum": r_.get("durum", "—"), "Ayrıntı": detail})
        for item in cal_rep.get("elle", []):
            rows_cal.append({"Kaynak": item.split(" (")[0], "Durum": "elle kontrol gerekir",
                             "Ayrıntı": item.split(" (", 1)[1].rstrip(")") if " (" in item else ""})
        st.dataframe(pd.DataFrame(rows_cal), hide_index=True, width="stretch")

    st.divider()
    st.markdown("#### 📥 Takvim için KAP geçmişi")
    ctx_total = conn.execute("SELECT COUNT(*) FROM news WHERE status='context'").fetchone()[0]
    ctx_missing = conn.execute("SELECT COUNT(*) FROM news WHERE status='context' AND body IS NULL").fetchone()[0]
    st.caption(f"Bilanço durumu ve şirket olayları (genel kurul, kâr payı, sermaye artırımı) için son {config.KAP_HISTORY_DAYS} günün KAP "
               "bildirimlerini alır. Yapay zekâ KULLANMAZ, kredi harcamaz; kayıtlar analiz sırasına girmez. KAP bekleme "
               "süresi korunur. KAP sınır uygularsa okuyucu 3–10 dk bekleyip KENDİLİĞİNDEN devam eder; tamamlanınca "
               "üstte özet çıkar. Tekrar basmanız gerekmez.")
    st.write(f"Kayıtlı takvim bildirimi: {ctx_total} · form alanları okunmayı bekleyen: {ctx_missing}")
    if st.button(f"📥 Takvim için KAP geçmişini tamamla (son {config.KAP_HISTORY_DAYS} gün, ücretsiz)", key="kap_history"):
        bar = st.progress(0.0, text="KAP bildirim listesi alınıyor...")
        try:
            res = kap_history.fill_gaps(conn, uni)   # yalnız listesi alınmamış günler (taranan günler kaydı)
            started = kap_worker.start(force=True) if not os.environ.get("HALLEY_OFFLINE") else False
            if not res.get("bosluk_gun"):
                st.success(f"Son {config.KAP_HISTORY_DAYS} günün KAP listesi zaten eksiksiz; eklenecek bildirim yok.")
            else:
                st.success(f"{res['bosluk_gun']} eksik günün listesi alındı; {res['eklenen']} yeni takvim bildirimi "
                           "eklendi. " + ("Olay sayfaları arka planda okunuyor; ilerleme sayfanın üstündeki kutuda."
                                          if started or kap_worker.running() else "Okunacak yeni sayfa yok."))
        except Exception as e:
            conn.rollback()
            st.error(f"KAP geçmişi alınamadı: {nice_err(e)}")

    st.divider()
    st.markdown("#### 🧪 Ucuz test analizi")
    st.caption("Sıradaki en yeni 1 haberi ekonomik ayarla (kısa düşünme, ikinci kontrol yok) analiz eder ve sonucu "
               "burada gösterir. HİÇBİR ŞEY KAYDEDİLMEZ: listeye ve skora karışmaz, haber sırada kalır. Akışı denemek "
               "içindir; tahmini maliyet haber başına ~0,003–0,005 $.")
    if st.button("🧪 1 haberle ucuz test yap", key="cheap_test"):
        if not pipeline.has_api_key():
            st.warning("Test için OpenAI API anahtarı gerekli.")
        else:
            with st.spinner("Test analizi yapılıyor (kaydedilmeyecek)..."):
                try:
                    st.session_state["cheap_test_result"] = analyzer.test_one(conn, uni) or {"bos": True}
                except Exception as e:
                    st.session_state["cheap_test_result"] = {"hata": nice_err(e)}
    tr = st.session_state.get("cheap_test_result")
    if tr:
        if tr.get("bos"):
            st.info("Sırada analiz edilecek haber yok. Önce 🧪 Ücretsiz dene ile haber toplayın.")
        elif tr.get("hata"):
            st.error(f"Test tamamlanamadı: {tr['hata']}")
        else:
            row_ = tr["row"]
            st.write(f"**Haber:** {row_['title']}  \nKaynak: {row_['source']} · {row_['published_at'][:16].replace('T', ' ')}")
            st.write(f"**Maliyet:** {tr['usd']:.4f} $ · girdi {tr['input_tokens']:,} · çıktı {tr['output_tokens']:,} token")
            if tr["analysis"] is None:
                st.write(f"Ön eleme bu haberi önemsiz buldu: {tr['filter'].neden if tr['filter'] else '-'}")
            else:
                a = tr["analysis"]
                st.write(f"**Özet:** {a.ozet}")
                for imp in a.etkiler:
                    st.write(f"- {imp.hisse}: {imp.yon}, etki {impact_word(imp.etki)} — {imp.gerekce}")
                st.caption(f"Olay: {EVENT_TR.get(a.olay_tipi, a.olay_tipi)} · güven %{a.guven * 100:.0f} · "
                           "Bu sonuç kaydedilmedi; gerçek analiz yüksek doğrulukla ayrıca yapılır.")

with tab_trend:
    # W5: performans ve gelişim takibi + onay bekleyen öneriler. Onay hiçbir ayarı kendiliğinden değiştirmez.
    _today = datetime.now(config.TR_TZ).date()
    st.caption("Kayıtlı sanal işlemler, kaçırılan fırsat günlüğü ve karar izinden kodla hesaplanır (yapay zekâ yok). "
               f"Karşılaştırma ve öneri için en az {trends.MIN_TRADES} kapanmış işlem / {trends.MIN_FILTER_N} hisse-gün "
               "ve istatistiksel olarak anlamlı fark gerekir.")
    st.markdown("##### 🗳️ Onayınızı bekleyen öneriler")
    _pend = trends.pending(conn)
    if not _pend:
        st.info("Onay bekleyen öneri yok. Öneriler akşam analizinde, yeterli veri biriktikçe kendiliğinden oluşur.")
    for s_ in _pend:
        with st.container(border=True):
            st.markdown(f"**{s_['baslik']}** · _{ {'ayar': 'ayar önerisi', 'kod': 'kural/kod değişikliği', 'bilgi': 'bilgi'}.get(s_['tur'], s_['tur'])}_")
            st.markdown(md(s_["metin"]))
            if s_.get("nerede"):
                st.caption("Nerede: " + s_["nerede"])
            note_ = st.text_input("Not (isteğe bağlı)", key=f"sug_note_{s_['id']}")
            b1, b2, _ = st.columns([1, 1, 3])
            if b1.button("✅ Onayla", key=f"sug_ok_{s_['id']}"):
                trends.decide(conn, s_["id"], "onaylandı", note_)
                conn.close()
                st.rerun()
            if b2.button("❌ Reddet", key=f"sug_no_{s_['id']}"):
                trends.decide(conn, s_["id"], "reddedildi", note_)
                conn.close()
                st.rerun()
    st.caption("Onay yalnız kararınızı kaydeder: ayar önerisini Ayarlar'dan siz değiştirirsiniz; kural/kod önerisi "
               "geliştirme listesine girer. Hiçbir ayar ya da strateji kendiliğinden değişmez.")
    _perf = trends.performance(conn)
    _t = _perf["toplam"]
    st.markdown("##### 📈 Performans zaman içinde")
    if _t["n"]:
        p1, p2, p3 = st.columns(3)
        p1.metric("Kapanan sanal işlem", _t["n"])
        p2.metric("Kazanma oranı", f"%{_t['kazanma_%']:.0f}")
        p3.metric("Ortalama R", f"{_t['ort_R']:+.2f}" if _t["ort_R"] is not None else "—")
        if not _t["yeterli"]:
            st.warning(f"Örnek az ({_t['n']} < {trends.MIN_TRADES}): bu oranlar henüz güvenilir değil.")
        if _perf["haftalik"]:
            st.dataframe(dash_cells(pd.DataFrame([{"Hafta": w["hafta"], "İşlem": w["n"], "Kazanma %": w["kazanma_%"],
                                                   "Ort. R": w["ort_R"], "Toplam R": w["toplam_R"]}
                                                  for w in _perf["haftalik"]]), ["Kazanma %", "Ort. R", "Toplam R"]),
                         hide_index=True, width="stretch")
        if "karsilastirma" in _perf:
            a_, b_ = _perf["karsilastirma"]["son"], _perf["karsilastirma"]["onceki"]
            st.caption(f"Son {trends.MIN_TRADES} işlem: {a_['ort_R']:+.2f} R · önceki {trends.MIN_TRADES}: {b_['ort_R']:+.2f} R")
    else:
        st.info("Henüz kapanmış sanal işlem yok.")
    _ss = trends.strategy_stats(conn)
    for key_, title_ in (("senaryo", "🎯 Stratejiye göre"), ("kaynak_haber", "📰 Haber kaynağına göre"),
                         ("olay_turu", "🗂️ Haberin olay türüne göre"), ("risk", "⚠️ Risk seviyesine göre")):
        if _ss[key_]:
            st.markdown(f"##### {title_}")
            st.dataframe(dash_cells(pd.DataFrame([{"Grup": r["grup"], "İşlem": r["n"], "Kazanma %": r["kazanma_%"],
                                                   "Ort. R": r["ort_R"], "Ort. net %": r["ort_net_%"],
                                                   "Yeterli örnek": "evet" if r["yeterli"] else
                                                   f"hayır (< {trends.MIN_TRADES})"} for r in _ss[key_]]),
                                    ["Kazanma %", "Ort. R", "Ort. net %"]),
                         hide_index=True, width="stretch")
    st.markdown("##### 🧹 Hangi neden/filtre sonradan yükselen hisseleri eledi?")
    _fr = trends.filter_rates(conn, (_today - timedelta(days=180)).isoformat())
    if _fr["toplam_n"]:
        st.caption(f"{_fr['gun']} karar günü, {_fr['toplam_n']} hisse-gün; genel kaçırılan oranı %{_fr['genel_%']:.1f}. "
                   "Bir nedenin oranı diğerlerinden anlamlı yüksekse o filtre fazla fırsat eliyor olabilir.")
        st.dataframe(dash_cells(pd.DataFrame([{"Neden": r["neden"], "Değerlendirilen": r["degerlendirilen"],
                                               "Kaçırılan": r["kacirilan"], "Oran %": r["oran_%"],
                                               "Güven aralığı %": f"{r['alt_%']:.1f}–{r['ust_%']:.1f}",
                                               "Diğerleri %": r["digerleri_%"]} for r in _fr["satirlar"]]),
                                ["Oran %", "Diğerleri %"]), hide_index=True, width="stretch")
    else:
        st.info("Henüz penceresi tamamlanmış karar günü yok (bekçi en az bir akşam çalışmalı ve 5 işlem günü geçmeli).")
    _rep = trends.repeated(conn, _today)
    if _rep["son_sayi"] or _rep["onceki_sayi"]:
        st.markdown(f"##### 🔁 Tekrar eden nedenler (son {trends.RECENT_DAYS} gün / önceki {trends.RECENT_DAYS} gün)")
        codes_ = sorted(set(_rep["son_neden"]) | set(_rep["onceki_neden"]))
        st.dataframe([{"Neden": c_, "Son": _rep["son_neden"].get(c_, 0), "Önceki": _rep["onceki_neden"].get(c_, 0)}
                      for c_ in codes_], hide_index=True, width="stretch")
    _done = trends.decided(conn)
    if _done:
        with st.expander(f"Karar verilmiş öneriler ({len(_done)})"):
            st.dataframe([{"Tarih": (r["karar_ani"] or "")[:16].replace("T", " "), "Öneri": r["baslik"],
                           "Karar": r["durum"], "Not": r["karar_notu"] or ""} for r in _done],
                         hide_index=True, width="stretch")

conn.close()

with tab_adv:
    st.divider()
    st.markdown("### 🧪 Geçmiş veri pilotu")
    from bist_haber.backtest_ui import render as render_backtest
    render_backtest()

with tab_reports:
    # W3: bekçi rapor arşivi — yalnız okunur; dosyalar değiştirilmez, silinmez
    names = watchdog.list_reports()
    if not names:
        st.info("Henüz bekçi raporu yok. Üstteki **🌅 Sabah analizi** ya da **🌙 Akşam analizi** düğmesiyle ilk raporu "
                "oluşturun; her rapor tarihiyle arşive kaydedilir.")
    else:
        f1, f2 = st.columns([1, 3])
        kind_f = f1.radio("Tür", ["Hepsi", "Sabah", "Akşam"], horizontal=False, key="rep_kind")
        shown = [n for n in names if kind_f == "Hepsi" or ("_sabah" in n) == (kind_f == "Sabah")]
        def label(n) -> str:
            """Arşiv adı → okunur etiket. Beklenmeyen değerde çökmez (2026-11-09 uçtan uca testte bulundu)."""
            n = str(n or "")
            m = re.match(r"^(\d{4}-\d{2}-\d{2})_(sabah|aksam)(?:_(\d+))?$", n)
            if not m:
                return n
            return (("🌅 " if m.group(2) == "sabah" else "🌙 ") + m.group(1)
                    + (" sabah" if m.group(2) == "sabah" else " akşam")
                    + (f" ({m.group(3)}. çalıştırma)" if m.group(3) else ""))

        if shown:
            pick = f2.selectbox(f"Rapor ({len(shown)} kayıt, en yeni üstte)", shown, format_func=label, key="rep_pick")
            if pick not in shown:          # süzgeç değişince eski seçim listede yoksa ilk rapor gösterilir
                pick = shown[0]
            path = watchdog.report_dir() / f"{pick}.md"
            d1, d2 = st.columns(2)
            d1.download_button("Raporu indir (.md)", path.read_bytes(), file_name=path.name, key="rep_dl_md")
            jp = path.with_suffix(".json")
            if jp.exists():
                d2.download_button("Ham veriyi indir (.json)", jp.read_bytes(), file_name=jp.name, key="rep_dl_json")
            st.caption("Arşivdeki raporlar o anki veriyle üretildi ve sonradan değiştirilmez (geriye dönük bilgi karışmaz).")
            st.markdown(path.read_text(encoding="utf-8"))
        else:
            f2.info("Bu türde rapor yok.")

st.markdown("<div class='disclaimer'>Halley haberleri otomatik olarak özetler ve puanlar; yatırım tavsiyesi değildir. "
            "Puan eşikleri henüz geçmiş veriyle ayarlanmadı. Karar ve emir sorumluluğu kullanıcıdadır.</div>",
            unsafe_allow_html=True)
st.session_state["_render_sec"] = time.time() - _RENDER_T0
