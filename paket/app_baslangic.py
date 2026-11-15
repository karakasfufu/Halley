"""Halley paneli (derlenmiş sürüm): panelin kodu app_kod.pyc dosyasındadır.
Kurulum paketinde app.py yerine bu dosya durur (paket/build_package.py). Panel kodu açılırken hata verirse (ör. bozuk
güncelleme) burada yakalanır ve bist_haber'e hiç dayanmadan "önceki sürüme dön" düğmesi gösterilir. Streamlit'in kendi
akış denetimi (yeniden çalıştırma/durdurma) BaseException olduğu için buraya takılmaz.
"""
import marshal as _m
import os as _os
import pathlib as _p
import subprocess as _sp

try:
    exec(_m.loads(_p.Path(__file__).with_name("app_kod.pyc").read_bytes()[16:]), globals())
except Exception as _hata:
    import streamlit as _st
    _kok = _p.Path(__file__).resolve().parent.parent
    _onceki = _kok / "guncelleme" / "onceki"
    _st.error("Halley'in bu sürümü açılırken bir hata oluştu. Verileriniz etkilenmedi.")
    if (_onceki / "app.py").exists():
        _st.markdown("Son güncellemeden önceki sürüme dönebilirsiniz; Halley kapanıp önceki sürümle yeniden açılır.")
        if _st.button("↩️ Önceki sürüme dön", type="primary"):
            (_kok / "guncelleme" / "geri_don.txt").write_text("panel hatası", encoding="utf-8")
            _sp.Popen(["cmd", "/c", "start", "", str(_kok / "Halley.exe"), "--yeniden-baslat"]
                      + _os.environ.get("HALLEY_BASLATICI_ARGS", "").split(), cwd=str(_kok),
                      creationflags=getattr(_sp, "CREATE_NO_WINDOW", 0), close_fds=True)
            _st.success("Halley birkaç saniye içinde önceki sürümle yeniden açılacak.")
    else:
        _st.markdown("Halley'i kapatıp yeniden açmayı deneyin; düzelmezse kurulum dosyasıyla yeniden kurun "
                     "(verileriniz korunur).")
    with _st.expander("Teknik ayrıntı (sorunu bildirirken ekleyin)"):
        _st.exception(_hata)
