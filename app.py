"""Halley — BIST haber paneli. Başlatmak için: baslat.bat (çift tıkla).

Terminal düzeni (2026-11-09 kullanıcı isteği, plan Aşama 3): üstte sabit menü, 9 ayrı ekran (Dashboard, Fırsatlar,
Hisse Analizi, Takip Listem, Bekçi, Haberler, İşlem Günlüğü, Performans, Ayarlar). Hesaplar değişmedi; yalnız
yerleşim. Yalnız seçili ekran çizilir.
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
                        trends, watchdog, ai_comment, sectors, transfer, notify, takip_ui, tracker, firsat_log, ready, ai_service,
                        weekly, chart)
from bist_haber.textutil import tr_fold  # noqa: E402

st.set_page_config(page_title="Halley", page_icon="☄️", layout="wide", initial_sidebar_state="collapsed")
_RENDER_T0 = time.time()   # sayfa çizim süresi (otomatik yenileme aralığı buna göre)

# Karanlık mod (2026-11-09 kullanıcı isteği: "beyaz ekran göz yoruyor"). config.toml'daki özel tema Streamlit menüsünde
# koyu temaya geçişi kilitliyor; bu yüzden seçim panelde (üst bantta) yapılır, data/ayarlar.json'da saklanır ve tema
# her çalıştırmada buradan uygulanır. Tek kullanıcılı yerel uygulama: tema ayarı tüm sekmeler için ortaktır.
from streamlit import config as _st_config  # noqa: E402

# 2026-11-09 Aşama 3: varsayılan koyu tema (kullanıcı isteği: koyu, terminal tarzı); seçim Ayarlar'da saklanır
DARK = bool(pipeline.load_settings().get("karanlik_mod", True))
_THEME = ({"base": "dark", "primaryColor": "#818CF8", "backgroundColor": "#0D1322", "secondaryBackgroundColor": "#1A2338",
           "textColor": "#E2E8F0", "linkColor": "#A5B4FC", "borderColor": "#2A3850",
           "dataframeHeaderBackgroundColor": "#1E293B"} if DARK else
          {"base": "light", "primaryColor": "#4F46E5", "backgroundColor": "#F3F5FA", "secondaryBackgroundColor": "#FFFFFF",
           "textColor": "#0F172A", "linkColor": "#4338CA", "borderColor": "#D5DBE8",
           "dataframeHeaderBackgroundColor": "#EEF2FF"})
_theme_changed = False
for _k, _v in _THEME.items():
    if _st_config.get_option(f"theme.{_k}") != _v:
        _st_config.set_option(f"theme.{_k}", _v, where_defined="Halley karanlık mod")
        _theme_changed = True
if _theme_changed and st.session_state.get("_theme_applied") != DARK:
    st.session_state["_theme_applied"] = DARK      # tek sefer: tema tarayıcıya bir sonraki çizimde gider
    st.rerun()
st.session_state["_theme_applied"] = DARK
_CSS_VARS = ('--h-ink:#F1F5F9; --h-sub:#E2E8F0; --h-muted:#B6C2D4; --h-line:#2B3852; --h-pos:#22C55E; --h-neg:#F87171; --h-acc:#818CF8; --h-amber:#F59E0B; --h-card:#151E31; --h-card2:#111A2C; --h-hover:#1E2A44; --h-cnt-bg:#1E2A4A; --h-cnt-fg:#C7D2FE; --h-pos-bg:rgba(34,197,94,.16); --h-pos-fg:#86EFAC; --h-neg-bg:rgba(248,113,113,.16); --h-neg-fg:#FCA5A5; --h-warn-bg:rgba(245,158,11,.16); --h-warn-fg:#FCD34D; --h-neu-bg:#243049; --h-neu-fg:#E2E8F0; --h-pos-txt:#4ADE80; --h-neg-txt:#F87171; --h-opp-a:#0B2A20; --h-opp-line:#1F5F3F; --h-opp-h:#6EE7B7; --h-bg:#0D1322; --h-glow1:rgba(99,102,241,.20); --h-glow2:rgba(245,158,11,.06); --h-btn:#1A2338; --h-btn-hover:#262F55; --h-btn-hover-fg:#E0E7FF; --h-input:#0F1729; --h-hero:linear-gradient(118deg, #1E1B4B 0%, #3730A3 55%, #6D28D9 100%); --a-warn-bg:rgba(245,158,11,.10); --a-warn-bd:#F59E0B; --a-warn-fg:#FDE68A; --a-info-bg:rgba(129,140,248,.12); --a-info-bd:#818CF8; --a-info-fg:#E0E7FF; --a-ok-bg:rgba(34,197,94,.10); --a-ok-bd:#22C55E; --a-ok-fg:#BBF7D0; --a-err-bg:rgba(248,113,113,.12); --a-err-bd:#F87171; --a-err-fg:#FECACA;' if DARK else
             '--h-ink:#0F172A; --h-sub:#1E293B; --h-muted:#334155; --h-line:#D5DBE8; --h-pos:#16A34A; --h-neg:#DC2626; --h-acc:#4F46E5; --h-amber:#D97706; --h-card:#FFFFFF; --h-card2:#FFFFFF; --h-hover:#EEF2FF; --h-cnt-bg:#EEF2FF; --h-cnt-fg:#3730A3; --h-pos-bg:#DCFCE7; --h-pos-fg:#166534; --h-neg-bg:#FEE2E2; --h-neg-fg:#991B1B; --h-warn-bg:#FEF3C7; --h-warn-fg:#92400E; --h-neu-bg:#E2E8F0; --h-neu-fg:#1E293B; --h-pos-txt:#15803D; --h-neg-txt:#B91C1C; --h-opp-a:#ECFDF5; --h-opp-line:#A7F3D0; --h-opp-h:#065F46; --h-bg:#F3F5FA; --h-glow1:#E0E7FF; --h-glow2:#FEF3C7; --h-btn:#FFFFFF; --h-btn-hover:#EEF2FF; --h-btn-hover-fg:#4338CA; --h-input:#FFFFFF; --h-hero:linear-gradient(118deg, #0F172A 0%, #1E1B4B 52%, #3730A3 100%); --a-warn-bg:#FFFBEB; --a-warn-bd:#F59E0B; --a-warn-fg:#78350F; --a-info-bg:#EEF2FF; --a-info-bd:#6366F1; --a-info-fg:#1E1B4B; --a-ok-bg:#F0FDF4; --a-ok-bd:#22C55E; --a-ok-fg:#14532D; --a-err-bg:#FEF2F2; --a-err-bd:#EF4444; --a-err-fg:#7F1D1D;')

# Görünüm (2026-11-09 kullanıcı isteği: "dağınık, önemli bilgiler silik"): koyu ve okunur yazı, kart düzeni, renkli
# bölüm başlıkları. Yalnız sunum; hiçbir hesap değişmez.
st.markdown("""
<style>
:root {/*VARS*/}
.stApp {background: radial-gradient(1100px 380px at 8% -8%, var(--h-glow1) 0%, transparent 62%),
        radial-gradient(800px 300px at 100% -4%, var(--h-glow2) 0%, transparent 58%), var(--h-bg);}
.block-container {padding-top: 1.1rem; max-width: 1440px;}
header[data-testid="stHeader"] {display: none;}
/* uygulama görünümü: web'e özgü sağ üst menü (Stop / ⋮) gizli; yenilemek için F5 */
[data-testid="stToolbar"], [data-testid="stStatusWidget"], [data-testid="stMainMenu"], [data-testid="stAppDeployButton"] {display: none !important;}
/* silik yazılar → okunur */
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: var(--h-muted) !important;
  font-size: 0.9rem; line-height: 1.55; opacity: 1 !important;}
