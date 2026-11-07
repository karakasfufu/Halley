"""Halley — BIST haber paneli. Başlatmak için: baslat.bat (çift tıkla).

Sade düzen (2026-11-06): tek "Haberleri güncelle" düğmesi, 3 özet kutusu, olumlu/olumsuz hisse listeleri.
Ayarlar katlanır bölümde; durum ve geçmiş veri pilotu "Gelişmiş" sekmesinde.
"""
import os
from datetime import date, datetime
from html import escape as esc

import pandas as pd
import streamlit as st

from bist_haber import (analyzer, calendar_sync, config, corp_events, db, earnings, entries, kap_history,
                        kap_worker, macro_calendar, pipeline, report, technical, timeline, tradeplan)

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
    if quality != config.DEFAULT_QUALITY:
        st.caption("⚠️ Bu ayarda maliyet düşer ama analizler daha az ayrıntılı ve hata payı daha yüksek olabilir.")
    st.caption("Kaynaklar: KAP + " + ", ".join(config.RSS_SOURCE_LABELS.get(n, n) for n in config.RSS_FEEDS)
               + ". KAP hızlı isteklere sınır koyduğu için ilk güncelleme birkaç dakika sürebilir.")

if h2.button("🔄 Haberleri güncelle", type="primary", use_container_width=True):
    bar = st.progress(0.0, text="Başlıyor...")
    try:
        res = pipeline.update_all(conn, days=days, analysis_limit=analysis_limit, quality=quality,
                                  progress=lambda m, p: bar.progress(min(p, 1.0), text=m))
        st.session_state["last_update"] = datetime.now(config.TR_TZ).strftime("%H:%M")
        st.session_state["last_result"] = res
        if not os.environ.get("HALLEY_OFFLINE"):  # yarım kalan / boşluk sayfalarını arka planda tamamla
            kap_worker.start(force=bool(res.get("kap", {}).get("rate_limited") or res.get("takvim_boslugu", {}).get("eklenen")))
    except Exception as e:
        st.error(f"Güncelleme tamamlanamadı: {e}")
    conn.close()  # sayfa yenilenmeden önce bağlantıyı bırak (aksi hâlde açık kalıyordu)
    st.rerun()

if h2.button("🧪 Ücretsiz dene", use_container_width=True, key="free_check",
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
        st.warning("KAP geçici olarak istek sınırı uyguladı; kalan bildirimler arka planda, sınır kalkınca "
                   "kendiliğinden okunuyor (aşağıdaki durum kutusu). Tekrar basmanız gerekmez.")
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
    kap_reader_box()


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

tab_list, tab_news, tab_adv = st.tabs(["📈 Bugünün listesi", "📰 Haberler", "🔧 Gelişmiş"])


_TECH_CACHE = {}


def tech(ticker: str):
    """Teknik göstergeler (kodla hesaplanır, kredi harcamaz). Sayfa çiziminde bir kez hesaplanır."""
    if ticker not in _TECH_CACHE:
        _TECH_CACHE[ticker] = technical.for_ticker(conn, ticker)
    return _TECH_CACHE[ticker]


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
                 use_container_width=True)
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


_PLAN_CACHE = {}
_EARN_CACHE = {}
_EVENT_CACHE = {}
_TL_CACHE = {}


def macro_risk_line():
    """Parça B4: vade (15 işlem günü) içindeki piyasa geneli olaylar — tüm hisseler için aynı, bir kez hesaplanır."""
    if "macro" not in _TL_CACHE:
        _TL_CACHE["macro"] = timeline.macro_risk(datetime.now(config.TR_TZ).date(), 15)
    return _TL_CACHE["macro"]


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
                                    "Kaç işlem günü sonra": x["is_gunu_sonra"] if x["is_gunu_sonra"] else "—",
                                    "Kapsam": x["kapsam"], "Olay": x["olay"], "Ayrıntı": x["ayrinti"]}
                                   for x in tl["olaylar"]]), hide_index=True, use_container_width=True)
    notes = [n for n in ([("Takvimi henüz bilinmeyen: " + ", ".join(tl["bilinmeyen"])) if tl["bilinmeyen"] else None,
                          tl.get("tatil_notu"), tl.get("kap_boslugu")]) if n]
    if notes:
        st.caption(" · ".join(notes))


