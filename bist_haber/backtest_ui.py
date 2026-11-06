"""Kullanıcının komut satırı kullanmadan çalıştırabileceği pilot ekranı."""
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st

from . import backtest, config, pipeline, pilot_export


def render():
    st.markdown("#### Geçmiş KAP bildirimleri · doğruluk ve maliyet pilotu")
    st.info("Bu ilk aşama, belgelerin doğru okunmasını ve haber sonrası fiyat hareketlerini ölçer. "
            "Örneklenmiş bildirimlerle günlük skor eşikleri değiştirilmez.")
    today = datetime.now(config.TR_TZ).date()
    end_default = date(today.year, today.month, 1) - timedelta(days=32)
    start_default = date(end_default.year, end_default.month, 1)
    c1, c2, c3 = st.columns(3)
    start = c1.date_input("Başlangıç", start_default, key="bt_start")
    end = c2.date_input("Bitiş", end_default, key="bt_end")
    limit = c3.selectbox("En fazla bildirim", [100, 200], key="bt_limit")
    st.caption("En fazla 32 günlük aralık seçin; bitiş en az 21 gün önce olsun. "
               "Belgelerin hazırlanması API harcaması yapmaz. KAP sınırları nedeniyle birkaç dakika sürebilir.")
    conn = backtest.connect()
    try:
        if st.button("1 · Belgeleri hazırla / eksikleri yeniden dene", key="bt_prepare"):
            bar = st.progress(0.0, text="Başlıyor...")
            try:
                backtest.prepare(conn, start, end, limit, lambda m, p: bar.progress(min(1.0, p), text=m))
                st.success("Belge hazırlığı tamamlandı. Analize uygun ve eksik belgeler aşağıda.")
            except Exception as e:
                conn.rollback()
                st.error(f"Hazırlık tamamlanamadı: {e}")
        overview = backtest.overview(conn)
        selection = overview["metadata"].get("selection")
        if not selection:
            st.caption("Henüz pilot hazırlanmadı.")
            with st.expander("Yöntem ve bilinen sınırlar"):
                for item in backtest.LIMITATIONS:
                    st.write("• " + item)
            return
        st.caption(f"Hazırlanan örnek: {selection['start']} – {selection['end']} · "
                   f"{selection['eligible']} uygun bildirimden {selection['selected']} seçildi. "
                   "Yukarıdaki tarihleri değiştirmek mevcut örneği değiştirmez; hazırlama düğmesini kullanın.")
        c1, c2, c3 = st.columns(3)
        c1.metric("Analize hazır", overview["ready"])
        c2.metric("Analiz edildi", overview["analyzed"])
        c3.metric("Eksik / denetlenemedi", overview["incomplete"])
        money = overview["wallet"]
        st.write(f"**Pilot API bütçesi:** {money['charged_usd']:.4f} USD bilinen kullanım · "
                 f"{money['reserved_usd']:.4f} USD ayrılmış/belirsiz · "
                 f"{money['remaining_usd']:.4f} USD kalan (toplam sınır 1 USD).")
        st.caption("Model gpt-5-mini. Büyük/belirsiz kararlar ayrı ikinci analizle kontrol edilir. "
                   "Aynı belge, talimat ve görüş yeniden ücretlendirilmez. Bağlantısı kesilen çağrı "
                   "için ayrılan tutar korunur; otomatik tekrar yapılmaz. Kesilen yanıt sonuç sayılmaz.")
        st.caption("Her basışta en fazla 10 hazır bildirim işlenir. Sonraki grup kendiliğinden başlamaz. "
                   "Bu küçük tur veri/analiz kontrolü içindir; başarı oranı veya eşik seçimi için yeterli değildir.")
        if st.button("2 · Fiyatları al / yenile (OpenAI harcaması yok)", key="bt_prices"):
            try:
                with st.spinner("Geçmiş fiyatlar alınıyor..."):
                    count = backtest.update_prices(conn)
                st.success(f"{count} fiyat satırı alındı.")
                overview = backtest.overview(conn)
            except Exception as e:
                conn.rollback()
                st.error(f"Fiyatlar alınamadı: {e}")
        st.caption(f"Belgesi ve 10 işlem günlük fiyatı hazır: {overview['priced_ready']} · "
                   f"Fiyat dönemi eksik: {overview['missing_prices']}. "
                   "Fiyatı eksik bildirime analiz harcaması yapılmaz; kayıt korunur.")
        if overview["metadata"].get("collection_note"):
            st.warning(overview["metadata"]["collection_note"])
        can_analyze = pipeline.has_api_key() and overview["priced_ready"] > 0 and money["remaining_usd"] > 0
        if not pipeline.has_api_key():
            st.caption("Pilot analizi için soldaki alana OpenAI API anahtarınızı girin.")
        if st.button("3 · En fazla 10 bildirimi analiz et (ücretli)", disabled=not can_analyze, key="bt_analyze"):
            bar = st.progress(0.0, text="Başlıyor...")
            try:
                result = backtest.analyze(conn, lambda m, p: bar.progress(min(1.0, p), text=m))
                st.session_state["bt_analysis_result"] = result
                st.rerun()
            except Exception as e:
                st.error(f"Pilot durdu: {e}")
        if "bt_analysis_result" in st.session_state:
            result = st.session_state["bt_analysis_result"]
            st.write(f"Son turda analiz edilen: {result['analyzed']}")
            if result.get("stopped"):
                st.warning(result["stopped"])
        cost = st.selectbox("Toplam alış + satış maliyeti varsayımı", [0, 10, 20, 50], index=2,
                            format_func=lambda v: f"%{v / 100:.2f}", key="bt_cost")
        results = backtest.evaluate(conn, cost_bps=cost)
        exported = pilot_export.build_report(conn, results, cost_bps=cost)
        files = exported["files"]
        st.download_button("📦 Bütün pilot tablolarını ve yöntemi indir (ZIP)",
                           pilot_export.zip_bytes(files), file_name="halley_pilot_raporu.zip",
                           mime="application/zip", key="bt_all_download")
        st.caption("ZIP içinde dört dosya bulunur: olay sonuçları, pozitif olay özeti, belge eksikleri ve yöntem açıklaması. "
                   "İndirmek mevcut sonuçları kullanır; yeni analiz veya OpenAI harcaması başlatmaz.")
        if results:
            frame = exported["frame"]
            st.caption("Giriş: haberin yayımlandığı günden sonraki ilk endeks işlem gününün açılışı. "
                       "1 gün: o günün kapanışı; 5 gün: giriş dahil beşinci işlem gününün kapanışı. "
                       "Negatif/nötr olaylar açığa satış kazancı olarak hesaplanmaz.")
            st.warning("Eksik fiyatlı olaylar tabloda korunur. Yakın tarihli aynı hisse haberleri "
                       "birbirini etkileyebilir; bunlar bağımsız işlem veya portföy getirisi değildir.")
            summary = exported["summary"]
            if not summary.empty:
                st.write("**Pozitif olaylar · betimleyici sonuçlar (%)**")
                st.dataframe(summary, hide_index=True, use_container_width=True)
            else:
                st.info("Fiyat sonucu tam pozitif olay bulunmadığından pozitif özet boş.")
            st.download_button("Pozitif olay özetini indir (CSV)", files["halley_pozitif_ozet.csv"],
                               file_name="halley_pozitif_ozet.csv", mime="text/csv", key="bt_summary_download")
            st.write(f"**Tüm olay/vade satırları:** {len(frame)} · eksik: {(frame['eksik'] != '').sum()}")
            st.caption("Buradaki 'eksik' yalnızca fiyat sonuçlarını gösterir. Belgesi eksik veya henüz denetlenmemiş "
                       "bildirimler aşağıdaki ayrı listededir; 'eksik: 0' bütün belgelerin tam olduğu anlamına gelmez.")
            st.dataframe(frame, hide_index=True, use_container_width=True)
            st.download_button("Tüm olay sonuçlarını indir (CSV)", files["halley_pilot.csv"],
                               file_name="halley_pilot.csv", mime="text/csv", key="bt_download")
        with st.expander("Belge eksikleri ve yöntem"):
            details = exported["gaps"]
            if not details.empty:
                st.dataframe(details, hide_index=True, use_container_width=True)
            else:
                st.info("Seçili örnekte belge eksiği görünmüyor.")
            st.download_button("Belge eksiklerini indir (CSV)", files["halley_belge_eksikleri.csv"],
                               file_name="halley_belge_eksikleri.csv", mime="text/csv", key="bt_gaps_download")
            st.download_button("Yöntem açıklamasını indir (TXT)", files["halley_yontem.txt"],
                               file_name="halley_yontem.txt", mime="text/plain", key="bt_methods_download")
            for item in backtest.LIMITATIONS:
                st.write("• " + item)
            st.caption("API fiyat varsayımı (2026-11-06): milyon girdi tokenı 0,25 USD; "
                       "milyon çıktı tokenı 2 USD. Cache indirimi hesaba katılmadan ihtiyatlı hesaplanır. "
                       "Bu pilot Batch kullanmaz; Batch ve tam dönem kalibrasyonu sonraki aşamadır.")
    finally:
        conn.close()
