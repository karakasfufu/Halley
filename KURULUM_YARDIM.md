# Halley — kurulum yardımı (Windows)

## 1. Doğru dosyayı indirin
- Depo **özeldir**: indirmeden önce GitHub'a **size davet gönderilen hesapla giriş yapın**. Giriş yapmadan bağlantı
  "404 – sayfa bulunamadı" der.
- Sürüm sayfasında **Assets** başlığının altındaki **`Halley_Kurulum.exe`** dosyasını indirin (yaklaşık 147 MB).
  "Source code (zip)" ya da yeşil "Code → Download ZIP" **kurulum dosyası değildir**; onlar çalışmaz.
- Tarayıcı "yaygın olarak indirilmiyor / tehlikeli olabilir" derse: indirilenler listesinde dosyanın yanındaki
  menüden **Sakla** (Keep) → **Yine de sakla**.

## 2. Windows'un engelini kaldırın (en sık sorun)
Halley imzasız bir programdır. Windows, internetten inen imzasız programı **Defender kapalı olsa bile** durdurur;
bunu Defender değil **SmartScreen** yapar.
1. İndirilen `Halley_Kurulum.exe`'ye **sağ tıklayın → Özellikler**.
2. **Genel** sekmesinin en altında **"Güvenlik: Bu dosya başka bir bilgisayardan geldi…"** satırı varsa yanındaki
   **Engellemeyi kaldır** kutusunu işaretleyin → **Tamam**.
3. Dosyaya çift tıklayın. Yine de mavi "Windows bilgisayarınızı korudu" penceresi çıkarsa: **Ek bilgi → Yine de
   çalıştır**.
4. Kurulum penceresinde **Kur** (ya da Halley kuruluysa **Güncelle**). Verileriniz korunur.

## 3. Hâlâ açılmıyorsa
- **Windows 11'de "Akıllı Uygulama Denetimi"** (Smart App Control) açıksa imzasız programlar hiç çalıştırılamaz ve
  "Yine de çalıştır" seçeneği çıkmaz. Kontrol: Ayarlar → Gizlilik ve güvenlik → Windows Güvenliği → Uygulama ve
  tarayıcı denetimi → **Akıllı Uygulama Denetimi ayarları**. "Açık" yazıyorsa bize bildirin; bu ayarı kapatmak sizin
  kararınızdır (kapatılınca Windows sıfırlanmadan yeniden açılamaz). Kalıcı çözüm, programın imzalanmasıdır.
- Kurulum bir hata mesajı verdiyse şu dosyayı gönderin: `%TEMP%\halley_kurulum.log` (Başlat → Çalıştır →
  `%TEMP%` yazın → listede `halley_kurulum.log`). Hata mesajının ekran görüntüsü de yeterli.
- Dosyanın bozulmadan indiğini kontrol etmek için (isteğe bağlı): PowerShell'de
  `Get-FileHash "$env:USERPROFILE\Downloads\Halley_Kurulum.exe"` → çıkan kod sürüm notundaki SHA-256 ile aynı olmalı.

## 4. Kurulduktan sonra
- Masaüstündeki **Halley** simgesiyle açın. İlk açılışta OpenAI API anahtarını girin.
- Eski bilgisayardaki verileri taşımak için: ⚙️ Ayarlar → 💾 Veri ve gelişmiş → **İçe aktar**.