def corp_event(ticker: str) -> dict:
    """Parça B3: kayıtlı KAP bildirimlerinden genel kurul / kâr payı / sermaye artırımı tarihleri."""
    if ticker not in _EVENT_CACHE:
        _EVENT_CACHE[ticker] = corp_events.upcoming(conn, ticker)
    return _EVENT_CACHE[ticker]


def earning(ticker: str) -> dict:
    """Parça B2: bilanço yasal son tarihi ve açıklanıp açıklanmadığı (eldeki kayıtlardan)."""
    if ticker not in _EARN_CACHE:
        _EARN_CACHE[ticker] = earnings.status(conn, ticker)
    return _EARN_CACHE[ticker]


def scenario(r: dict) -> dict:
    """Haber + teknik + risk → SL/TP/vade senaryosu (kodla, kredi harcamaz)."""
    if r["ticker"] not in _PLAN_CACHE:
        imp = conn.execute("SELECT confidence, persistence, reason, published_at, effective_date FROM impacts WHERE ticker=? AND direction!=0 "
                           "ORDER BY published_at DESC LIMIT 1", (r["ticker"],)).fetchone()
        t_ = tech(r["ticker"])
        move = technical.news_moves_for(conn, r["ticker"], imp["effective_date"], t_.get("atr")) if imp and t_ else {}
        news_info = {"score": r["score"], "direction": 1 if r["score"] > 0 else (-1 if r["score"] < 0 else 0),
                     "confidence": imp["confidence"] if imp else None, "flags": r.get("flags", ""),
                     "persistence": imp["persistence"] if imp else "orta",
                     "reason": imp["reason"] if imp else "", "summary": r["last_news"], "hareket": move,
                     "bilanco_riski": earnings.window_risk(earning(r["ticker"]), datetime.now(config.TR_TZ).date(), 15),
                     "olay_riskleri": corp_events.risk_lines(corp_event(r["ticker"]), (t_ or {}).get("son_fiyat")),
                     "makro_riski": macro_risk_line(),
                     "temettu": [(e["tarih"], e["brut_tl"] / t_["son_fiyat"] * 100) for e in corp_event(r["ticker"])["yaklasan"]
                                 if e["tur"] == "temettu_hak" and e.get("brut_tl") and t_ and t_.get("son_fiyat")]}
        _PLAN_CACHE[r["ticker"]] = tradeplan.plan(tech(r["ticker"]), news_info)
    return _PLAN_CACHE[r["ticker"]]


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
        st.dataframe(pd.DataFrame(table).round(2), hide_index=True, use_container_width=True)
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
            f"<a href='{esc(i['url'])}' target='_blank'>haberin kaynağını aç</a></div></div>",
            unsafe_allow_html=True)