[data-testid="stWidgetLabel"] p {color: var(--h-ink); font-weight: 600;}
.stMarkdown p, .stMarkdown li {color: var(--h-sub);}
/* üst bant */
.hero {background: var(--h-hero); border-radius: 18px; margin-bottom: 18px;
  padding: 20px 26px 18px; position: relative; overflow: hidden; border: 1px solid rgba(129,140,248,.25); box-shadow: 0 14px 34px -16px rgba(30,27,75,.55);}
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
.sec .cnt {font-size: .8rem; font-weight: 700; padding: 2px 10px; border-radius: 999px; background: var(--h-cnt-bg); color: var(--h-cnt-fg);}
.sec.t-pos .cnt {background: var(--h-pos-bg); color: var(--h-pos-fg);} .sec.t-neg .cnt {background: var(--h-neg-bg); color: var(--h-neg-fg);}
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
/* özet kartları: renk kartın ANAHTARINA bağlı (sıraya değil; 2026-11-09 sırayla renk kayması düzeltildi) */
.st-key-kpi_pos div[data-testid="stMetric"], .st-key-kpi_bist_up div[data-testid="stMetric"] {border-top: 5px solid var(--h-pos);}
.st-key-kpi_neg div[data-testid="stMetric"], .st-key-kpi_bist_down div[data-testid="stMetric"] {border-top: 5px solid var(--h-neg);}
.st-key-kpi_opp div[data-testid="stMetric"] {border-top: 5px solid var(--h-amber);}
.st-key-kpi_upd div[data-testid="stMetric"], .st-key-kpi_bist_flat div[data-testid="stMetric"] {border-top: 5px solid var(--h-acc);}
.st-key-kpi_pos [data-testid="stMetricValue"], .st-key-kpi_bist_up [data-testid="stMetricValue"] {color: var(--h-pos-txt);}
.st-key-kpi_neg [data-testid="stMetricValue"], .st-key-kpi_bist_down [data-testid="stMetricValue"] {color: var(--h-neg-txt);}
.st-key-kpi_opp [data-testid="stMetricValue"] {color: var(--h-amber);}
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
button[data-baseweb="tab"]:hover {background: var(--h-hover);}
button[data-baseweb="tab"][aria-selected="true"] {background: linear-gradient(118deg, #4F46E5, #7C3AED);}
button[data-baseweb="tab"][aria-selected="true"] p {color: #FFFFFF;}
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {display: none;}
/* düğmeler ve uyarılar */
.stButton button, .stDownloadButton button, [data-testid="stFormSubmitButton"] button {font-weight: 700; border-radius: 10px;
  transition: background .15s, border-color .15s, color .15s;}
/* ikincil düğmeler: tema değişse de tarayıcı eski rengi tutmasın diye renk açıkça verilir */
.stButton button[kind="secondary"], .stDownloadButton button, [data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"] {
  background: var(--h-btn) !important; color: var(--h-ink) !important; border: 1px solid var(--h-line) !important;}
.stButton button[kind="secondary"]:hover, .stDownloadButton button:hover,
[data-testid="stFormSubmitButton"] button[kind="secondaryFormSubmit"]:hover {
  background: var(--h-btn-hover) !important; color: var(--h-btn-hover-fg) !important; border-color: var(--h-acc) !important;}
.stButton button p, .stDownloadButton button p, [data-testid="stFormSubmitButton"] button p {color: inherit !important;}
.stButton button:disabled {opacity: .55;}
.stButton button[kind="primary"]:hover {filter: brightness(1.12);}
/* giriş kutuları */
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background: var(--h-input) !important; border-color: var(--h-line) !important;}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea {color: var(--h-ink) !important;}
[data-testid="stNumberInputStepDown"], [data-testid="stNumberInputStepUp"] {background: var(--h-btn) !important;}
[data-testid="stExpander"] summary:hover {background: var(--h-hover); border-radius: 14px;}
/* uyarı kutuları: iki temada da okunur renkler */
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {background: var(--a-warn-bg) !important; border-left: 4px solid var(--a-warn-bd);}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) * {color: var(--a-warn-fg) !important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {background: var(--a-info-bg) !important; border-left: 4px solid var(--a-info-bd);}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) * {color: var(--a-info-fg) !important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {background: var(--a-ok-bg) !important; border-left: 4px solid var(--a-ok-bd);}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) * {color: var(--a-ok-fg) !important;}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {background: var(--a-err-bg) !important; border-left: 4px solid var(--a-err-bd);}
[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) * {color: var(--a-err-fg) !important;}
[data-testid="stAlertContainer"] a {text-decoration: underline;}
.stButton button[kind="primary"] {background: linear-gradient(118deg, #4F46E5, #7C3AED); border: none;
  box-shadow: 0 8px 18px -10px rgba(79,70,229,.8);}
[data-testid="stAlertContainer"] {border-radius: 12px;}
[data-testid="stAlertContainer"] p {font-weight: 500;}
/* fırsat özeti */
.opp {background: linear-gradient(135deg, var(--h-opp-a), var(--h-card) 70%); border: 1px solid var(--h-opp-line); border-radius: 16px;
  padding: 14px 18px; margin: 4px 0 8px;}
.opp .h {font-size: 1.05rem; font-weight: 800; color: var(--h-opp-h);}
.opp .chips {display: flex; flex-wrap: wrap; gap: 8px; margin: 10px 0 8px;}
.opp .tk {background: var(--h-card2); border: 1px solid var(--h-line); border-radius: 10px; padding: 5px 10px; font-size: .86rem;
  color: var(--h-sub); border-left: 4px solid #94A3B8;}
.opp .tk b {color: var(--h-ink); margin-right: 4px;}
.opp .tk.r-düşük {border-left-color: var(--h-pos);} .opp .tk.r-orta {border-left-color: var(--h-amber);}
.opp .tk.r-yüksek {border-left-color: var(--h-neg);}
.opp .f {font-size: .85rem; color: var(--h-muted);}
/* haber kartları */
.news-card {background: var(--h-card); border: 1px solid var(--h-line); border-radius: 12px; padding: 12px 16px; margin-bottom: 8px;}
.news-meta {color: var(--h-muted); font-size: 0.86rem;}
.chip {display:inline-block; padding:2px 10px; border-radius:999px; font-size:0.8rem; font-weight:700; margin-right:6px;}
.warn {background:var(--h-warn-bg); color:var(--h-warn-fg);} .pos {background:var(--h-pos-bg); color:var(--h-pos-fg);}
.neg {background:var(--h-neg-bg); color:var(--h-neg-fg);} .neu {background:var(--h-neu-bg); color:var(--h-neu-fg);}
.disclaimer {color: var(--h-muted); font-size:0.84rem; margin-top:2rem; border-top: 1px solid var(--h-line); padding-top: 12px;}
/* Aşama 3 (2026-11-09): terminal düzeni — üst bant, sabit menü, kartlar */
.topbar {display: flex; align-items: baseline; gap: 14px; flex-wrap: wrap; padding: 2px 2px 0;}
.topbar .brand {font-size: 1.55rem; font-weight: 800; color: var(--h-ink); letter-spacing: -.02em;}
.topbar .tag {font-size: .74rem; font-weight: 800; color: var(--h-acc); border: 1px solid var(--h-acc); border-radius: 999px;
  padding: 1px 9px; text-transform: uppercase; letter-spacing: .04em;}
.topbar .meta {color: var(--h-muted); font-size: .86rem;}
/* menü yapışkan: sabitleme menünün KABINDA (menü kendi kabında sabitlenince kaydırınca kayboluyordu) */
div:has(> .st-key-navbar) {position: sticky; top: 0; z-index: 990; background: var(--h-bg); padding: 6px 0 8px;
  border-bottom: 1px solid var(--h-line);}
.st-key-navbar [role="radiogroup"] {gap: 5px; flex-wrap: wrap;}
.st-key-navbar label[data-baseweb="radio"] {background: var(--h-card); border: 1px solid var(--h-line); border-radius: 10px;
  padding: 6px 13px; margin: 0 !important; cursor: pointer; transition: background .12s;}
.st-key-navbar label[data-baseweb="radio"] > div:first-child {display: none;}
.st-key-navbar label[data-baseweb="radio"] p {font-weight: 700; color: var(--h-muted); font-size: .92rem;}
.st-key-navbar label[data-baseweb="radio"]:hover {background: var(--h-hover);}
.st-key-navbar label[data-baseweb="radio"]:has(input:checked) {background: linear-gradient(118deg, #4F46E5, #7C3AED);
  border-color: transparent;}
.st-key-navbar label[data-baseweb="radio"]:has(input:checked) p {color: #FFFFFF;}
[class*="st-key-row_pos_"] {border-left: 4px solid var(--h-pos) !important;}
[class*="st-key-row_neg_"] {border-left: 4px solid var(--h-neg) !important;}
[class*="st-key-row_neu_"] {border-left: 4px solid #94A3B8 !important;}
[class*="st-key-row_"] {background: var(--h-card); padding: 6px 12px !important;}
[class*="st-key-d_"] {background: var(--h-card);}
[class*="st-key-d_"] .sec {margin-top: 2px;}
.page-h {font-size: 1.35rem; font-weight: 800; color: var(--h-ink); margin: 6px 0 2px;}
.page-s {color: var(--h-muted); font-size: .9rem; margin-bottom: 10px;}

</style>
""".replace("/*VARS*/", _CSS_VARS), unsafe_allow_html=True)

GUNLER = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"]


def section_title(icon: str, text: str, tone: str = "", count=None, note: str = "") -> None:
    """Renkli bölüm başlığı (yalnız görünüm)."""
    st.markdown(f"<div class='sec {'t-' + tone if tone else ''}'><span>{icon}</span>{esc(text)}"
                + (f"<span class='cnt'>{count}</span>" if count is not None else "")
                + (f"<span class='note'>{esc(note)}</span>" if note else "") + "</div>", unsafe_allow_html=True)


def dollar(text: str) -> str:
    """Markdown'da iki "$" arası formül sayılıyor ("2.285 \\$ · bütçe 10 \\$" eğik ve bozuk görünüyordu): \\$'ları kaçır."""
    return re.sub(r"(?<!\\)\$", r"\\$", str(text))


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

# ---------------- Ayar değerleri (Aşama 3: ayar ekranı ayrı; her ekranda kayıtlı ayarlardan okunur) ----------------
_S = pipeline.load_settings()
_q_keys = list(config.QUALITY_PROFILES)
days = int(_S.get("kap_gun", 1)) if int(_S.get("kap_gun", 1)) in (1, 2, 3, 5, 7) else 1
analysis_limit = int(_S.get("panel_analiz_siniri", 10))
analysis_limit = analysis_limit if analysis_limit in (1, 3, 5, 10, 20, 30) else 10
window = min(30, max(3, int(_S.get("liste_pencere", 7))))
quality = _S.get("analiz_kalitesi", config.DEFAULT_QUALITY)
quality = quality if quality in _q_keys else config.DEFAULT_QUALITY
commission = float(_S.get("komisyon_pct", journal.DEFAULT_COMMISSION_PCT))
slippage = float(_S.get("kayma_pct", journal.DEFAULT_SLIPPAGE_PCT))
capital = float(_S.get("sermaye", 0.0))
risk_pct = float(_S.get("risk_pct", 0.0))
ai_budget = float(_S.get("yz_butce_usd", ai_comment.DEFAULT_BUDGET_USD))
news_budget = float(_S.get("haber_butce_usd", config.NEWS_BUDGET_USD))

PAGE_DASH, PAGE_FIRSAT, PAGE_HISSE, PAGE_TAKIP, PAGE_BEKCI = ("📊 Dashboard", "🎯 Fırsatlar", "🔍 Hisse Analizi",
                                                              "⭐ Takip Listem", "🛡️ Bekçi")
PAGE_HABER, PAGE_GUNLUK, PAGE_PERF, PAGE_AYAR = "📰 Haberler", "📒 İşlem Günlüğü", "🏁 Performans", "⚙️ Ayarlar"
PAGES = [PAGE_DASH, PAGE_FIRSAT, PAGE_HISSE, PAGE_TAKIP, PAGE_BEKCI, PAGE_HABER, PAGE_GUNLUK, PAGE_PERF, PAGE_AYAR]

# ---------------- Üst bant (her ekranda) ----------------
_today = datetime.now(config.TR_TZ)
tb1, tb2, tb3, tb4 = st.columns([5, 1.7, 1.4, 1.2], vertical_alignment="center")
tb1.markdown(
    "<div class='topbar'><span class='brand'>☄️ Halley</span><span class='tag'>Swing terminali</span>"
    f"<span class='meta'>📅 {_today.day} {['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'][_today.month - 1]} "
    f"{_today.year}, {GUNLER[_today.weekday()]} · 🕒 Son güncelleme: {esc(last_update_text())} · 🔒 Emir vermez, işlemi siz "
    "Midas'tan yaparsınız</span></div>", unsafe_allow_html=True)

if tb2.button("🔄 Haberleri güncelle", type="primary", width="stretch"):
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

_dark_new = tb4.toggle("🌙 Koyu", value=DARK, key="dark_mode",
                      help="Koyu renkli görünüm (göz yormaz). Seçim bu bilgisayarda saklanır.")
if _dark_new != DARK:
    pipeline.save_settings(karanlik_mod=bool(_dark_new))
    conn.close()
    st.rerun()

if tb3.button("🧪 Ücretsiz dene", width="stretch", key="free_check",
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

# ---------------- Sabit menü ----------------
if "_goto" in st.session_state:          # başka ekrandan gelen yönlendirme (ör. 🔍 Analiz → Hisse Analizi)
    _pg, _tk = st.session_state.pop("_goto")
    st.session_state["nav"] = _pg
    if _tk:
        st.session_state["hisse_pick"] = _tk
# Seçili ekran ayrıca saklanır: tema değişince yapılan yenilemede Streamlit menü seçimini unutuyordu (menüde
# "Fırsatlar" seçili görünürken Dashboard açılıyordu; 2026-11-09 görünüm kontrolünde bulundu).
if "nav" not in st.session_state and st.session_state.get("_page") in PAGES:
    st.session_state["nav"] = st.session_state["_page"]
with st.container(key="navbar"):
    PAGE = st.radio("Ekran", PAGES, horizontal=True, key="nav", label_visibility="collapsed")
st.session_state["_page"] = PAGE


def goto(page: str, ticker=None) -> None:
    st.session_state["_goto"] = (page, ticker)
    conn.close()
    st.rerun()


def go_button(label: str, page: str, key: str, ticker=None, **kw) -> None:
    if st.button(label, key=key, **kw):
        goto(page, ticker)


for _kind, _text in st.session_state.pop("_flash", []):
    {"error": st.error, "warning": st.warning, "success": st.success}.get(_kind, st.info)(dollar(_text))

if not pipeline.has_api_key():
    st.warning("Başlamak için OpenAI API anahtarınızı bir kez girin. Anahtar yalnızca bu bilgisayarda saklanır.")
    k1, k2 = st.columns([3, 1])
    key = k1.text_input("OpenAI API anahtarı", type="password", placeholder="sk-...", label_visibility="collapsed")
    if k2.button("Anahtarı kaydet", width="stretch") and key.strip():
        pipeline.save_api_key(key)
        conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
        st.rerun()

def update_apply(m: dict) -> None:
    """İndir → doğrula → dene → Halley'i yeniden başlat (dosya değişimini Halley.exe yapar)."""
    from bist_haber import guncelleme
    bar = st.progress(0.0, text="Güncelleme başlıyor…")
    try:
        guncelleme.hazirla(m, lambda p_, t_: bar.progress(min(p_, 1.0), text=t_))
        guncelleme.yeniden_baslat()
        st.success("✅ Güncelleme hazır. Halley birkaç saniye içinde kapanıp yeni sürümle açılacak; verileriniz korunur.")
    except Exception as e:
        st.error(f"Güncelleme yapılamadı: {nice_err(e)} Mevcut sürüm değişmedi.")


def update_banner() -> None:
    """2026-11-15: yeni sürüm varsa üstte bant (günde en fazla bir kez kontrol; ağ hatası paneli engellemez)."""
    from bist_haber import guncelleme
    if "_upd" not in st.session_state:
        try:
            st.session_state["_upd"] = guncelleme.kontrol()
        except Exception:
            st.session_state["_upd"] = {"durum": "hata"}
        son = guncelleme.son_islem()
        if son:
            st.session_state["_upd_son"] = son
            try:
                (guncelleme.kok() / "guncelleme" / "son_islem.json").unlink()
            except OSError:
                pass
    son = st.session_state.get("_upd_son")
    if son:
        msg = {"guncellendi": ("success", f"✅ Halley güncellendi: {son.get('surum', '')}. Verileriniz korundu."),
               "geri_donuldu": ("info", f"↩️ Önceki sürüme dönüldü: {son.get('surum', '')}."),
               "otomatik_geri_donuldu": ("warning", f"⚠️ Yeni sürüm açılamadığı için önceki sürüme dönüldü "
                                                    f"({son.get('surum', '')}). Sorunu bildirin."),
               "hata": ("warning", "⚠️ Güncelleme uygulanamadı; mevcut sürümle devam ediliyor.")}.get(son.get("islem"))
        if msg:
            getattr(st, msg[0])(msg[1])
    u = st.session_state["_upd"]
    if u.get("durum") == "yeni":
        with st.container(border=True, key="upd_box"):
            c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
            c1.markdown(f"🆕 **Yeni Halley sürümü var: {esc(u.get('yeni') or '')}** "
                        f"<span class='news-meta'>(kurulu: {esc(u.get('kurulu') or '')})</span>"
                        + (f"  \n{esc(u['notlar'])}" if u.get("notlar") else ""), unsafe_allow_html=True)
            if c2.button(f"🔄 Güncelle ({u.get('boyut_mb', 0):g} MB)", key="upd_go", type="primary", width="stretch",
                         help="Yalnız uygulama kodu iner; verileriniz, ayarlarınız ve API anahtarınız değişmez. "
                              "Halley kendini yeniden başlatır. Sorun çıkarsa önceki sürüme dönülür."):
                update_apply(guncelleme.manifest())
    elif u.get("durum") == "tam_kurulum":
        st.caption(f"🆕 Yeni Halley sürümü var ({esc(u.get('yeni') or '')}), ama {esc(u.get('neden', ''))}: uygulama "
                   f"içinden güncellenemez. Yeni kurulum dosyasını [güncelleme sayfasından]({u.get('sayfa')}) indirip "
                   "**Güncelle** ile kurun; verileriniz korunur.")
    elif u.get("durum") == "bekliyor":
        st.caption("🔄 Bir güncelleme hazır bekliyor; Halley yeniden açıldığında uygulanır.")


update_banner()

if not conn.execute("SELECT 1 FROM news LIMIT 1").fetchone():
    st.info("🆕 Halley yeni kurulmuş görünüyor. Başka bilgisayardan veri taşıyorsanız: **⚙️ Ayarlar → 💾 Veri ve gelişmiş → "
            "İçe aktar**.")

last = st.session_state.get("last_result", {})
if last.get("free"):
    est = last.get("estimate", {})
    new_kap = last.get("kap", {}).get("new", 0)
    new_rss = last.get("rss", {}).get("new", 0)
    st.info(f"🧪 Ücretsiz deneme tamamlandı — yapay zekâ çağrılmadı, kredi harcanmadı. "
            f"KAP'ta {new_kap}, haber sitelerinde {new_rss} yeni kayıt bulundu. "
            f"Sırada {est.get('waiting', 0)} haber var; bir sonraki **Haberleri güncelle** bunların "
            f"{est.get('next_count', 0)} tanesini analiz eder (tahmini maliyet "
            f"{est.get('low_usd', 0):.3f}–{est.get('high_usd', 0):.3f} \\$).")
if last:
    if last.get("kap", {}).get("rate_limited"):
        st.warning("KAP geçici olarak istek sınırı uyguladı; kalan bildirimler arka planda, sınır kalkınca "
                   "kendiliğinden okunuyor (aşağıdaki durum kutusu). Tekrar basmanız gerekmez.")
    an = last.get("analyze", {})
    if an.get("errors"):
        st.error(f"{an['errors']} haber analiz edilemedi. Ayrıntı: ⚙️ Ayarlar → Veri ve gelişmiş.")
    if an.get("waiting"):
        st.caption(f"{an['waiting']} haber bir sonraki güncellemeyi bekliyor.")
    if an.get("tekrar"):
        st.caption(f"{an['tekrar']} haber daha önce analiz edilmiş bir haberin tekrarı olduğu için yapay zekâya "
                   "gönderilmedi (ücretlendirilmedi).")
    if an.get("rutin") or last.get("rutin"):
        st.caption(f"{an.get('rutin') or last.get('rutin')} rutin haber (izahname, günlük geri alım raporu, piyasa bülteni gibi) Python ön "
                   "elemesiyle yapay zekâya gönderilmedi (ücretlendirilmedi). Haberler'de 'Atlandı' olarak görünür; "
                   "önemli bulduğun biri olursa 🔬 analiz bölümünde '🧹' işaretiyle seçip analiz ettirebilirsin.")
    if last.get("rss", {}).get("failed_feeds"):
        st.caption("Bazı haber siteleri okunamadı. Ayrıntı: ⚙️ Ayarlar → Veri ve gelişmiş.")

# ---------------- Durum kutuları (her ekranda; yalnız iş sürerken görünür) ----------------
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
        st.info(f"🔬 {tur.capitalize()} sürüyor: {k}/{n} haber · şu ana kadar ≈ {s_.get('harcanan_usd', 0):.3f} \\$ · "
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
            f"🔬 Son {tur} ({s_['bitti'][11:16]}): {text_} · gerçek maliyet ≈ {s_.get('harcanan_usd', 0):.3f} \\$"
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

rows = report.build(conn, uni, days=window)
positives = [r for r in rows if r["score"] >= 1.5]
negatives = [r for r in rows if r["score"] <= -1.5]
neutrals = [r for r in rows if -1.5 < r["score"] < 1.5]

# W1: panel ve bekçi aynı hesabı kullanır (bist_haber/signals.py)
CTX = signals.Context(conn)


def tech(ticker: str):
    """Teknik göstergeler (kodla hesaplanır, kredi harcamaz). Sayfa çiziminde bir kez hesaplanır."""
    return CTX.tech(ticker)


def _n(v, fmt="{:.2f}"):
    return "—" if v is None else fmt.format(v)


CHART_PERIODS = {"3 ay": 63, "6 ay": 126, "1 yıl": 250}


def chart_block(tk: str, t=None, scenario_: dict = None, ready_row: dict = None, key: str = "") -> None:
    """2026-11-15 Aşama 5: mum grafiği + hacim + EMA + plan seviyeleri + olası fiyat aralığı konisi (YZ yok)."""
    k = key or tk
    c1, c2, c3 = st.columns([1.6, 1.6, 3], vertical_alignment="center")
    per = c1.radio("Dönem", list(CHART_PERIODS), index=1, horizontal=True, key=f"ch_p_{k}")
    hor = c2.radio("Koni (işlem günü)", [5, 10, 20], index=1, horizontal=True, key=f"ch_h_{k}")
    df = chart.history(conn, tk, CHART_PERIODS[per])
    if df.empty or len(df) < 5:
        st.caption("📈 Grafik için yeterli fiyat geçmişi yok.")
        return
    sigma = chart.daily_vol(chart.history(conn, tk, chart.VOL_DAYS + 5))
    cdf = chart.cone(float(df["close"].iloc[-1]), df["date"].iloc[-1].date(), sigma, int(hor))
    best = None
    if not ready_row and scenario_:
        g = scenario_.get("girisler") or scenario_
        best = next((x for x in g.get("senaryolar", []) if x["tur"] == g.get("en_uygun")), None)
    lv = chart.plan_levels(t, best, ready_row)
    fig = chart.figure(df, cdf, lv, dark=DARK)
    if fig is not None:
        st.altair_chart(fig, use_container_width=True, theme=None)    # renkler karanlık mod ayarından (chart.figure)
    src = ("hazır fırsat planı" if ready_row else f"en uygun giriş senaryosu ({best['ad']})" if best else
           "plan yok; yalnız destek/direnç")
    c3.caption(f"Seviyeler: {src}. Mavi koni = olası fiyat aralığı (koyu %50, açık %80).")
    st.caption("📈 " + chart.cone_text(chart.cone_summary(cdf), lv)
               + " Koni **yön tahmini değildir**: yükseliş ya da düşüş varsaymaz, yalnız hissenin kendi geçmiş "
               "oynaklığından hesaplanır (olağandışı haber/olayda aralık aşılabilir). Mumlar: yeşil yükselen, kırmızı "
               "düşen gün; çizgiler EMA 20/50/200; kesikli yatay çizgiler giriş, SL, TP1, TP2 ve 20 günlük destek/"
               "direnç" + ("; gri bant giriş aralığı (üst kenar azami giriş)." if ready_row else "."))


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
        st.caption("ℹ️ Bu, Halley'in önerdiği plan: fiyat gösterilen **giriş koşuluna gelince** alım. 🎯 Fırsatlar ve "
                   "Dashboard'da görünen **risk bu senaryonun riskidir**. Aşağıdaki «Mevcut fiyattan girilirse» bölümü ise "
                   "hemen şimdi almayı gösterir; riski farklı olabilir.")
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
        st.caption("Kutulardaki yüzdeler: seviyenin giriş fiyatına uzaklığı; «fiyattan» yazan, girişin bugünkü fiyata "
                   "uzaklığı (+ ise fiyatın o kadar yükselmesi beklenir). Risk/getiri 1 : 2,5 = olası kazanç olası zararın "
                   "2,5 katı (1'in altı elverişsiz).")
        st.caption(f"**Senaryo riski: {best.get('risk_seviyesi', '—')}** — 🎯 Fırsatlar'da görünen risk budur (ortak risk faktörleri + "
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
        st.caption("Üç senaryo türü: **Kırılım** = fiyat direncin üstünde kapanınca ertesi gün alım · **Geri çekilme** = "
                   "yükseliş trendinde ortalamaya inince alım · **Destekten tepki** = desteğe yakın alım. *Durum*: iyi / "
                   "zayıf / elverişsiz = risk/getiri kalitesi; açıklama yazanlar şu an uygulanamaz (nedeni yazar). *Risk*: "
                   "o senaryonun risk seviyesi.")
    st.caption("📏 " + entries.BACKTEST_NOTE)


def scenario_block(p: dict) -> None:
    if p.get("girisler"):
        entry_block(p["girisler"])
    st.markdown("**🎯 Mevcut fiyattan girilirse (referans)** <span class='news-meta'>(tahmini; yatırım tavsiyesi "
                "değildir)</span>", unsafe_allow_html=True)
    st.caption("ℹ️ Bu bölüm, hisseyi **bugün, son fiyattan** alsaydınız ne olurdu sorusunun cevabıdır (karşılaştırma "
               "için). Buradaki risk, yukarıdaki giriş senaryosunun riski DEĞİLDİR: şimdi almak çoğu zaman daha risklidir, "
               "çünkü zarar durdur uzak ya da hedef yakın olabilir.")
    if p["durum"] != "senaryo":
        st.caption(p["neden_yok"])
        if p["riskler"]:
            st.markdown("Risk notları:\n" + "\n".join(f"- {esc(x)}" for x in p["riskler"]))
        return
    if p.get("elverissiz"):
        st.warning("Mevcut seviyelerde risk/getiri elverişsiz: olası zarar olası kazançtan büyük.")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Referans (son fiyat)", f"{p['giris']:.2f} TL")
    c2.metric("Zarar durdur (SL)", f"{p['sl']:.2f} TL", f"{p['sl_%']:+.1f}%")
    c3.metric("Kâr al (TP)", f"{p['tp']:.2f} TL", f"{p['tp_%']:+.1f}%")
    c4.metric("Risk / getiri", f"1 : {p['rr']:.1f}" if p["rr"] else "—")
    d1, d2 = st.columns(2)
    d1.metric("Tahmini vade", f"{p['vade'][0]}–{p['vade'][1]} işlem günü")
    d2.metric("Risk (şimdi alınırsa)", p["risk_seviyesi"].capitalize(),
              help="Hemen şimdi, son fiyattan alımın riski. Fırsatlardaki risk ise giriş senaryosunun riskidir.")
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
               f"{r['news_count']} haber. Haber skoru: haberlerin yönü, etkisi ve güveninden hesaplanır, haber eskidikçe "
               "azalır (+1,50 ve üstü olumlu sinyal, −1,50 ve altı olumsuz). Emir vermeden önce haberin kendisini okuyun.")
    rr_ = next((x for x in READY_ACTIVE if x["ticker"] == r["ticker"]), None)
    chart_block(r["ticker"], tech(r["ticker"]), scenario(r), rr_, key=f"sd_{r['ticker']}")
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
        _stock_rows(items, tone)
def pending_score(r: dict):
    """Bekleyen senaryonun genel fırsat puanı (en uygun giriş senaryosuna göre; yoksa None). Yalnız bilgi."""
    p = scenario(r)
    g = p.get("girisler") or {}
    s = next((x for x in g.get("senaryolar", []) if x["tur"] == g.get("en_uygun")), None)
    t = tech(r["ticker"])
    if not s or not t:
        return None
    return ready.overall_score(r["score"], ready.tech_score(t)["skor"], s["rr1"], s.get("risk_seviyesi", "orta"))["puan"]


def _stock_rows(items: list, tone: str = "neu") -> None:
    """Aşama 3: liste satırı kısa; ayrıntılı analiz ayrı ekranda açılır (🔍 Analiz → Hisse Analizi)."""
    for r in items:
        reason = (r["last_news"] or "").strip()
        reason = reason if len(reason) <= 90 else reason[:88].rstrip() + "…"
        badge = check_badge(r.get("flags", ""))
        with st.container(border=True, key=f"row_{tone}_{r['ticker']}"):
            a, b, c, d = st.columns([1.2, 5.2, 1.3, 1.6], vertical_alignment="center")
            gp = pending_score(r) if tone == "pos" else None
            a.markdown(f"**{r['ticker']}**  \n<span class='news-meta'>skor {r['score']:+.2f}"
                       + (f" · puan {gp}/100" if gp is not None else "") + "</span>", unsafe_allow_html=True)
            b.markdown(f"{esc(r['name'])} · {esc(reason)}  \n<span class='news-meta'>{esc(badge)}"
                       f"{' · ' if badge else ''}{esc(technical.short_label(tech(r['ticker'])))}</span>",
                       unsafe_allow_html=True)
            with c:
                go_button("🔍 Analiz", PAGE_HISSE, f"an_{r['ticker']}", r["ticker"], width="stretch")
            with d:
                takip_ui.follow_button(conn, r["ticker"], f"list_{r['ticker']}", compact=True)


def news_cards(ticker: str, limit: int = 5) -> None:
    rows_ = conn.execute("SELECT i.*, n.title, n.url, n.source, n.note FROM impacts i JOIN news n ON n.id=i.news_id "
                         "WHERE i.ticker=? ORDER BY i.published_at DESC LIMIT ?", (ticker, limit)).fetchall()
    st.markdown("**📰 Haberler ve analiz**")
    if not rows_:
        st.caption("Bu hisse için analiz edilmiş haber yok.")
    for i in rows_:
        cls, word = DIR_TR[i["direction"]]
        source = esc(config.RSS_SOURCE_LABELS.get(i["source"].replace("rss:", ""), i["source"].upper()))
        st.markdown(
            f"<div class='news-card'><div class='news-meta'>{i['published_at'][:16].replace('T', ' ')} · {source}</div>"
            f"<span class='chip {cls}'>{word} · etki {impact_word(i['magnitude'])}</span>"
            f"<div style='margin-top:6px'><b>{esc(i['title'])}</b></div><div>{esc(i['note'] or '')}</div>"
            f"<div class='news-meta' style='margin-top:6px'>Neden: {esc(i['reason'] or '-')} · "
            f"<a href='{esc(i['url'] or '')}' target='_blank'>haberin kaynağını aç</a></div></div>",
            unsafe_allow_html=True)


def generic_details(ticker: str) -> None:
    """Haber skoru olmayan hisse (ör. takip için seçilen): senaryolar yalnız fiyat verisinden, takip bekçisiyle aynı
    kural (tracker.scenario_guard + entries.scenarios). Haber skoru şartı aranmaz."""
    t = tech(ticker)
    st.caption("Bu hissede son günlerde olumlu/olumsuz haber kaydı yok: aşağıdaki giriş senaryoları yalnız fiyat "
               "verisinden hesaplandı (haber skoru şartı aranmadı). Takibe alırsanız bekçi bu senaryoları izler.")
    why = tracker.scenario_guard(t)
    rr_ = next((x for x in READY_ACTIVE if x["ticker"] == ticker), None)
    chart_block(ticker, t, None if why or not t else entries.scenarios(t), rr_, key=f"gd_{ticker}")
    if why:
        st.warning(why)
    elif t:
        entry_block(entries.scenarios(t))
    technical_block(t)
    st.caption("🏭 Sektör: " + sectors.compare_text(sectors.compare(conn, ticker)))
    st.caption("📑 Bilanço takvimi: " + earnings.describe(earning(ticker)))
    timeline_block(ticker)
    financial_block(ticker)
    news_cards(ticker)


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
    st.caption("🔎 " + calendar_sync.summary_line() + " — yenilemek için: ⚙️ Ayarlar → Veri ve gelişmiş → Takvim kontrolü.")


AYLAR = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım", "Aralık"]

# Panelin "uygun" senaryoları sanal işlem olarak günlüğe yazılır (Parça C1) — her ekranda, önceki davranışla aynı
SUMMARY = tradeplan.opportunity_summary({r["ticker"]: scenario(r) for r in positives})
for r in positives:
    t_rec = tech(r["ticker"])
    if t_rec:
        journal.record_auto(conn, r["ticker"], scenario(r), t_rec["tarih"], r["score"])
if rows:
    journal.update_all(conn, commission, slippage)


def _opp_why(tk: str) -> str:
    """Listeden çıkan hissenin nedeni (panel ve bekçiyle aynı karar kodu)."""
    r = next((x for x in rows if x["ticker"] == tk), None)
    if r is None:
        return f"son {window} günün haber listesinden çıktı (haber penceresi dışında kaldı)"
    d = signals.decide(CTX, r)
    if d["neden_kodu"] == "SKOR_ESIK_ALTI":
        return f"haber skoru {r['score']:.2f}'e indi (en az 1,50 gerekir; haber eskidikçe skor azalır)"
    return d["neden"] + (f" — {d['detay']['neden_yok']}" if d.get("detay", {}).get("neden_yok") else "")


firsat_log.record([tk for tk, _, _ in SUMMARY["uygun"]], _opp_why)

# 2026-11-10 Hazır Fırsatlar: akşam/sabah analizinde kaydedilen planlar (bist_haber/ready.py)
if not st.session_state.get("_model_doldur"):     # 2026-11-15: güncellemeden önceki açık fırsatlara model olasılığı
    st.session_state["_model_doldur"] = True
    try:
        ready.fill_missing_model(conn)
    except Exception:  # gösterim yardımcısı; panel açılışını asla engellemesin
        pass
READY_ROWS = ready.current(conn)
READY_ACTIVE = [r for r in READY_ROWS if r["durum"] in ("aday", "onaylandi", "giris")]
READY_NEWS = [r for r in READY_ACTIVE if r["kaynak"] != "teknik"]      # 2026-11-14 Aşama 4
READY_TECH = [r for r in READY_ACTIVE if r["kaynak"] == "teknik"]


def news_line(tk: str) -> str:
    """Kart için son yönlü haberin özeti ve etkisi (kayıtlı analizden; yapay zekâ çağrılmaz)."""
    i = conn.execute("SELECT i.direction, i.magnitude, i.confidence, i.published_at, n.note, n.title FROM impacts i "
                     "JOIN news n ON n.id=i.news_id WHERE i.ticker=? AND i.direction!=0 ORDER BY i.published_at DESC "
                     "LIMIT 1", (tk,)).fetchone()
    if not i:
        return "📰 Bu hisse için analiz edilmiş yönlü haber yok."
    text = (i["note"] or i["title"] or "").strip()
    text = text if len(text) <= 260 else text[:257].rsplit(" ", 1)[0] + "…"
    return (f"📰 **Haber ({i['published_at'][8:10]}.{i['published_at'][5:7]}):** {text} · "
            f"**{DIR_TR[i['direction']][1].lower()}**, etki {impact_word(i['magnitude'])}"
            + (f", güven %{i['confidence'] * 100:.0f}" if i["confidence"] is not None else ""))
NAMES_ALL = {r["ticker"]: r["name"] for r in conn.execute("SELECT ticker, name FROM companies")}


def model_line(r: dict) -> str:
    """Aşama 6: öneri anında kaydedilen model olasılığı (gizli kayıt). Ayar kapalıysa ya da kayıt yoksa boş."""
    if not pipeline.load_settings().get("model_olasilik_goster", False) or not r.get("model_json"):
        return ""
    try:
        m = json.loads(r["model_json"])
    except ValueError:
        return ""
    if m.get("olasilik") is None:
        return ""
    sim = (f" · geçmişte benzer {m['benzer_n']} durumda %{100 * m['benzer_oran']:.0f}"
           if m.get("benzer_n") and m.get("benzer_oran") is not None else "")
    return (f"🎯 **TP1'e SL'den önce ulaşma olasılığı (model): %{100 * m['olasilik']:.0f} — {m.get('bant', '?')}**{sim}. "
            "Yalnız bilgi: yalnız teknik veriden (haber hesaba katılmaz); geçmişte söylediği oranlar biraz iyimser çıktı.")


def ready_card(r: dict) -> None:
    tk = r["ticker"]
    pct = lambda v: f"{(v / r['giris'] - 1) * 100:+.1f}%"
    with st.container(border=True, key=f"rc_{r['id']}"):
        h1, h2, h3 = st.columns([4.2, 1.3, 1.5], vertical_alignment="center")
        when = f"{r['giris_gunu'][8:10]}.{r['giris_gunu'][5:7]} açılış"
        h1.markdown(f"**{tk}** · {esc(NAMES_ALL.get(tk, ''))}  \n<span class='news-meta'>{esc(ready.TYPE_NAMES.get(r['tur'], r['tur']))}"
                    f" · {esc(ready.STATE_TR.get(r['durum'], r['durum']))} · giriş: {when}</span>", unsafe_allow_html=True)
        with h2:
            go_button("🔍 Analiz", PAGE_HISSE, f"rc_an_{r['id']}", tk, width="stretch")
        with h3:
            takip_ui.follow_button(conn, tk, f"ready_{r['id']}", compact=True)
        c = st.columns(6)
        c[0].metric("Kapanış", f"{r['kapanis']:.2f}")
        c[1].metric("Giriş aralığı", f"{r['giris_alt']:.2f}–{r['azami_giris']:.2f}")
        c[2].metric("Azami giriş", f"{r['azami_giris']:.2f}", "üstünde ALMA", delta_color="off")
        c[3].metric("Zarar durdur", f"{r['sl']:.2f}", pct(r["sl"]))
        c[4].metric("TP1", f"{r['tp1']:.2f}", pct(r["tp1"]))
        c[5].metric("TP2", f"{r['tp2']:.2f}", pct(r["tp2"]))
        teknik_ = r["kaynak"] == "teknik"
        gp = ready.overall_score(r["haber_skoru"], r["teknik_skor"], r["rr1"], r["risk"], r["kaynak"])
        st.caption(f"Risk/getiri **1:{r['rr1']:.1f}** · tahmini getiri TP1 {pct(r['tp1'])}, TP2 {pct(r['tp2'])} · tahmini "
                   f"tutma {r['vade_lo']}–{r['vade_hi']} işlem günü · "
                   + ("haber yok (yalnız teknik)" if teknik_ or r["haber_skoru"] is None
                      else f"haber skoru {r['haber_skoru']:.2f}")
                   + f" · teknik skor {r['teknik_skor']}/10 · risk **{r['risk']}** · geçerlilik: yalnız {when} (açılış "
                   "azami girişin altındaysa; üstündeyse fırsat iptal olur)"
                   + (f" · açılış {r['acilis']:.2f}" if r.get("acilis") else ""))
        st.caption(f"🧮 **Genel fırsat puanı {gp['puan']}/100** — haber {gp['parca']['haber']:.0f}/30 · teknik "
                   f"{gp['parca']['teknik']:.0f}/30 · risk/getiri {gp['parca']['risk_getiri']:.0f}/20 · risk "
                   f"{gp['parca']['risk']:.0f}/20. Yalnız bilgi: seçimi ve sırayı değiştirmez; 5 yıllık geçmiş sınamada TP1'i öngörmedi (yazı-tura düzeyi)."
                   + (" Yalnız teknik fırsatta haber puanı 0'dır (en fazla 70)." if teknik_ else ""))
        ml = model_line(r)
        if ml:
            st.caption(ml)
        if not teknik_:
            st.caption(news_line(tk))
        st.caption("Neden: " + r["neden"])
        with st.expander("📈 Grafik ve olası fiyat aralığı"):
            chart_block(tk, tech(tk), None, r, key=f"rc_{r['id']}")


def ready_when_text() -> str:
    if not READY_ROWS:
        return "henüz kayıtlı liste yok"
    g = READY_ROWS[0]["giris_gunu"]
    an = "sabah kontrolünden geçti" if any(r["durum"] == "onaylandi" for r in READY_ROWS) else "akşam analizi"
    return f"giriş günü {g[8:10]}.{g[5:7]} · {an}"


def ready_section() -> None:
    """Hazır Fırsatlar: koşulu sağlanmış, açılışta uygulanabilir planlar (önce gösterilir)."""
    with st.container(border=True, key="r_box"):
        section_title("✅", "Hazır Fırsatlar", "pos", len(READY_NEWS), ready_when_text())
        st.caption("Koşulu analiz anında **zaten sağlanmış** planlar: akşam analizi (kapanıştan sonra) ertesi işlem günü "
                   "için seçer, sabah kontrolü açılıştan önce yeniden değerlendirir (kötü haber, bozulan plan → iptal). "
                   "**Açılış azami girişin üstündeyse almayın**; bekçi açılıştan sonra kontrol edip Telegram'dan bildirir. "
                   "En fazla 5 hisse; uygun yoksa liste boş kalır.")
        if READY_NEWS:
            for r in READY_NEWS:
                ready_card(r)
        else:
            st.info("Şu an geçerli haberli hazır fırsat yok. Akşam analizi kapanıştan ~20 dakika sonra (Halley açıksa "
                    "kendiliğinden) yeni liste hazırlar. Liste sırf dolsun diye hisse önerilmez.")
        section_title("📐", "Yalnız teknik fırsatlar", "", len(READY_TECH), "haber desteği yok · ayrı ölçülür")
        st.caption("Olumlu haberi **olmayan** likit hisselerden, yalnız fiyat verisiyle aynı \"koşulu sağlanmış plan\" "
                   "kuralıyla seçilir; şart daha sıkıdır (teknik skor en az 7/10 ve yükseliş trendi; son haberi olumsuz "
                   "olanlar alınmaz). Haber desteği olmadığı için haberli fırsatlardan **sonra** gelir ve sonuçları "
                   "🏁 Performans'ta ayrı ölçülür. Kurallar yeni, henüz sınanmadı.")
        if READY_TECH:
            for r in READY_TECH:
                ready_card(r)
        else:
            st.caption("Şu an yalnız teknik fırsat yok (akşam analizinde yeniden aranır).")
        gone = [r for r in READY_ROWS if r["durum"] in ("iptal", "girissiz")]
        if gone:
            with st.expander(f"⛔ İptal edilenler ({len(gone)})"):
                for r in gone:
                    st.caption(f"**{r['ticker']}** — {r['iptal_nedeni'] or ready.STATE_TR.get(r['durum'])}")
        b1, b2, b3 = st.columns([1.6, 2.2, 1.8], vertical_alignment="center")
        if b1.button("🔄 Şimdi yeniden hesapla (kaydetmeden)", key="hz_live", width="stretch",
                     help="Kayıtlı fiyat ve haberlerle hazır fırsat kuralını şimdi çalıştırır; sonuç yalnız gösterilir, "
                          "kaydedilmez ve performansa girmez (kayıtlı liste akşam/sabah analizinde oluşur)."):
            sel = ready.select(conn, CTX, rows)
            with st.spinner("Yalnız teknik fırsatlar için tüm hisseler taranıyor (~10 sn)..."):
                tsel = ready.select_tech(conn, CTX, rows, uni)
            st.session_state["ready_live"] = {"zaman": datetime.now(config.TR_TZ).strftime("%H:%M"),
                                              "secilen": sel["secilen"], "elenen": sel["elenen"],
                                              "teknik": tsel["secilen"]}
            conn.close()
            st.rerun()
        saved_ = pipeline.load_settings()
        ai_on = b2.toggle("🤖 Sabah kontrolünde bu hisselerin gece haberlerini yapay zekâyla analiz et", key="hz_ai",
                          value=bool(saved_.get("hazir_sabah_yz", False)),
                          help="Varsayılan KAPALI. Açarsanız sabah kontrolü, yalnız hazır listedeki 1–5 hissenin akşamdan "
                               "bu yana gelen KAP haberlerini analiz eder (haber başına ~0,013 \\$, aylık haber bütçesini "
                               "aşmaz). Kapalıyken yalnız önceden analiz edilmiş haberler kontrol edilir.")
        if ai_on != bool(saved_.get("hazir_sabah_yz", False)):
            pipeline.save_settings(hazir_sabah_yz=ai_on)
        pend = [r for r in READY_ACTIVE if r["durum"] in ("aday", "onaylandi")]
        if b3.button("🤖 Yeni haberlerini şimdi analiz et", key="hz_ai_now", width="stretch",
                     disabled=not (pend and pipeline.has_api_key()),
                     help="Hazır listedeki hisselerin akşamdan bu yana gelen KAP haberlerini şimdi bir kez analiz eder "
                          f"(en fazla {len(pend)} hisse; haber başına ~0,013 \\$, bütçe içinde). Olumsuz haber çıkan "
                          "fırsat iptal edilir."):
            before = analyzer.month_spend(conn)
            with st.spinner("Hazır fırsatların yeni haberleri okunuyor ve analiz ediliyor..."):
                try:
                    g = ready.news_guard(conn, pend, datetime.now(config.TR_TZ), analyze=True)
                    an = g.get("analiz") or {}
                    flash("success", f"Haber kontrolü tamam: {an.get('metin', 0)} yeni metin, "
                                     f"{(an.get('analiz') or {}).get('analyzed', 0) if isinstance(an.get('analiz'), dict) else 0} analiz, "
                                     f"maliyet ≈ {analyzer.month_spend(conn) - before:.3f} $."
                                     + (f" Olumsuz haber nedeniyle iptal: {', '.join(g['iptal'])}." if g["iptal"] else
                                        " Olumsuz haber çıkmadı."))
                except Exception as e:
                    flash("error", f"Haber kontrolü tamamlanamadı: {nice_err(e)}")
            conn.close()
            st.rerun()
        if not pipeline.has_api_key():
            b3.caption("API anahtarı yok.")
        live = st.session_state.get("ready_live")
        if live:
            st.markdown(f"**Anlık hesap ({live['zaman']}) — kaydedilmedi:** {len(live['secilen'])} haberli hisse hazır görünüyor"
                        + (": " + ", ".join(p["ticker"] for p in live["secilen"]) if live["secilen"] else "."))
            both = live["secilen"] + live.get("teknik", [])
            if live.get("teknik"):
                st.markdown(f"📐 Yalnız teknik: {', '.join(p['ticker'] for p in live['teknik'])}")
            if both:
                st.dataframe(dash_cells(pd.DataFrame([{
                    "Hisse": p["ticker"], "Kaynak": ready.KAYNAK_TR[p.get("kaynak", "haber")],
                    "Tür": ready.TYPE_NAMES[p["tur"]], "Kapanış": p["kapanis"],
                    "Azami giriş": p["azami_giris"], "SL": p["sl"], "TP1": p["tp1"], "TP2": p["tp2"], "R/G": p["rr1"],
                    "Teknik": str(p["teknik_skor"]), "Risk": p["risk"], "Genel puan": str(p.get("genel_puan", "—"))}
                    for p in both]),
                    ["Kapanış", "Azami giriş", "SL", "TP1", "TP2", "R/G"]), hide_index=True, width="stretch")
            with st.expander(f"Neden diğerleri hazır değil? ({len(live['elenen'])} hisse)"):
                st.dataframe(pd.DataFrame([{"Hisse": k, "Neden": v} for k, v in sorted(live["elenen"].items())]),
                             hide_index=True, width="stretch")

# ---------------- İşlem günlüğü ----------------
JOURNAL_COLS = {   # tablo başlığının üstüne gelince çıkan açıklamalar
    "Tür": st.column_config.Column(help="Sanal: Halley'in kendi önerisini izlediği işlem (siz almadınız). Gerçek: sizin "
                                        "«Bu işleme girdim» ile kaydettiğiniz işlem."),
    "Sinyal günü": st.column_config.Column(help="Senaryonun hesaplandığı fiyat günü; sonraki günler değerlendirilir."),
    "Giriş": st.column_config.Column(help="Planlanan alış fiyatı"),
    "SL": st.column_config.Column(help="Zarar durdur (stop loss)"),
    "TP1": st.column_config.Column(help="İlk hedef: yarısı satılır, stop giriş fiyatına çekilir"),
    "TP2": st.column_config.Column(help="İkinci hedef: kalan yarı satılır"),
    "Durum": st.column_config.Column(help="bekliyor: giriş olmadı · açık: alındı, izleniyor · açık (TP1 görüldü): yarısı "
                                          "satıldı · kapandı: bitti · iptal: süresinde giriş olmadı"),
    "Sonuç": st.column_config.Column(help="TP2 / SL / başabaş (TP1 sonrası) / süre doldu / gerçekleşmedi"),
    "Net %": st.column_config.Column(help="Komisyon ve kayma düşülmüş getiri; açık işlemde son kapanışa göre"),
    "R": st.column_config.Column(help="Kazancın planlanan zarara (giriş − SL) oranı: +1R = planlanan zarar kadar kazanç"),
}


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
    st.caption("Kazanma oranı: kârla kapanan işlem yüzdesi · Ortalama net: maliyet düşülmüş ortalama getiri · "
               "Ortalama R: kazancın planlanan zarara oranı (+1 = planlanan zarar kadar kazanç) · Kâr faktörü: toplam "
               "kazanç / toplam zarar (1'in üstü kârlı) · Maks. düşüş: arka arkaya kayıpların en kötü toplamı (R) · "
               "Sharpe: getirinin oynaklığa oranı (yüksek = daha istikrarlı).")
    if not m["yeterli_ornek"]:
        st.warning(f"Yalnız {m['kapanan']} kapanan işlem var: {journal.MIN_TRADES_FOR_STATS}'dan az örnekte bu oranlar "
                   "rastlantıdan ayırt edilemez; karar için kullanmayın.")

# ---------------- Haberler ----------------
def news_analysis_box() -> None:
    """🔬 Haber analizi (kullanıcı isteği 2026-11-09): kaç haber, hangileri, tahmini maliyet; ve analiz edilmiş haberi
    derin yeniden inceleme. Her ikisi aylık haber analizi bütçesine tabidir."""
    st.markdown("#### 🔬 Haber analizi")
    spent = analyzer.month_spend(conn)
    st.caption(f"Bu ay haber analizine harcanan ≈ {spent:.3f} \\$ · bütçe {news_budget:.2f} \\$ · kalan "
               f"{max(0.0, news_budget - spent):.3f} \\$ (Ayarlar'dan değişir). Tahminler bu bilgisayardaki gerçek analiz "
               "maliyetlerinden hesaplanır; gerçek tutar haberin uzunluğuna göre değişir.")
    if not pipeline.has_api_key():
        st.info("Analiz için OpenAI API anahtarı gerekir (sayfanın üstünden girin).")
    mode = st.radio("Ne yapılsın?", ["🆕 Bekleyen haberleri analiz et", "🔁 Analiz edilmiş haberi derin yeniden incele"],
                    horizontal=True, key="na_mode")
    if mode.startswith("🆕"):
        pend = analyzer.pending(conn)
        with_rutin = st.checkbox("Python ön elemesinin rutin sayıp atladığı haberleri de göster", value=False,
                                 key="na_rutin")
        st.caption("Ön eleme izahname, günlük geri alım raporu, piyasa bülteni gibi yorum gerektirmeyen haberleri yapay "
                   "zekâya göndermez (ücret harcanmaz). Önemli olduğunu düşündüğün biri varsa buradan seçip analiz "
                   "ettirebilirsin.")
        if with_rutin:
            pend = pend + [r for r in conn.execute(
                "SELECT * FROM news WHERE status='skipped' AND note LIKE 'Python ön eleme:%' AND body IS NOT NULL "
                "AND TRIM(body)!='' ORDER BY published_at DESC").fetchall()]
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
                          "Başlık": ("🧹 " if r["status"] == "skipped" else "") + (r["title"] or "")[:90],
                          "_id": r["id"]})
        f1, f2, f3 = st.columns([1, 2, 1])
        tk = f1.text_input("Hisse kodu (süz)", key="na_ticker").strip().upper()
        groups = f2.multiselect("Öncelik grubu", list(analyzer.PRIORITY_LABELS.values()),
                                default=list(analyzer.PRIORITY_LABELS.values())[:2], key="na_groups")
        old_too = f3.checkbox(f"{config.AUTO_ANALYSIS_MAX_AGE_DAYS} günden eski haberler de", value=False, key="na_old")
        view = [x for x in rows_ if (not tk or tk in x["Hisse"].split(",")) and x["Öncelik"] in groups
                and (old_too or x["Yaş (gün)"] <= config.AUTO_ANALYSIS_MAX_AGE_DAYS)]
        n_rut = sum(1 for r in pend if r["status"] == "skipped")
        st.caption(f"Bekleyen {len(pend) - n_rut} haber" + (f" + ön elemenin atladığı {n_rut} haber (🧹)" if n_rut else "")
                   + f" · süzgeçten geçen {len(view)} (öncelik sırasıyla; en üstteki önce)")
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
        st.info(f"Seçilen {len(sel)} haber · tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} \\$"
                + (f" · bütçe nedeniyle yalnız ilk {len(fit)} haber analiz edilir ({over} haber kalır)" if over else ""))
        if st.button(f"🔬 {len(fit)} haberi analiz et", key="na_run", disabled=not (fit and pipeline.has_api_key())):
            bar = st.progress(0.0, text="Yapay zekâ haberleri analiz ediyor...")
            before = analyzer.month_spend(conn)
            try:
                res = analyzer.analyze(conn, uni, rows=fit, quality=quality, budget_usd=news_budget, track=True,
                                       on_eleme=False, progress=lambda i, n: bar.progress(i / max(n, 1), text=f"Analiz ({i}/{n})..."))
                cost = analyzer.month_spend(conn) - before
                flash("success", f"{res.get('analyzed', 0)} haber analiz edildi, {res.get('filtered_out', 0)} haber ön "
                      f"elemede önemsiz bulundu" + (f", {res['errors']} haberde hata" if res.get("errors") else "")
                      + (f", {res['tekrar']} haber daha önce analiz edilmiş bir haberin tekrarı olduğu için atlandı "
                         "(ücretlendirilmedi)" if res.get("tekrar") else "")
                      + f". Gerçek maliyet ≈ {cost:.3f} \\$." + (" OpenAI hesabı/kotası nedeniyle durdu: "
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
        st.info(f"Seçilen {len(sel)} haber · tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} \\$"
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
                      + f". Gerçek maliyet ≈ {cost:.3f} \\$.")
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
                       f"edilir. Sıradakiler için tahmini maliyet {est['low_usd']:.3f}–{est['high_usd']:.3f} \\$ "
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
            st.caption(f"Tahmini maliyet: rapor yorumu {e1['low']:.3f}–{e1['high']:.3f} \\$ / çalıştırma"
                       + (f" · kaçırılan açıklaması {e1['low']:.3f}–{e1['high']:.3f} \\$ / hisse (en fazla "
                          f"{ai_comment.MAX_MISSED}; daha önce açıklanan ücretlendirilmez)" if ai_missed else "")
                       + f" · bu ay harcanan {spent_:.3f} \\$ / bütçe {ai_budget:.2f} \\$")
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
                                      "yz_kacirilan": bool(ai_missed and pipeline.has_api_key()),
                                      "telegram": bool(notify.configured() and pipeline.load_settings().get("telegram_acik")),
                                      "hazir_sabah_yz": bool(pipeline.load_settings().get("hazir_sabah_yz", False))},
                    ai=bool(use_ai and pipeline.has_api_key()),
                    progress=lambda m, p_: bar.progress(min(max(p_, 0.0), 1.0), text=m))
                st.session_state["watch_last"] = out["rapor"]
                flash("success", f"{label} tamamlandı; rapor arşive kaydedildi ({out['rapor']}).")
                bd = out.get("bildirim")
                if bd and not bd["ok"]:
                    flash("warning", "Telegram bildirimi gönderilemedi: " + "; ".join(bd["hatalar"]))
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
                st.markdown(dollar(path.read_text(encoding="utf-8")))
                st.download_button("Raporu indir (.md)", path.read_bytes(), file_name=f"{name}.md",
                                   key="watch_dl")


def settings_panel() -> None:
    s1, s2, s3 = st.columns(3)
    _days = s1.select_slider("KAP: kaç günlük bildirim taransın?", options=[1, 2, 3, 5, 7], value=days, key="set_days")
    _al = s2.selectbox("Güncellemede / sabah analizinde en fazla kaç haber analiz edilsin?",
                                  [1, 3, 5, 10, 20, 30], index=[1, 3, 5, 10, 20, 30].index(analysis_limit),
                                  help="KAP ve haber siteleri birlikte bu adede dahildir; öncelik sırası: açık işlemler, "
                                       f"likit hisseler… {config.AUTO_ANALYSIS_MAX_AGE_DAYS} günden eski haberler "
                                       "kendiliğinden analiz edilmez (📰 Haberler ekranından elle seçilebilir). Para "
                                       "tavanı ayrıca: haber analizi aylık bütçesi.", key="live_analysis_limit")
    _win = s3.slider("Son kaç günün haberleri listeye katılsın?", 3, 30, window, key="set_window")
    if (_days, _al, _win) != (days, analysis_limit, window):   # Aşama 3: bu üçü de saklanır (ayarlar ayrı ekranda)
        pipeline.save_settings(kap_gun=_days, panel_analiz_siniri=_al, liste_pencere=_win)
        conn.close()
        st.rerun()
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
    # 2026-11-15 Aşama 6: model olasılığını kartlarda gösterme anahtarı (varsayılan KAPALI; kullanıcı kararı bekleniyor)
    mp_on = st.toggle("🎯 Hazır fırsat kartlarında modelin \"TP1'e SL'den önce ulaşma olasılığı\"nı göster (varsayılan kapalı)",
                      key="model_olasilik_set", value=bool(saved.get("model_olasilik_goster", False)),
                      help="Yalnız bilgi: seçimi, sırayı ve eşikleri değiştirmez. Model 4 yıllık geçmişle yalnız teknik veriden "
                           "eğitildi (haberi hesaba katmaz); son 12 ayda olasılıkları 2–6 puan yüksek söyledi. Ayrıntı: ASAMA6_RAPOR.md")
    if mp_on != bool(saved.get("model_olasilik_goster", False)):
        pipeline.save_settings(model_olasilik_goster=mp_on)
    # W6: bekçinin yapay zekâ yorumları için aylık bütçe (haber analizi maliyeti bunun dışında)
    ai_budget = st.number_input("Bekçi yapay zekâ yorumu aylık bütçesi (\\$)", 0.0, 100.0,
                                float(saved.get("yz_butce_usd", ai_comment.DEFAULT_BUDGET_USD)), 1.0, format="%.2f",
                                key="ai_budget", help="Rapor yorumu ve kaçırılan fırsat açıklamaları bu bütçeyi aşmaz: "
                                                     "bir çağrının en kötü durum maliyeti bütçeyi aşacaksa çağrı yapılmaz.")
    if ai_budget != saved.get("yz_butce_usd"):
        pipeline.save_settings(yz_butce_usd=ai_budget)
    # 2026-11-09 (kullanıcı onayı): haber analizinin de aylık bütçesi — bütçeyi aşacak analiz yapılmaz
    news_budget = st.number_input("Haber analizi aylık bütçesi (\\$)", 0.0, 500.0,
                                  float(saved.get("haber_butce_usd", config.NEWS_BUDGET_USD)), 1.0, format="%.2f",
                                  key="news_budget", help="Haberleri güncelle, sabah analizi ve 🔬 Haber analizi bu "
                                  "bütçeyi aşmaz: bir haberin en kötü durum maliyeti kalan bütçeyi aşacaksa o haber ve "
                                  "sonrakiler analiz edilmez. Bu ay harcanan 📰 Haberler ekranında görünür.")
    if news_budget != saved.get("haber_butce_usd"):
        pipeline.save_settings(haber_butce_usd=news_budget)
    if quality != config.DEFAULT_QUALITY:
        st.caption("⚠️ Bu ayarda maliyet düşer ama analizler daha az ayrıntılı ve hata payı daha yüksek olabilir.")
    # 2026-11-09: Telegram bildirimi (ücretsiz, yapay zekâ yok). Anahtar .env'de; veri aktarma dosyasına girmez.
    st.markdown("**📨 Telegram bildirimi**")
    if "_tg_on_set" in st.session_state:       # alıcı kaydedilince düğmeyi de aç (yoksa eski konumu ayarı geri kapatır)
        st.session_state["tg_on"] = st.session_state.pop("_tg_on_set")
    tg_on = st.toggle("Sabah ve akşam analizi bitince özetini Telegram'a gönder", key="tg_on",
                      value=bool(saved.get("telegram_acik", False)), disabled=not notify.configured(),
                      help="Önerilen senaryolar, takip listesi, stopa yaklaşan işlemler, TP/SL olan işlemler. "
                           "Ücretsizdir; emir vermez.")
    if notify.configured() and tg_on != bool(saved.get("telegram_acik", False)):
        pipeline.save_settings(telegram_acik=tg_on)
    tk_on = st.toggle("⭐ Takip listemdeki hisselerin bekçi olaylarını gönder (giriş, SL, TP, kırılım…)", key="tk_tg_on",
                      value=bool(saved.get("takip_bildirim", True)), disabled=not notify.configured(),
                      help="Yalnız takibe aldığınız hisseler; türleri hisse bazında ⭐ Takip Listem ekranından seçilir.")
    if notify.configured() and tk_on != bool(saved.get("takip_bildirim", True)):
        pipeline.save_settings(takip_bildirim=tk_on)
    # Aşama 4 (kullanıcı onayı 2026-11-09): takip listesindeki hisselerin yeni KAP haberleri bütçe içinde otomatik analiz
    th_on = st.toggle("📰 Takip listemdeki hisselerin yeni KAP haberlerini bekçi otomatik analiz etsin (varsayılan kapalı)",
                      key="tk_news_on", value=bool(saved.get("takip_haber_analizi", False)),
                      help="Bekçi işlem günlerinde 30 dakikada bir KAP listesine bakar; YALNIZ takip ettiğiniz hisselerin "
                           "yeni bildirimlerini okur ve yapay zekâyla analiz eder (haber başına ~0,013 \\$; aylık haber "
                           "analizi bütçesini aşmaz). Etkisi 3/5 ve üzeri olumlu/olumsuz haberler bildirilir.")
    if th_on != bool(saved.get("takip_haber_analizi", False)):
        pipeline.save_settings(takip_haber_analizi=th_on)
    hz_tg = st.toggle("✅ Hazır fırsatların açılış kontrolünü Telegram'a gönder (açılış azami girişin üstündeyse uyarı)",
                      key="hz_tg_on", value=bool(saved.get("hazir_bildirim", True)), disabled=not notify.configured())
    if notify.configured() and hz_tg != bool(saved.get("hazir_bildirim", True)):
        pipeline.save_settings(hazir_bildirim=hz_tg)
    hz_ai2 = st.toggle("🤖 Sabah kontrolünde hazır fırsatların gece haberlerini yapay zekâyla analiz et (varsayılan kapalı)",
                       key="hz_ai_set", value=bool(saved.get("hazir_sabah_yz", False)),
                       help="Yalnız hazır listedeki 1–5 hisse; haber başına ~0,013 \\$, aylık haber bütçesi içinde.")
    if hz_ai2 != bool(saved.get("hazir_sabah_yz", False)):
        pipeline.save_settings(hazir_sabah_yz=hz_ai2)
    with st.container(border=True, key="tg_box"):
        st.caption("**Telegram kurulumu**" + (f" — {len(notify.chat_ids())} alıcı ayarlı ✅" if notify.configured()
                                              else " — henüz ayarlanmadı"))
        st.caption("1) Telegram'da **@BotFather**'a `/newbot` yazın, bota bir ad verin; size bir **bot anahtarı** "
                   "verir. 2) Anahtarı aşağıya yapıştırıp kaydedin. 3) Bildirim alacak herkes Telegram'da kendi botunuzu "
                   "bulup **/start** yazsın (ya da botu bir gruba ekleyin). 4) **🔍 Alıcıları bul** → seçin → kaydedin. "
                   "5) **📨 Deneme mesajı gönder**.")
        tg_tok = st.text_input("Bot anahtarı", type="password", key="tg_token",
                               placeholder="kayıtlı (değiştirmek için yenisini yapıştırın)" if notify.token() else
                               "123456789:ABC...")
        if st.button("💾 Bot anahtarını kaydet", key="tg_save_token", disabled=not tg_tok.strip()):
            notify.save(tok=tg_tok)
            flash("success", "Bot anahtarı bu bilgisayara kaydedildi (.env). Şimdi alıcıları bulun.")
            conn.close()
            st.rerun()
        if notify.token():
            if st.button("🔍 Alıcıları bul (bota /start yazanlar)", key="tg_find"):
                try:
                    st.session_state["tg_found"] = notify.find_chats()
                except Exception as e:
                    flash("error", f"Alıcılar alınamadı: {e}")
                    conn.close()
                    st.rerun()
            found = st.session_state.get("tg_found")
            known = {c["id"]: c for c in (found or [])}
            for cid in notify.chat_ids():
                known.setdefault(cid, {"id": cid, "ad": "kayıtlı alıcı", "tur": ""})
            if found is not None and not found:
                st.warning("Bota henüz kimse yazmamış. Telegram'da botu açıp **/start** yazın, sonra yeniden deneyin.")
            if known:
                pick = st.multiselect("Bildirim alacaklar", list(known), default=notify.chat_ids() or list(known),
                                      format_func=lambda c: f"{known[c]['ad']} ({c})", key="tg_pick")
                if st.button("💾 Alıcıları kaydet", key="tg_save_chats"):
                    notify.save(chats=pick)
                    if pick and not saved.get("telegram_acik"):
                        pipeline.save_settings(telegram_acik=True)
                        st.session_state["_tg_on_set"] = True
                    flash("success", f"{len(pick)} alıcı kaydedildi." + (" Bildirimler açıldı." if pick else ""))
                    conn.close()
                    st.rerun()
        if notify.configured() and st.button("📨 Deneme mesajı gönder", key="tg_test"):
            r = notify.send("✅ Halley bağlandı. Sabah ve akşam analizi özetleri buraya gelecek." + notify.FOOT)
            if r["ok"]:
                flash("success", f"Deneme mesajı {r['gonderilen']} alıcıya gönderildi.")
            else:
                flash("error", "Gönderilemedi: " + "; ".join(r["hatalar"]))
            conn.close()
            st.rerun()
    st.caption("Kaynaklar: KAP + " + ", ".join(config.RSS_SOURCE_LABELS.get(n, n) for n in config.RSS_FEEDS)
               + ". KAP hızlı isteklere sınır koyduğu için ilk güncelleme birkaç dakika sürebilir.")


def advanced_panel() -> None:
    # 2026-11-09 (kullanıcı isteği): başka bilgisayara taşıma. API anahtarı dosyaya girmez (bkz. bist_haber/transfer.py).
    st.markdown("#### 💾 Veri aktarma (başka bilgisayara taşıma)")
    st.caption("Haberler, analizler, fiyatlar, işlem günlüğü, bekçi raporları, geçmiş veri pilotu ve ayarlar tek dosyada "
               "taşınır. API anahtarı dosyaya girmez; her bilgisayarda ayrı girilir.")
    x1, x2 = st.columns(2)
    with x1:
        st.markdown("**Dışa aktar** (bu bilgisayardan)")
        if st.button("📦 Veri dosyasını hazırla", key="export_prepare"):
            try:
                _ex = transfer.export_bytes()
                st.session_state["export_file"] = (_ex["bytes"], _ex["manifest"])
            except Exception as e:
                st.error(f"Veri dosyası hazırlanamadı: {nice_err(e)}")
        if st.session_state.get("export_file"):
            _b, _man = st.session_state["export_file"]
            _oz = _man["ozet"]
            st.caption(f"Hazır: {len(_b) / 1e6:.1f} MB · {_oz.get('haber', 0):,} haber · {_oz.get('etki', 0):,} analiz "
                       f"sonucu · {_oz.get('islem_gunlugu', 0)} işlem günlüğü kaydı · {_oz.get('rapor', 0)} rapor")
            st.download_button("⬇️ Veri dosyasını indir", _b, file_name=f"halley_veri_{date.today().isoformat()}.zip",
                               mime="application/zip", key="export_download")
    with x2:
        st.markdown("**İçe aktar** (başka bilgisayardan gelen dosya)")
        _up = st.file_uploader("halley_veri_….zip dosyasını seçin", type=["zip"],
                               key=f"import_file_{st.session_state.get('import_n', 0)}")
        if _up is not None:
            _data = _up.getvalue()
            _chk = transfer.inspect(_data)
            if not _chk["ok"]:
                st.error("Bu dosya içe aktarılamaz: " + "; ".join(_chk["hatalar"]))
            else:
                _oz = _chk["ozet"]
                st.info(f"Dosya sağlam ({_chk['manifest']['olusturma'][:16].replace('T', ' ')} tarihinde hazırlanmış): "
                        f"{_oz.get('haber', 0):,} haber, {_oz.get('etki', 0):,} analiz sonucu, "
                        f"{_oz.get('islem_gunlugu', 0)} işlem günlüğü kaydı, {_oz.get('rapor', 0)} rapor; son fiyat günü "
                        f"{_oz.get('son_fiyat_gunu') or '—'}.")
                st.warning("İçe aktarınca bu bilgisayardaki mevcut veriler bu dosyadakilerle DEĞİŞTİRİLİR. Önce mevcut "
                           "veriler otomatik olarak yedeklenir (data/yedek klasörü). API anahtarınız değişmez.")
                _sure = st.checkbox("Anladım, içe aktar", key=f"import_sure_{st.session_state.get('import_n', 0)}")
                if st.button("📥 İçe aktar", key="import_go", disabled=not _sure, type="primary"):
                    try:
                        conn.commit()
                        _res = transfer.import_bytes(_data)
                        sectors.clear_cache()
                        st.cache_data.clear()
                        for _k in ("_regime", "_regime_key", "export_file", "last_result"):
                            st.session_state.pop(_k, None)
                        flash("success", f"Veriler içe aktarıldı ({_res['dosya']} dosya). Önceki veriler şuraya "
                                         f"yedeklendi: {_res['yedek']}")
                    except Exception as e:
                        flash("error", f"İçe aktarma tamamlanamadı: {nice_err(e)}")
                    st.session_state["import_n"] = st.session_state.get("import_n", 0) + 1
                    conn.close()
                    st.rerun()
    st.divider()
    st.markdown("#### Durum")
    counts = dict(conn.execute("SELECT status, COUNT(*) FROM news GROUP BY status").fetchall())
    labels = {"new": "Analiz bekliyor", "analyzed": "Analiz edildi", "filtered_out": "Önemsiz bulundu (ön eleme)",
              "skipped": "Atlandı (rutin/ilgisiz/eski)", "error": "Hata",
              "duplicate": "Tekrarlanan haber (aynı içerik ya da başlık; yeniden analiz edilmedi)",
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
               "içindir; tahmini maliyet haber başına ~0,003–0,005 \\$.")
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
            st.write(f"**Maliyet:** {tr['usd']:.4f} \\$ · girdi {tr['input_tokens']:,} · çıktı {tr['output_tokens']:,} token")
            if tr["analysis"] is None:
                st.write(f"Ön eleme bu haberi önemsiz buldu: {tr['filter'].neden if tr['filter'] else '-'}")
            else:
                a = tr["analysis"]
                st.write(f"**Özet:** {a.ozet}")
                for imp in a.etkiler:
                    st.write(f"- {imp.hisse}: {imp.yon}, etki {impact_word(imp.etki)} — {imp.gerekce}")
                st.caption(f"Olay: {EVENT_TR.get(a.olay_tipi, a.olay_tipi)} · güven %{a.guven * 100:.0f} · "
                           "Bu sonuç kaydedilmedi; gerçek analiz yüksek doğrulukla ayrıca yapılır.")
    st.divider()
    st.divider()
    st.markdown("### 🧪 Geçmiş veri pilotu")
    from bist_haber.backtest_ui import render as render_backtest
    render_backtest()


def trend_panel() -> None:
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


def reports_panel() -> None:
    # W3: bekçi rapor arşivi — yalnız okunur; dosyalar değiştirilmez, silinmez
    w1, w2 = st.columns([1.4, 3], vertical_alignment="center")
    if w1.button("📅 Bu haftanın raporunu şimdi oluştur", key="rep_weekly", width="stretch",
                 help="Haftanın piyasası, hazır fırsatlar (haberli / yalnız teknik), kapanan işlemler, takip olayları ve "
                      "yapay zekâ maliyeti. Yalnız kayıtlı veriden, yapay zekâ KULLANILMAZ (ücretsiz)."):
        name = weekly.run(conn, send=lambda _t: None)     # elle üretimde Telegram gönderilmez (tekrar mesaj olmasın)
        flash("success", f"Haftalık rapor oluşturuldu: {name}. Aşağıdaki listede «Haftalık» türünden açabilirsiniz.")
        conn.close()
        st.rerun()
    w2.caption("Haftalık rapor, haftanın son işlem gününün akşam analizinden sonra bekçi tarafından kendiliğinden de "
               "oluşturulur (Telegram açıksa kısa özeti o zaman gelir; bu düğme Telegram'a göndermez).")
    names = watchdog.list_reports()
    if not names:
        st.info("Henüz bekçi raporu yok. Yukarıdaki **🌅 Sabah analizi** ya da **🌙 Akşam analizi** düğmesiyle ilk raporu "
                "oluşturun; her rapor tarihiyle arşive kaydedilir.")
    else:
        f1, f2 = st.columns([1, 3])
        kind_f = f1.radio("Tür", ["Hepsi", "Sabah", "Akşam", "Haftalık"], horizontal=False, key="rep_kind")
        kmap = {"Sabah": "_sabah", "Akşam": "_aksam", "Haftalık": "_haftalik"}
        shown = [n for n in names if kind_f == "Hepsi" or kmap[kind_f] in n]
        def label(n) -> str:
            """Arşiv adı → okunur etiket. Beklenmeyen değerde çökmez (2026-11-09 uçtan uca testte bulundu)."""
            n = str(n or "")
            m = re.match(r"^(\d{4}-\d{2}-\d{2})_(sabah|aksam|haftalik)(?:_(\d+))?$", n)
            if not m:
                return n
            return ({"sabah": "🌅 ", "aksam": "🌙 ", "haftalik": "📅 "}[m.group(2)] + m.group(1)
                    + {"sabah": " sabah", "aksam": " akşam", "haftalik": " haftalık rapor"}[m.group(2)]
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
            st.markdown(dollar(path.read_text(encoding="utf-8")))
        else:
            f2.info("Bu türde rapor yok.")


def page_head(title: str, sub: str = "") -> None:
    st.markdown(f"<div class='page-h'>{esc(title)}</div>" + (f"<div class='page-s'>{esc(sub)}</div>" if sub else ""),
                unsafe_allow_html=True)


def price_freshness_warning() -> None:
    """2026-11-15 denetim: akşam analizi günlerce çalışmayınca evren fiyatları eski kalıyordu ve panel bunu söylemiyordu.
    Son kapanmış işlem günü fiyatı olmayan hisse oranı %30'u aşarsa uyarı (teknik tarama/yalnız teknik eski fiyatla)."""
    last_ = tracker.last_closed_day(datetime.now(config.TR_TZ))
    if not last_:
        return
    tot, ok_ = conn.execute("SELECT COUNT(*), SUM(m>=?) FROM (SELECT MAX(date) m FROM prices GROUP BY ticker)",
                            (last_.isoformat(),)).fetchone()
    if not tot or (ok_ or 0) >= 0.7 * tot:
        return
    common = conn.execute("SELECT m FROM (SELECT MAX(date) m FROM prices GROUP BY ticker) GROUP BY m "
                          "ORDER BY COUNT(*) DESC LIMIT 1").fetchone()[0]
    st.warning(f"⚠️ **Hisse fiyatları güncel değil:** {tot} hisseden {tot - (ok_ or 0)} tanesinin son fiyatı "
               f"{common[8:10]}.{common[5:7]} tarihli; son işlem günü {last_.strftime('%d.%m')}. Akşam analizi o günlerde "
               "çalışmamış (Halley kapalıydı). Teknik tarama, yalnız teknik fırsatlar ve grafikler eski fiyatla hesaplanıyor. "
               "Düzeltmek için: 🛡️ Bekçi → **🌙 Akşam analizi** (yapay zekâ kullanmaz, ücretsiz). Halley açıksa bekçi bunu "
               "seans başlamadan kendisi de yapar.")


def regime_strip() -> None:
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


def bist_metric(col) -> None:
    px = conn.execute("SELECT date, close FROM prices WHERE ticker='XU100' ORDER BY date DESC LIMIT 2").fetchall()
    if len(px) == 2 and px[1]["close"]:
        chg = (px[0]["close"] / px[1]["close"] - 1) * 100
        tone = "up" if chg > 0 else "down" if chg < 0 else "flat"      # kart rengi günün yönüne göre
        with col.container(key=f"kpi_bist_{tone}"):
            st.metric("BIST 100", f"{px[0]['close']:,.0f}".replace(",", "."),
                      f"%{chg:+.2f} · {px[0]['date'][8:10]}.{px[0]['date'][5:7]}")
            st.caption("son kapanış · önceki güne göre değişim")
    else:
        with col.container(key="kpi_bist_flat"):
            st.metric("BIST 100", "—")


def page_dashboard() -> None:
    with st.container(key="kpi"):
        k0, m1, m2, k3, m3 = st.columns(5)
    bist_metric(k0)
    for col_, key_, label_, val_, note_ in (
            (m1, "kpi_pos", "Olumlu haber", f"{len(positives)} hisse", f"son {window} günde haber skoru +1,50 ve üstü"),
            (m2, "kpi_neg", "Olumsuz haber", f"{len(negatives)} hisse", f"son {window} günde haber skoru −1,50 ve altı"),
            (k3, "kpi_opp", "Hazır fırsat", f"{len(READY_ACTIVE)} hisse",
             f"koşulu sağlanmış (haberli {len(READY_NEWS)} · 📐 yalnız teknik {len(READY_TECH)}) · bekleyen senaryo: "
             f"{len(SUMMARY['uygun'])}"),
            (m3, "kpi_upd", "Son güncelleme", last_update_text(), "son haber analizinin saati")):
        with col_.container(key=key_):
            st.metric(label_, val_)
            st.caption(note_)
    price_freshness_warning()
    regime_strip()
    c1, c2 = st.columns([3, 2])
    with c1.container(border=True, key="d_ready"):
        section_title("✅", "Hazır Fırsatlar", "pos", len(READY_ACTIVE), ready_when_text())
        if READY_ACTIVE:
            st.dataframe(dash_cells(pd.DataFrame([{
                "Hisse": r["ticker"], "Tür": ready.TYPE_NAMES.get(r["tur"], r["tur"]), "Giriş aralığı":
                f"{r['giris_alt']:.2f}–{r['azami_giris']:.2f}", "SL": r["sl"], "TP1": r["tp1"], "TP2": r["tp2"],
                "R/G": r["rr1"], "Risk": r["risk"], "Kaynak": ready.KAYNAK_TR[r["kaynak"]],
                "Genel puan": str(ready.overall_score(r["haber_skoru"], r["teknik_skor"], r["rr1"], r["risk"],
                                                      r["kaynak"])["puan"]),
                "Durum": ready.STATE_TR.get(r["durum"], r["durum"])}
                for r in READY_NEWS + READY_TECH]), ["SL", "TP1", "TP2", "R/G"]), hide_index=True, width="stretch")
            st.caption("Koşulu sağlanmış, açılışta uygulanabilir planlar. Açılış azami girişin (aralığın üst ucu) "
                       "üstündeyse alınmaz. 📐 Yalnız teknik = haber desteği yok. Genel puan yalnız bilgi "
                       "(5 yıllık geçmiş sınamada TP1'i öngörmedi (yazı-tura düzeyi)). Ayrıntı ve gerekçe Fırsatlar ekranında.")
        else:
            st.caption("Şu an geçerli hazır fırsat yok (uygun yoksa liste boş kalır). Akşam analizi kapanıştan sonra "
                       "kendiliğinden yeni liste hazırlar.")
        go_button("Hazır fırsatların ayrıntısı →", PAGE_FIRSAT, "d_all_ready")
    with c1.container(border=True, key="d_opps"):
        section_title("⏳", "Bekleyen fırsatlar", "", len(SUMMARY["uygun"]), "koşul bekleyen senaryolar")
        if not SUMMARY["uygun"]:
            st.caption("Bugün koşul bekleyen uygun senaryo yok. Her gün işlem yapmak gerekmez.")
        for tk, name, risk in SUMMARY["uygun"][:8]:
            a, b, c = st.columns([1.3, 4, 1.5], vertical_alignment="center")
            a.markdown(f"**{tk}**")
            b.caption(f"{name.split(' (')[0]} · senaryo riski {risk}")
            with c:
                go_button("🔍 Analiz", PAGE_HISSE, f"d_an_{tk}", tk, width="stretch")
        if SUMMARY["uygun"]:
            st.caption("Risk, gösterilen senaryonun riskidir (koşul oluşunca alım). Hemen şimdi almanın riski 🔍 Analiz "
                       "ekranında «Mevcut fiyattan girilirse» bölümünde ayrıca yazar.")
        go_button("Tüm bekleyen fırsatlar →", PAGE_FIRSAT, "d_all_opps")
    with c2.container(border=True, key="d_watch"):
        section_title("🛡️", "Bekçi")
        takip_ui.watcher_status(conn, compact=True)
        ev = tracker.events(conn, limit=6)
        if ev:
            st.markdown("\n".join(f"- `{e['zaman'][5:16].replace('T', ' ')}` **{e['ticker']}** {md(e['mesaj'])}"
                                  + ("" if e["kesin"] else " _(gün içi)_") for e in ev))
        else:
            st.caption("Henüz bekçi olayı yok.")
        go_button("Bekçi ekranı →", PAGE_BEKCI, "d_to_bekci")
    c3, c4 = st.columns(2)
    with c3.container(border=True, key="d_scen"):
        act = [s for s in tracker.scenarios(conn, active_only=True) if tracker.is_watched(conn, s["ticker"])]
        section_title("⭐", "Aktif senaryolarım", count=len(act), note="takip listesi")
        st.caption("Takibe aldığınız hisselerin bekçinin izlediği senaryoları. ⏳ giriş bekleniyor = fiyat giriş "
                   "seviyesine henüz gelmedi; 🟢 açık = giriş gerçekleşti.")
        if act:
            st.dataframe(dash_cells(pd.DataFrame([{
                "Hisse": s["ticker"], "Senaryo": tracker.NAMES.get(s["senaryo"], s["senaryo"]),
                "Durum": takip_ui.STATE_TR.get(s["durum"], s["durum"]), "Giriş": s["giris"], "SL": s["sl"],
                "TP1": s["tp1"], "TP2": s["tp2"]} for s in act]), ["Giriş", "SL", "TP1", "TP2"]),
                hide_index=True, width="stretch")
        else:
            st.caption("Takip listenizde etkin senaryo yok. Fırsatlar ya da Hisse Analizi ekranındaki **➕ Takibe Al** ile ekleyin.")
        go_button("Takip Listem →", PAGE_TAKIP, "d_to_takip")
    with c4.container(border=True, key="d_open"):
        jr = watchdog._journal_rows(conn)
        section_title("📒", "Açık işlemler", count=len(jr), note="sanal + gerçek")
        st.caption("Sanal = Halley'in kendi önerisini izlediği işlem (siz almadınız); Gerçek = sizin kaydettiğiniz. "
                   "Stopa uzaklık % = son kapanışın stopun ne kadar üstünde olduğu (küçüldükçe stop yaklaşıyor).")
        if jr:
            st.dataframe(dash_cells(pd.DataFrame([{
                "No": r["no"], "Tür": r["tur"], "Hisse": r["hisse"], "Durum": r["durum"], "Giriş": r["giris"],
                "Stop": r["stop"], "Son": r["son"], "Stopa uzaklık %": r["stop_uzaklik_%"]} for r in jr]),
                ["Giriş", "Stop", "Son", "Stopa uzaklık %"]), hide_index=True, width="stretch")
        else:
            st.caption("Açık ya da bekleyen işlem yok.")
        go_button("İşlem günlüğü →", PAGE_GUNLUK, "d_to_gunluk")
    with st.container(key="macro"):
        macro_block()


def page_firsatlar() -> None:
    page_head(PAGE_FIRSAT, "Önce hazır fırsatlar (koşulu sağlanmış), altında koşul bekleyen senaryolar. Ayrıntı için 🔍 Analiz.")
    price_freshness_warning()
    ready_section()
    section_title("⏳", "Bekleyen Fırsatlar", note="henüz giriş koşulu oluşmamış senaryolar (destek/direnç teyidi bekleyen)")
    opportunity_check_box()
    if not rows:
        st.info("Henüz liste yok. Yukarıdaki **Haberleri güncelle** düğmesine basın.")
    else:
        summary_ = SUMMARY
        if summary_["uygun"]:
            st.markdown(
                f"<div class='opp'><div class='h'>🎯 Bugün {len(summary_['uygun'])} hissede uygun görünen giriş senaryosu var</div>"
                "<div class='chips'>" + "".join(
                    f"<span class='tk r-{esc(str(risk))}'><b>{esc(tk)}</b>{esc(name.split(' (')[0].lower())} · senaryo riski {esc(str(risk))}</span>"
                    for tk, name, risk in summary_["uygun"])
                + "</div><div class='f'>Kenar rengi risk seviyesini gösterir (yeşil düşük, turuncu orta, kırmızı yüksek). "
                "Risk, gösterilen giriş senaryosunun riskidir (fiyat koşula gelince alım); hemen şimdi almanın riski 🔍 Analiz "
                "ekranında ayrıca yazar. Bu bir senaryodur, yatırım tavsiyesi değildir.</div></div>",
                unsafe_allow_html=True)
        else:
            st.info("**Bugün uygun işlem fırsatı bulunamadı.** Her gün işlem yapmak gerekmez. "
                    + ("Nedenler: " + "; ".join(f"{k} ({v} hisse)" for k, v in summary_["nedenler"].items()) + "."
                       if summary_["nedenler"] else "Olumlu haber alan hisse yok."))
        section_title("📈", "Olumlu haber alanlar", "pos", len(positives))
        st.caption("Skor = haber skoru: haberlerin yönü, etkisi ve güveninden hesaplanır, haber eskidikçe azalır (+1,50 ve "
                   "üstü olumlu, −1,50 ve altı olumsuz). ✅ Teyitli: iki ayrı analiz aynı sonuca vardı · ⚠️ Kontrol et: "
                   "analizler çelişti. Altındaki etiket teknik trend özeti. 🔍 Analiz: tüm analiz · ➕ Takibe Al: bekçi "
                   "izlesin ve bildirsin. **Puan** = genel fırsat puanı (0–100: haber, teknik, en uygun giriş "
                   "senaryosunun risk/getirisi ve riski); yalnız bilgi, sırayı değiştirmez; 5 yıllık geçmiş sınamada TP1'i öngörmedi (yazı-tura düzeyi).")
        stock_list(positives, "Bu dönemde olumlu haber alan hisse yok.", "pos")
        section_title("📉", "Olumsuz haber alanlar", "neg", len(negatives))
        stock_list(negatives, "Bu dönemde olumsuz haber alan hisse yok.", "neg")
        if neutrals and st.toggle(f"Etkisi zayıf/nötr haberleri de göster ({len(neutrals)} hisse)", key="show_neutral"):
            section_title("👁️", "İzlenecekler", "neu", len(neutrals))
            stock_list(neutrals, "", "neu")
        st.caption("🔍 Analiz ile haberin özeti, nedeni ve kaynağı açılır. "
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


def page_hisse() -> None:
    names = {r["ticker"]: r["name"] for r in conn.execute("SELECT ticker, name FROM companies ORDER BY ticker")}
    opts = sorted(names)
    if not opts:
        st.info("Şirket listesi henüz yok.")
        return
    by = {r["ticker"]: r for r in rows}
    if "hisse_pick" not in st.session_state and st.session_state.get("_hisse") in opts:
        st.session_state["hisse_pick"] = st.session_state["_hisse"]   # başka ekrandan dönünce seçim kaybolmasın
    if st.session_state.get("hisse_pick") not in opts:
        st.session_state["hisse_pick"] = positives[0]["ticker"] if positives else opts[0]
    s0, s1, s2 = st.columns([1.6, 3, 1.6], vertical_alignment="bottom")
    q = tr_fold(s0.text_input("Ara", key="hisse_q", placeholder="kod ya da şirket adı (ör. aksigorta)"))
    if q:   # Türkçe karakterli adlar da bulunsun: "aksigorta" → AKSİGORTA, "sise" → ŞİŞE
        found = [t for t in opts if all(w in tr_fold(f"{t} {names.get(t, '')}") for w in q.split())]
        if found:
            opts = found
            if st.session_state.get("hisse_pick") not in opts:
                st.session_state["hisse_pick"] = opts[0]
        else:
            s0.caption("Eşleşen hisse yok.")
    tk = s1.selectbox("Hisse", opts, key="hisse_pick", format_func=lambda t: f"{t} — {names.get(t, '')}")
    st.session_state["_hisse"] = tk
    with s2:
        takip_ui.follow_button(conn, tk, f"card_{tk}")
    st.markdown(f"<div class='page-h'>{esc(tk)} · {esc(names.get(tk, ''))}</div>", unsafe_allow_html=True)
    r = by.get(tk)
    draw = lambda: (tracked_box(tk), stock_details(r) if r else generic_details(tk))
    hisse_html_ui(tk, names.get(tk, ""), draw)
    draw()


def hisse_html_ui(tk: str, name: str, draw) -> None:
    """2026-11-15: Hisse Analizi ekranını tek dosya .html olarak indir. Dosya, ekranı çizen fonksiyonların aynısıyla
    üretilir (bist_haber/html_export); YZ çağrısı yok. İki adım: hazırla → kaydet (her açılışta boşuna üretilmesin)."""
    from bist_haber import html_export
    e1, e2 = st.columns([1.6, 4], vertical_alignment="center")
    if e1.button("📄 HTML olarak indir", key=f"html_mk_{tk}", width="stretch",
                 help="Bu ekranın (grafik, senaryolar, teknik görünüm, takvim, haberler) tek dosyalık bir kopyası. "
                      "Tarayıcıda açılır; grafik için internet gerekir, diğer bölümler çevrimdışı okunur."):
        now_ = datetime.now(config.TR_TZ)
        try:
            body = html_export.capture(globals(), draw, DARK=False)
            st.session_state["_html_dosya"] = (tk, html_export.page(
                f"{tk} · {name}", f"Halley · Hisse Analizi · {now_.strftime('%d.%m.%Y %H:%M')} · fiyatlar gecikmelidir",
                body, "Halley haberleri ve fiyatları kodla özetler; yatırım tavsiyesi değildir. Emir vermez, işlemi siz "
                      "Midas'tan yaparsınız. Bu dosya oluşturulduğu andaki verileri gösterir; sonradan güncellenmez."),
                f"{tk}_analiz_{now_.strftime('%Y%m%d_%H%M')}.html")
        except Exception as ex:
            st.error(f"HTML dosyası hazırlanamadı: {nice_err(ex)}")
    got = st.session_state.get("_html_dosya")
    if got and got[0] == tk:
        e2.download_button(f"💾 Dosyayı kaydet ({got[2]})", got[1].encode("utf-8"), file_name=got[2],
                           mime="text/html", key=f"html_dl_{tk}", on_click="ignore")


def tracked_box(tk: str) -> None:
    """Takipteki senaryolar ile bugünkü analiz farklı olabilir: neden olduğunu açıkça yaz (2026-11-09 görünüm kontrolü)."""
    if not tracker.is_watched(conn, tk):
        return
    sc = tracker.scenarios(conn, tk, active_only=True)
    with st.container(border=True, key="h_tracked"):
        section_title("⭐", "Takipteki senaryolar", count=len(sc), note="bekçi bunları izliyor")
        if sc:
            st.dataframe(dash_cells(pd.DataFrame([{
                "Senaryo": tracker.NAMES.get(s["senaryo"], s["senaryo"]), "Durum": takip_ui.STATE_TR.get(s["durum"], s["durum"]),
                "Giriş": s["giris"], "SL": s["sl"], "TP1": s["tp1"], "TP2": s["tp2"], "Hesap günü": s["signal_day"],
                "Geçerlilik (işlem günü)": str(s["gecerlilik"])} for s in sc]), ["Giriş", "SL", "TP1", "TP2"]),
                hide_index=True, width="stretch")
        else:
            st.caption("Etkin takip senaryosu yok; bekçi her kapanıştan sonra yeniden hesaplar.")
        st.caption("Takip senaryoları **hesap günündeki** fiyatla kaydedildi ve sonuçlanana ya da süresi dolana kadar aynı "
                   "seviyelerle izlenir. Aşağıdaki giriş senaryoları ise **bugünkü** fiyatla yeniden hesaplanır; fiyat "
                   "değiştiyse ikisi farklı olabilir (ör. fiyat destekten uzaklaştıysa bugün \"destekten tepki\" "
                   "uygulanamaz görünür, takipteki senaryo yine de giriş seviyesini bekler).")


def opportunity_check_box() -> None:
    """Fırsat sayısı neden değişti? Elle yeniden kontrol + tüm adayların durumu (2026-11-09 kullanıcı isteği)."""
    with st.container(border=True, key="opp_check"):
        c1, c2, c3 = st.columns([4, 1.8, 1.6], vertical_alignment="center")
        ch = firsat_log.changes(1)
        last_ch = ch[0] if ch else None
        txt = f"**Şu an {len(SUMMARY['uygun'])} hissede uygun senaryo var.** "
        if last_ch and last_ch.get("onceki_sayi") is not None:
            txt += (f"Son değişiklik {last_ch['zaman'][8:10]}.{last_ch['zaman'][5:7]} {last_ch['zaman'][11:16]}: "
                    f"{last_ch['onceki_sayi']} → {last_ch['sayi']}"
                    + (f" · eklenen: {', '.join(last_ch['eklenen'])}" if last_ch["eklenen"] else "")
                    + (f" · çıkan: {', '.join(x['hisse'] for x in last_ch['cikan'])}" if last_ch["cikan"] else "") + ".")
        c1.markdown(txt)
        c1.caption("Liste kayıtlı veriden her açılışta yeniden hesaplanır: haber skoru haber eskidikçe azalır, fiyatlar ve "
                   "yeni analizler geldikçe senaryolar değişir. Hangi hissenin neden çıktığı aşağıdaki tabloda.")
        upd_px = c2.checkbox("Fiyatları da güncelle (ücretsiz, birkaç saniye)", key="opp_px")
        if c3.button("🔄 Fırsatları şimdi yeniden kontrol et", key="opp_recheck", width="stretch"):
            if upd_px and not os.environ.get("HALLEY_OFFLINE"):
                from bist_haber import prices as _prices
                with st.spinner("Olumlu haberli hisselerin fiyatları güncelleniyor..."):
                    try:
                        _prices.update(conn, [r["ticker"] for r in positives] + ["XU100"], period="1mo")
                    except Exception as e:
                        flash("warning", f"Fiyatlar güncellenemedi: {nice_err(e)}; kayıtlı fiyatlarla kontrol edildi.")
            st.session_state["opp_checked"] = datetime.now(config.TR_TZ).strftime("%H:%M:%S")
            flash("success", f"Fırsatlar yeniden kontrol edildi ({st.session_state['opp_checked']}). Sonuç aşağıda; "
                             "liste değiştiyse değişiklik kaydedildi.")
            conn.close()
            st.rerun()
        with st.expander(f"📋 Tüm adaylar — elle kontrol ({len(positives)} olumlu haberli hisse)"):
            cand = []
            for r in positives:
                d = signals.decide(CTX, r)
                p = scenario(r)
                g = p.get("girisler") or {}
                best = next((s for s in g.get("senaryolar", []) if s["tur"] == g.get("en_uygun")), None)
                cand.append({"Hisse": r["ticker"], "Haber skoru": r["score"],
                             "Durum": "✅ uygun" if d["neden_kodu"] == "ONERILDI" else "❌ " + d["neden"],
                             "En uygun senaryo": (best or {}).get("ad", "—"), "Giriş": (best or {}).get("giris"),
                             "SL": (best or {}).get("sl"), "TP1": (best or {}).get("tp1"), "TP2": (best or {}).get("tp2"),
                             "Risk": (best or {}).get("risk_seviyesi") or "—"})
            cand.sort(key=lambda x: (not x["Durum"].startswith("✅"), -x["Haber skoru"]))
            if cand:
                st.dataframe(dash_cells(pd.DataFrame(cand), ["Haber skoru", "Giriş", "SL", "TP1", "TP2"]),
                             hide_index=True, width="stretch")
            near = [r for r in neutrals if r["score"] >= 1.0]
            if near:
                st.caption("Eşiğin hemen altında (skor 1,00–1,49; senaryo için en az 1,50 gerekir): "
                           + ", ".join(f"{r['ticker']} {r['score']:.2f}" for r in near))
            hist = firsat_log.changes(15)
            if hist:
                st.markdown("**Liste değişiklikleri** (en yeni üstte)")
                st.dataframe(pd.DataFrame([{
                    "Zaman": h["zaman"][:16].replace("T", " "),
                    "Sayı": f"{h['onceki_sayi']} → {h['sayi']}" if h.get("onceki_sayi") is not None else str(h["sayi"]),
                    "Eklenen": ", ".join(h["eklenen"]) or "—",
                    "Çıkan (neden)": "; ".join(f"{x['hisse']}: {x['neden']}" for x in h["cikan"]) or "—"} for h in hist]),
                    hide_index=True, width="stretch")
            else:
                st.caption("Henüz kayıtlı liste değişikliği yok (kayıt 9 Kasım 2026 akşamından itibaren tutuluyor).")


def page_takip() -> None:
    page_head(PAGE_TAKIP, "Bot bütün piyasayı tarar; Telegram'a yalnız buradaki hisselerin olayları gider.")
    takip_ui.render(conn)


def page_bekci() -> None:
    page_head(PAGE_BEKCI, "Sabah/akşam analizi, takip bekçisinin olayları ve rapor arşivi.")
    price_freshness_warning()
    with st.container(border=True, key="watch"):
        watch_box()
        hs = ready.load_state()
        st.caption("🤖 Otomatik çalışma (Halley açıkken): akşam analizi kapanıştan ~20 dk sonra, sabah analizi 08:30–09:55 arası (açılıştan önce) "
                   "itibaren, hazır fırsat açılış kontrolü 10:05'ten itibaren — günde birer kez; elle yaptıysanız "
                   "yinelenmez. Yapay zekâ ile haber analizi YAPILMAZ (yalnız sabah haber kontrolü düğmesi açıksa). "
                   f"Son akşam: {hs.get('aksam_gunu', '—')} · son sabah: {hs.get('sabah_gunu', '—')} · son açılış kontrolü: "
                   f"{hs.get('acilis_gunu', '—')}" + (f" · son hata: {hs['hata']}" if hs.get("hata") else ""))
    with st.container(border=True, key="b_takip"):
        section_title("⭐", "Takip bekçisi", note="takip listenizi arka planda kendisi izler")
        takip_ui.watcher_status(conn)
        takip_ui.events_table(conn)
    section_title("📋", "Rapor arşivi", note="sabah/akşam/haftalık raporlar değiştirilmez")
    reports_panel()


def page_haberler() -> None:
    page_head(PAGE_HABER)
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


def page_gunluk() -> None:
    page_head(PAGE_GUNLUK)
    with st.expander("❓ İşlem Günlüğü nasıl okunur?", expanded=True):
        st.markdown(
            "- **Ne işe yarar?** Halley'in önerdiği senaryoların **gerçekte işe yarayıp yaramadığını ölçer.** Para "
            "yatırılmaz, emir verilmez; sonraki günlerin gerçek fiyatlarıyla \"bu senaryoya uyulsaydı ne olurdu\" "
            "hesaplanır.\n"
            "- **Sanal işlem:** bir hisse fırsatlarda \"uygun\" görünce Halley en uygun senaryoyu kendiliğinden kayda alır "
            "ve izler. **Siz almadınız**; bu, Halley'in kendi karnesidir.\n"
            "- **Gerçek işlem:** Midas'tan gerçekten aldıysanız aşağıdaki **✍️ Bu işleme girdim** bölümüne alış gününü ve "
            "fiyatını yazın. Aynı seviyelerle ayrıca izlenir; kendi sonuçlarınız ayrı ölçülür.\n"
            "- **Durum:** ⏳ *bekliyor* = fiyat giriş seviyesine henüz gelmedi · *açık* = giriş gerçekleşti, izleniyor · "
            "*açık (TP1 görüldü)* = ilk hedefe ulaştı, yarısı satıldı sayılır ve stop giriş fiyatına çekilir · "
            "*kapandı* = TP2, SL, başabaş ya da 30 işlem günü dolmasıyla bitti · *iptal* = geçerlilik süresinde giriş "
            "koşulu oluşmadı (para kaybı yok).\n"
            "- **Sütunlar:** *Sinyal günü* senaryonun hesaplandığı gün · *Giriş / SL / TP1 / TP2* planlanan alış, zarar "
            "durdur ve hedefler · *Net %* komisyon ve kayma düşülmüş getiri (açık işlemde son kapanışa göre) · *R* "
            "kazancın planlanan zarara oranı (+1R = planlanan zarar kadar kazanç, −1R = planlanan zarar kadar kayıp).\n"
            "- **Üstteki ölçüler** ancak yeterli işlem kapanınca anlamlıdır (en az 30); öncesinde rastlantı olabilir.\n"
            "- **🧺 Portföy riski:** açık/bekleyen işlemlerin aynı sektörde toplanması gibi uyarılar; sektör haberi "
            "hepsini birlikte etkileyebilir.")
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
        st.caption("Tablo başlığının üstüne gelince sütunun açıklaması çıkar. Bekliyor/iptal satırlarında Net % boştur "
                   "(alım olmadı).")
        st.dataframe(dash_cells(pd.DataFrame(tbl), ["Giriş", "SL", "TP1", "TP2", "Net %", "R"]),
                     hide_index=True, width="stretch", column_config=JOURNAL_COLS)
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


def page_performans() -> None:
    page_head(PAGE_PERF, "Hangi strateji gerçekten işe yarıyor? Yalnız kayıtlı sonuçlardan, kodla hesaplanır.")
    section_title("✅", "Hazır fırsatlar — gerçek sonuçlar", note="bekleyen senaryolardan ayrı ölçülür")
    kay = st.radio("Hangi fırsatlar?", ["Hepsi", "📰 Haberli", "📐 Yalnız teknik"], horizontal=True, key="pf_kay")
    kay_ = {"Hepsi": None, "📰 Haberli": "haber", "📐 Yalnız teknik": "teknik"}[kay]
    pf = ready.performance(conn, kay_)
    st.caption("Giriş = planlanan günün AÇILIŞ fiyatı (açılış azami girişin üstündeyse 'giriş olmadı'); sonra işlem "
               "günlüğüyle aynı kurallar: TP1'de yarısı satılır, stop girişe çekilir; TP2, SL ya da 30 işlem günü. "
               "Komisyon ve kayma düşülür.")
    k = st.columns(5)
    k[0].metric("Önerilen", pf["onerilen"])
    k[1].metric("Kapanan", pf["kapanan"])
    k[2].metric("Açık", pf["acik"])
    k[3].metric("Giriş olmadı", pf["girissiz"], help="açılış azami girişin üstündeydi")
    k[4].metric("Sabah iptal", pf["sabah_iptal"], help="kötü haber ya da bozulan plan")
    if pf["kapanan"]:
        st.dataframe(pd.DataFrame([{x: pf[x] for x in ("Kazanma %", "TP1 %", "TP2 %", "SL %", "Başabaş %", "Süre doldu %",
                                                        "Ort. net %", "Ort. işlem günü")}]), hide_index=True, width="stretch")
        if pf["kapanan"] < 30:
            st.caption(f"⚠️ Yalnız {pf['kapanan']} kapanan öneri var: 30'dan azken oranlar güvenilir değildir.")
    hist = ready.rows_for(conn, kaynak=kay_)[:60]
    if hist:
        st.dataframe(dash_cells(pd.DataFrame([{
            "Giriş günü": r["giris_gunu"], "Hisse": r["ticker"], "Kaynak": ready.KAYNAK_TR[r["kaynak"]],
            "Analiz": r["analiz"], "Önerilen giriş": r["giris"],
            "Azami": r["azami_giris"], "Açılış (gerçek giriş)": r.get("acilis"), "Durum": ready.STATE_TR.get(r["durum"], r["durum"]),
            "Sonuç": r["sonuc"].get("sonuc") or (r.get("iptal_nedeni") or "")[:60], "Net %": r["sonuc"].get("net_getiri_pct"),
            "İşlem günü": str(r["sonuc"].get("islem_gunu") or "")} for r in hist]),
            ["Önerilen giriş", "Azami", "Açılış (gerçek giriş)", "Net %"]), hide_index=True, width="stretch")
    else:
        st.caption("Henüz kayıtlı hazır fırsat yok; ilk liste ilk akşam analizinde oluşur.")
    st.divider()
    section_title("🏁", "Takip senaryoları — strateji başarı oranları")
    takip_ui.performance_table(conn)
    st.divider()
    section_title("🧭", "Sanal işlemler ve gelişim")
    trend_panel()


def ai_usage_panel() -> None:
    """Merkezi YZ servisinin kaydı (2026-11-14, Aşama 2): her çağrı, token, maliyet, hangi özellik, hatalar."""
    u = ai_service.usage(conn)
    st.caption("Halley'in ana işleri (tarama, teknik analiz, fırsatlar, bekçi, raporlar, Telegram) yapay zekâ KULLANMAZ. "
               "Yapay zekâ yalnız sizin başlattığınız işlemlerde çağrılır: 🔄 Haberleri güncelle, 📰 Haberler → 🔬 analiz, "
               "isteğe bağlı rapor yorumu, açtığınız haber kontrolü düğmeleri. Aynı içerik bir daha analiz edilmez. "
               "Maliyetler token sayısından hesaplanan tahmindir; kesin tutar OpenAI hesabınızdadır.")
    k = st.columns(4)
    k[0].metric("Bugün", f"{u['bugun']['cagri']} çağrı", f"≈ {u['bugun']['usd']:.3f} $", delta_color="off")
    k[1].metric("Bu ay", f"{u['ay']['cagri']} çağrı", f"≈ {u['ay']['usd']:.3f} $", delta_color="off")
    news_spent = analyzer.month_spend(conn)
    k[2].metric("Haber analizi bütçesi (ay)", f"{news_budget:.2f} $", f"kalan ≈ {max(0.0, news_budget - news_spent):.3f} $",
                delta_color="off")
    k[3].metric("Bu ay hata / tekrar", f"{u['ay']['hata']} / {u['ay']['tekrar']}")
    # 2026-11-14 denetim: Aşama 3 ön eleme ve Aşama 2 tekrar ayıklamanın bu ay kazandırdığı (tahmini)
    ay_ = datetime.now(config.TR_TZ).strftime("%Y-%m")
    n_rut = conn.execute("SELECT COUNT(*) FROM news WHERE status='skipped' AND note LIKE 'Python ön eleme:%' "
                         "AND substr(fetched_at,1,7)=?", (ay_,)).fetchone()[0]
    n_dup = conn.execute("SELECT COUNT(*) FROM news WHERE status='duplicate' AND substr(fetched_at,1,7)=?",
                         (ay_,)).fetchone()[0]
    avg_ = conn.execute("SELECT AVG(usd) FROM ai_calls WHERE islem='tam_analiz' AND durum='ok'").fetchone()[0] or 0.0154
    if n_rut or n_dup:
        st.caption(f"💰 Bu ay yapay zekâya hiç gönderilmeyen: {n_rut} rutin haber (Python ön eleme) + {n_dup} tekrar haber "
                   f"→ hepsi analiz edilseydi ≈ {(n_rut + n_dup) * avg_:.2f} $ tutardı (tahmini; haber başına ≈ "
                   f"{avg_:.4f} $). Elle analiz sınırı olduğu için gerçek tasarruf bundan az olabilir.")
    st.caption(f"Bu ay token: girdi {u['ay']['girdi']:,} · çıktı {u['ay']['cikti']:,}".replace(",", ".")
               + (f" · kayıt başlamadan önceki haber analizleri: {u['oncesi']['cagri']} çağrı ≈ {u['oncesi']['usd']:.2f} $"
                  if u["oncesi"]["cagri"] else ""))
    if u["modul"]:
        st.markdown("**Bu ay hangi özellik ne kadar kullandı**")
        st.dataframe(pd.DataFrame(u["modul"]), hide_index=True, width="stretch")
    else:
        st.info("Bu ay kayıtlı yapay zekâ çağrısı yok.")
    if u["gunluk"]:
        st.markdown("**Son 30 gün (günlük maliyet $)**")
        st.bar_chart(pd.DataFrame(u["gunluk"]).set_index("Gün")["Maliyet $"], height=180)
    if u["hatalar"]:
        with st.expander(f"Son hatalar ({len(u['hatalar'])})"):
            st.dataframe(pd.DataFrame([{"Zaman": h["zaman"][:16].replace("T", " "),
                                        "Özellik": ai_service.MODULE_TR.get(h["modul"], h["modul"]),
                                        "İşlem": ai_service.ISLEM_TR.get(h["islem"], h["islem"] or "—"),
                                        "Hata": h["hata"]} for h in u["hatalar"]]), hide_index=True, width="stretch")
    if u["son"]:
        with st.expander("Son 30 çağrı"):
            st.dataframe(pd.DataFrame([{"Zaman": c["zaman"][:16].replace("T", " "),
                                        "Özellik": ai_service.MODULE_TR.get(c["modul"], c["modul"]),
                                        "İşlem": ai_service.ISLEM_TR.get(c["islem"], c["islem"] or "—"),
                                        "Kayıt": c["ref"] or "—", "Girdi": c["girdi"], "Çıktı": c["cikti"],
                                        "Maliyet $": round(c["usd"] or 0, 4), "Durum": c["durum"]} for c in u["son"]]),
                         hide_index=True, width="stretch")


def update_panel() -> None:
    """⚙️ Ayarlar → 💾 Veri ve gelişmiş: sürüm, elle kontrol, önceki sürüme dönüş (2026-11-15)."""
    from bist_haber import guncelleme
    with st.container(border=True, key="upd_panel"):
        section_title("🔄", "Güncelleme")
        root = guncelleme.kok()
        if not root:
            st.caption("Bu Halley geliştirme klasöründen çalışıyor; uygulama içi güncelleme yalnız kurulum dosyasıyla "
                       "kurulmuş Halley'de açıktır.")
            return
        k = guncelleme.kurulu(root)
        st.markdown(f"Kurulu sürüm: **{esc(k['surum'])}**", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        if c1.button("🔎 Güncellemeyi şimdi kontrol et", key="upd_check", width="stretch"):
            st.session_state["_upd"] = u = guncelleme.kontrol(zorla=True)
            txt = {"guncel": "✅ Halley güncel.", "yeni": "🆕 Yeni sürüm var; sayfanın üstündeki **Güncelle** düğmesini "
                   "kullanın.", "tam_kurulum": "🆕 Yeni sürüm var ama tam kurulum gerekiyor (üstteki nota bakın).",
                   "bekliyor": "🔄 Hazırlanmış güncelleme yeniden açılışta uygulanacak.",
                   "hata": f"Kontrol edilemedi (internet bağlantısı?): {u.get('hata', '')}"}.get(u.get("durum"), "")
            flash("info", txt)
            conn.close()
            st.rerun()
        prev = guncelleme.onceki(root)
        if prev:
            if c2.button(f"↩️ Önceki sürüme dön ({prev})", key="upd_back", width="stretch",
                         help="Son güncellemeden önceki sürüm geri yüklenir; verileriniz değişmez. Halley yeniden açılır."):
                try:
                    guncelleme.geri_don_iste()
                    guncelleme.yeniden_baslat()
                    st.success("↩️ Halley birkaç saniye içinde kapanıp önceki sürümle açılacak.")
                except Exception as e:
                    st.error(f"Geri dönülemedi: {nice_err(e)}")
        else:
            c2.caption("Geri dönülecek önceki sürüm yok (henüz uygulama içinden güncelleme yapılmadı).")
        st.caption("Halley yeni sürümü günde bir kez kendiliğinden kontrol eder. Güncellemede yalnız uygulama kodu iner; "
                   "verileriniz (veritabanı, ayarlar, raporlar) ve API anahtarınız değişmez.")


def page_ayarlar() -> None:
    page_head(PAGE_AYAR)
    t1, t4, t2, t3 = st.tabs(["⚙️ Ayarlar ve bildirim", "🤖 Yapay zekâ kullanımı", "💾 Veri ve gelişmiş", "❓ Kılavuz"])
    with t4:
        ai_usage_panel()
    with t1:
        settings_panel()
    with t2:
        update_panel()
        advanced_panel()
    with t3:
        # Plan 1.3 (2026-11-09): programı kullanacak kişi için güncel kılavuz (KULLANIM.md ile aynı metin)
        _guide = config.ROOT / "KULLANIM.md"
        st.markdown(dollar(_guide.read_text(encoding="utf-8")) if _guide.exists() else
                    "Kılavuz dosyası (KULLANIM.md) bulunamadı.")


{PAGE_DASH: page_dashboard, PAGE_FIRSAT: page_firsatlar, PAGE_HISSE: page_hisse, PAGE_TAKIP: page_takip,
 PAGE_BEKCI: page_bekci, PAGE_HABER: page_haberler, PAGE_GUNLUK: page_gunluk, PAGE_PERF: page_performans,
 PAGE_AYAR: page_ayarlar}.get(PAGE, page_dashboard)()

conn.close()
st.markdown("<div class='disclaimer'>Halley haberleri otomatik olarak özetler ve puanlar; yatırım tavsiyesi değildir. "
            "Puan eşikleri henüz geçmiş veriyle ayarlanmadı. Karar ve emir sorumluluğu kullanıcıdadır.</div>",
            unsafe_allow_html=True)
st.session_state["_render_sec"] = time.time() - _RENDER_T0