def stock_list(items: list, empty_text: str) -> None:
    if not items:
        st.caption(empty_text)
        return
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
    macro_block()
    if not rows:
        st.info("Henüz liste yok. Yukarıdaki **Haberleri güncelle** düğmesine basın.")
    else:
        summary_ = tradeplan.opportunity_summary({r["ticker"]: scenario(r) for r in positives})
        if summary_["uygun"]:
            st.success(f"Bugün {len(summary_['uygun'])} hissede uygun görünen giriş senaryosu var: "
                       + ", ".join(f"{tk} ({name.split(' (')[0].lower()}, risk {risk})" for tk, name, risk in summary_["uygun"])
                       + ". Ayrıntı için hisseye tıklayın. Bu bir senaryodur, yatırım tavsiyesi değildir.")
        else:
            st.info("**Bugün uygun işlem fırsatı bulunamadı.** Her gün işlem yapmak gerekmez. "
                    + ("Nedenler: " + "; ".join(f"{k} ({v} hisse)" for k, v in summary_["nedenler"].items()) + "."
                       if summary_["nedenler"] else "Olumlu haber alan hisse yok."))
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
              "skipped": "Atlandı (rutin/ilgisiz/eski)", "error": "Hata",
              "context": "Takvim için alındı (analiz edilmez)"}
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

    st.divider()
    st.markdown("#### 📅 Takvim kontrolü")
    st.caption("TCMB (faiz kararı, PPK özeti, Enflasyon ve Finansal İstikrar raporları) ve Fed takvimleri resmi "
               "sayfalardan okunur; panel açılışında günde bir kez kendiliğinden de kontrol edilir. Sayfa yapısı "
               "değişmişse ya da bir tarih okunamazsa hiçbir şey değiştirilmez. Ücretsizdir, yapay zekâ kullanmaz.")
    if st.button("📅 Takvimi şimdi kontrol et", key="calendar_check"):
        with st.spinner("Resmi sayfalar okunuyor..."):
            try:
                calendar_sync.check()
            except Exception as e:
                st.error(f"Kontrol tamamlanamadı: {e}")
    cal_state = calendar_sync.load()
    st.write(calendar_sync.summary_line())
    cal_rep = cal_state.get("report", {})
    if cal_rep:
        rows_cal = []
        for key, label in (("tcmb", "TCMB takvimi"), ("fed", "Fed (FOMC) takvimi")):
            r_ = cal_rep.get(key, {})
            detail = r_.get("neden") or ("; ".join(r_.get("farklar") or []) or "yerleşik takvimle aynı")
            rows_cal.append({"Kaynak": label, "Durum": r_.get("durum", "—"), "Ayrıntı": detail})
        for item in cal_rep.get("elle", []):
            rows_cal.append({"Kaynak": item.split(" (")[0], "Durum": "elle kontrol gerekir",
                             "Ayrıntı": item.split(" (", 1)[1].rstrip(")") if " (" in item else ""})
        st.dataframe(pd.DataFrame(rows_cal), hide_index=True, use_container_width=True)

    st.divider()
    st.markdown("#### 📥 Takvim için KAP geçmişi")
    ctx_total = conn.execute("SELECT COUNT(*) FROM news WHERE status='context'").fetchone()[0]
    ctx_missing = conn.execute("SELECT COUNT(*) FROM news WHERE status='context' AND body IS NULL").fetchone()[0]
    st.caption("Bilanço durumu ve şirket olayları (genel kurul, kâr payı, sermaye artırımı) için son 45 günün KAP "
               "bildirimlerini alır. Yapay zekâ KULLANMAZ, kredi harcamaz; kayıtlar analiz sırasına girmez. KAP bekleme "
               "süresi korunur. KAP sınır uygularsa okuyucu 3–10 dk bekleyip KENDİLİĞİNDEN devam eder; tamamlanınca "
               "üstte özet çıkar. Tekrar basmanız gerekmez.")
    st.write(f"Kayıtlı takvim bildirimi: {ctx_total} · form alanları okunmayı bekleyen: {ctx_missing}")
    if st.button("📥 Takvim için KAP geçmişini al (son 45 gün, ücretsiz)", key="kap_history"):
        bar = st.progress(0.0, text="KAP bildirim listesi alınıyor...")
        try:
            res = kap_history.backfill(conn, uni, days=45, fetch_pages=False,
                                       progress=lambda m, p_: bar.progress(min(1.0, p_), text=m))
            started = kap_worker.start(force=True) if not os.environ.get("HALLEY_OFFLINE") else False
            st.success(f"{res['eklenen']} yeni takvim bildirimi listeye eklendi. "
                       + ("Olay sayfaları arka planda okunuyor; ilerleme sayfanın üstündeki kutuda."
                          if started or kap_worker.running() else "Okunacak sayfa kalmadı."))
        except Exception as e:
            conn.rollback()
            st.error(f"KAP geçmişi alınamadı: {e}")

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
                    st.session_state["cheap_test_result"] = {"hata": str(e)}
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

conn.close()

with tab_adv:
    st.divider()
    st.markdown("### 🧪 Geçmiş veri pilotu")
    from bist_haber.backtest_ui import render as render_backtest
    render_backtest()

st.markdown("<div class='disclaimer'>Halley haberleri otomatik olarak özetler ve puanlar; yatırım tavsiyesi değildir. "
            "Puan eşikleri henüz geçmiş veriyle ayarlanmadı. Karar ve emir sorumluluğu kullanıcıdadır.</div>",
            unsafe_allow_html=True)
