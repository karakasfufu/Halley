// Halley uygulaması (2026-11-09). Paketin kökünde durur: python\ (gömülü Python 3.9) ve app\ (uygulama) klasörleriyle.
// Kendi "Halley" penceresini açar (Windows'un Microsoft WebView2 bileşeniyle; tarayıcı/adres çubuğu yok), paneli ve
// KAP okuyucusunu siyah pencere olmadan arka planda çalıştırır. Pencere kapanınca hepsi kapanır.
// Derleme: Windows'taki .NET Framework 4 derleyicisi (csc.exe, C# 5) + paket/webview2/ (Microsoft imzalı DLL'ler).
//
// Komutlar:  Halley.exe                 → başlat (zaten açıksa açık pencereyi öne getirir)
//            Halley.exe --kapat         → açık olan Halley'i kapatır
//            Halley.exe --port 8503     → başka port (deneme için)
//            Halley.exe --pencere-yok   → pencere açmadan yalnız arka planı çalıştır (deneme için)
//            Halley.exe --kaldir        → programı kaldırır (veriler isteğe bağlı korunur)
//            Halley.exe --yeniden-baslat → açık Halley'i kapatır, bekleyen güncellemeyi/geri dönüşü uygular, yeniden açar
// Güncelleme (2026-11-15): panel yeni kodu guncelleme\yeni'ye hazırlar (bist_haber/guncelleme.py); dosya değişimini
// burada, hiçbir şey çalışmazken yaparız. Eski kod guncelleme\onceki'de kalır; yeni sürüm 2 dakikada açılmazsa
// kendiliğinden önceki sürüme dönülür. app\data ve app\.env hiçbir zaman taşınmaz.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

static class Halley
{
    const string MutexName = "Local\\HalleyPanel_Tek";
    const string QuitEventName = "Local\\HalleyPanel_Kapat";
    const string OpenEventName = "Local\\HalleyPanel_Ac";

    internal static string Root, Py, App, LogDir;
    static int Port = 8501;
    static string ExtraArgs = "";    // yeniden başlatmada korunacak seçenekler (--port, --pencere-yok)
    static bool NoWindow = false;
    static Process Panel, Reader;
    static Control Ui;
    static MainForm Window;
    internal static volatile bool Quitting = false;

    [STAThread]
    static int Main(string[] args)
    {
        Root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        Py = Path.Combine(Root, "python\\python.exe");
        App = Path.Combine(Root, "app");
        LogDir = Path.Combine(App, "data\\gunluk");
        bool quit = false, uninstall = false, restart = false;
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i].ToLowerInvariant();
            if (a == "--kapat") quit = true;
            else if (a == "--kaldir") uninstall = true;
            else if (a == "--yeniden-baslat") restart = true;
            else if (a == "--pencere-yok" || a == "--tarayici-yok") NoWindow = true;
            else if (a == "--port" && i + 1 < args.Length) { Port = int.Parse(args[i + 1]); i++; }
        }
        if (Port != 8501) ExtraArgs += " --port " + Port;
        if (NoWindow) ExtraArgs += " --pencere-yok";
        if (quit) return SignalQuit(true) ? 0 : 1;
        if (uninstall) return Uninstall();
        if (restart) SignalQuit(true, 120);      // açık olan tamamen kapanana kadar bekle (en fazla ~60 sn)

        bool created;
        using (Mutex m = new Mutex(true, MutexName, out created))
        {
            if (!created)
            {   // zaten açık: açık olana "paneli göster" de
                try { EventWaitHandle.OpenExisting(OpenEventName).Set(); } catch { }
                return 0;
            }
            return Run();
        }
    }

    static int Run()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        if (!File.Exists(Py) || !File.Exists(Path.Combine(App, "app.py")))
        {
            MessageBox.Show("Halley dosyaları eksik görünüyor:\n" + Py + "\n\nLütfen Halley_Kurulum.exe ile yeniden kurun.",
                            "Halley", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
        Directory.CreateDirectory(LogDir);
        ApplyPending();
        if (!PortFree(Port))
        {
            int p = Port;
            for (int k = 1; k <= 20 && !PortFree(p); k++) p = Port + k;
            Port = p;
        }
        if (!NoWindow) { Window = new MainForm(); Window.Show(); Application.DoEvents(); }   // pencere hemen görünsün
        try
        {
            Reader = Start(new string[] { "-m", "bist_haber", "okuyucu" }, "okuyucu.log");
            Panel = Start(new string[] { "-m", "streamlit", "run", "app.py", "--server.port", Port.ToString(),
                                         "--server.address", "127.0.0.1", "--server.headless", "true",
                                         "--browser.gatherUsageStats", "false" }, "panel.log");
        }
        catch (Exception e)
        {
            KillAll();
            MessageBox.Show("Halley başlatılamadı: " + e.Message, "Halley", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 3;
        }
        EventWaitHandle quitEv = new EventWaitHandle(false, EventResetMode.AutoReset, QuitEventName);
        EventWaitHandle openEv = new EventWaitHandle(false, EventResetMode.AutoReset, OpenEventName);
        if (Window != null) Ui = Window;
        else { Ui = new Control(); Ui.CreateControl(); }
        IntPtr unused = Ui.Handle;
        StartWatchers(quitEv, openEv);
        Application.ApplicationExit += delegate { KillAll(); };
        if (Window != null) Application.Run(Window); else Application.Run(new ApplicationContext());
        KillAll();
        return 0;
    }

    static void StartWatchers(EventWaitHandle quitEv, EventWaitHandle openEv)
    {
        new Thread(delegate ()
        {
            WaitHandle[] hs = new WaitHandle[] { quitEv, openEv };
            while (!Quitting)
            {
                int w = WaitHandle.WaitAny(hs, 1000);
                if (w == 0) { Ui.BeginInvoke((MethodInvoker)delegate { Shutdown(); }); break; }
                if (w == 1) Ui.BeginInvoke((MethodInvoker)delegate { BringToFront(); });
                if (Panel != null && Panel.HasExited && !Quitting && !File.Exists(Path.Combine(G, "denetim.txt")))
                {
                    Ui.BeginInvoke((MethodInvoker)delegate
                    {
                        if (Quitting) return;
                        MessageBox.Show("Halley beklenmedik şekilde kapandı.\nAyrıntı: " + Path.Combine(LogDir, "panel.log"),
                                        "Halley", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        Shutdown();
                    });
                    break;
                }
            }
        }) { IsBackground = true }.Start();
        new Thread(delegate ()
        {
            bool ok = WaitHealthy(120);
            Ui.BeginInvoke((MethodInvoker)delegate
            {
                if (Quitting) return;
                string denetim = Path.Combine(G, "denetim.txt");
                if (File.Exists(denetim))
                {   // güncellemeden sonraki ilk açılış
                    if (ok) { TryDelete(denetim); Record("guncellendi"); }
                    else
                    {
                        KillAll();
                        string err = "";
                        try { Swap(Path.Combine(G, "onceki"), Path.Combine(G, "acilmayan")); Record("otomatik_geri_donuldu"); }
                        catch (Exception e) { err = "\n\nGeri dönüş de başarısız: " + e.Message; }
                        TryDelete(denetim);
                        MessageBox.Show("Yeni sürüm açılamadı; önceki sürüme dönüldü. Halley yeniden açılıyor." + err +
                                        "\nAyrıntı: " + Path.Combine(LogDir, "panel.log"), "Halley",
                                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
                        try { Process.Start(new ProcessStartInfo(Path.Combine(Root, "Halley.exe"), "--yeniden-baslat" + ExtraArgs) { UseShellExecute = false }); } catch { }
                        Shutdown();
                        return;
                    }
                }
                if (ok) { if (Window != null) Window.Ready("http://127.0.0.1:" + Port); }
                else
                {
                    MessageBox.Show("Halley 2 dakikada açılamadı.\nAyrıntı: " + Path.Combine(LogDir, "panel.log"),
                                    "Halley", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    Shutdown();
                }
            });
        }) { IsBackground = true }.Start();
    }

    static void BringToFront()
    {
        if (Window == null) return;
        if (Window.WindowState == FormWindowState.Minimized) Window.WindowState = FormWindowState.Normal;
        Window.Activate();
    }

    static Process Start(string[] args, string logName)
    {
        ProcessStartInfo si = new ProcessStartInfo(Py);
        StringBuilder sb = new StringBuilder();
        foreach (string a in args) { if (sb.Length > 0) sb.Append(' '); sb.Append(a.Contains(" ") ? "\"" + a + "\"" : a); }
        si.Arguments = sb.ToString();
        si.WorkingDirectory = App;
        si.UseShellExecute = false;
        si.CreateNoWindow = true;
        si.RedirectStandardOutput = true;
        si.RedirectStandardError = true;
        si.StandardOutputEncoding = Encoding.UTF8;
        si.StandardErrorEncoding = Encoding.UTF8;
        // bilgisayardaki başka Python kurulumları karışmasın
        si.EnvironmentVariables.Remove("PYTHONHOME");
        si.EnvironmentVariables.Remove("PYTHONPATH");
        si.EnvironmentVariables["PYTHONNOUSERSITE"] = "1";
        si.EnvironmentVariables["PYTHONUTF8"] = "1";
        si.EnvironmentVariables["PYTHONIOENCODING"] = "utf-8";
        si.EnvironmentVariables["PYTHONDONTWRITEBYTECODE"] = "1";
        si.EnvironmentVariables["HALLEY_BASLATICI_ARGS"] = ExtraArgs.Trim();   // panel yeniden başlatırken aynı seçenekler
        string logPath = Path.Combine(LogDir, logName);
        try { if (File.Exists(logPath) && new FileInfo(logPath).Length > 5 * 1024 * 1024) File.Delete(logPath); } catch { }
        StreamWriter log = new StreamWriter(logPath, true, new UTF8Encoding(false));
        log.AutoFlush = true;
        log.WriteLine("---- " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " başlatıldı: python " + si.Arguments);
        Process p = new Process();
        p.StartInfo = si;
        object gate = new object();
        DataReceivedEventHandler h = delegate (object s, DataReceivedEventArgs e) { if (e.Data != null) lock (gate) { try { log.WriteLine(e.Data); } catch { } } };
        p.OutputDataReceived += h;
        p.ErrorDataReceived += h;
        p.Start();
        p.BeginOutputReadLine();
        p.BeginErrorReadLine();
        return p;
    }

    static bool PortFree(int port)
    {
        // 2026-11-09 denemede bulundu: başka program portu 0.0.0.0 / :: üzerinde dinlerken 127.0.0.1'e bağlanmak
        // Windows'ta yine de başarılı oluyor (iki sunucu aynı portta). Bu yüzden: önce bağlanmayı dene (biri cevap
        // veriyorsa dolu), sonra portu tüm arayüzlerde özel kullanımla açmayı dene.
        foreach (IPAddress ip in new IPAddress[] { IPAddress.Loopback, IPAddress.IPv6Loopback })
        {
            try
            {
                using (TcpClient c = new TcpClient(ip.AddressFamily))
                {
                    IAsyncResult r = c.BeginConnect(ip, port, null, null);
                    if (r.AsyncWaitHandle.WaitOne(400) && c.Connected) return false;
                }
            }
            catch { }
        }
        try
        {
            TcpListener l = new TcpListener(IPAddress.Any, port);
            l.ExclusiveAddressUse = true;
            l.Start(); l.Stop();
            return true;
        }
        catch { return false; }
    }

    static bool WaitHealthy(int seconds)
    {
        DateTime end = DateTime.Now.AddSeconds(seconds);
        while (DateTime.Now < end && !Quitting)
        {
            if (Panel != null && Panel.HasExited) return false;
            try
            {
                HttpWebRequest r = (HttpWebRequest)WebRequest.Create("http://127.0.0.1:" + Port + "/_stcore/health");
                r.Timeout = 3000;
                r.Proxy = null;
                using (HttpWebResponse resp = (HttpWebResponse)r.GetResponse())
                    if (resp.StatusCode == HttpStatusCode.OK) return true;
            }
            catch { }
            Thread.Sleep(700);
        }
        return false;
    }

    internal static void Shutdown()
    {
        if (Quitting) return;
        Quitting = true;
        KillAll();
        if (Window != null) { try { Window.Close(); } catch { } }
        Application.Exit();
    }

    static void KillAll()
    {
        foreach (Process p in new Process[] { Panel, Reader })
        {
            if (p == null) continue;
            try
            {
                if (!p.HasExited)
                {   // alt süreçlerle birlikte kapat
                    Process k = Process.Start(new ProcessStartInfo("taskkill", "/T /F /PID " + p.Id) { CreateNoWindow = true, UseShellExecute = false });
                    k.WaitForExit(10000);
                    if (!p.HasExited) p.Kill();
                }
            }
            catch { }
        }
    }

    static bool SignalQuit(bool wait) { return SignalQuit(wait, 40); }

    static bool SignalQuit(bool wait, int tries)
    {
        try
        {
            EventWaitHandle.OpenExisting(QuitEventName).Set();
            if (wait)
            {
                for (int i = 0; i < tries; i++)
                {
                    bool createdNew;
                    using (Mutex m = new Mutex(false, MutexName, out createdNew)) { if (createdNew) return true; }
                    Thread.Sleep(500);
                }
            }
            return true;
        }
        catch (WaitHandleCannotBeOpenedException) { return true; }   // zaten kapalı
    }

    // ---------------------------------------------------------------- uygulama içi güncelleme (2026-11-15)
    internal static string G { get { return Path.Combine(Root, "guncelleme"); } }
    static readonly string[] Keep = new string[] { "data", ".env" };

    static void TryDelete(string f) { try { if (File.Exists(f)) File.Delete(f); } catch { } }

    static void CopyIf(string a, string b) { try { if (File.Exists(a)) File.Copy(a, b, true); } catch { } }

    static void MoveCode(string from, string to)
    {   // from içindeki her şeyi (data ve .env hariç) to'ya taşı
        Directory.CreateDirectory(to);
        foreach (string d in Directory.GetDirectories(from))
        {
            string n = Path.GetFileName(d), dst = Path.Combine(to, n);
            if (Array.IndexOf(Keep, n.ToLowerInvariant()) >= 0) continue;
            if (Directory.Exists(dst)) Directory.Delete(dst, true);
            Directory.Move(d, dst);
        }
        foreach (string f in Directory.GetFiles(from))
        {
            string n = Path.GetFileName(f), dst = Path.Combine(to, n);
            if (Array.IndexOf(Keep, n.ToLowerInvariant()) >= 0) continue;
            if (File.Exists(dst)) File.Delete(dst);
            File.Move(f, dst);
        }
    }

    // incoming klasöründeki kodu app\'e koy; app\'teki kod outgoing'e gider. Sürüm dosyaları kodla birlikte taşınır.
    static void Swap(string incoming, string outgoing)
    {
        if (!File.Exists(Path.Combine(incoming, "app.py"))) throw new Exception("kurulacak kod eksik: " + incoming);
        CopyIf(Path.Combine(Root, "surum.txt"), Path.Combine(App, "surum.txt"));
        CopyIf(Path.Combine(Root, "surum_sira.txt"), Path.Combine(App, "surum_sira.txt"));
        if (Directory.Exists(outgoing)) Directory.Delete(outgoing, true);
        try
        {
            MoveCode(App, outgoing);
            MoveCode(incoming, App);
        }
        catch
        {   // yarım kaldıysa eski hâline getirmeyi dene
            try { MoveCode(App, incoming); MoveCode(outgoing, App); } catch { }
            throw;
        }
        try { Directory.Delete(incoming, true); } catch { }
        CopyIf(Path.Combine(App, "surum.txt"), Path.Combine(Root, "surum.txt"));
        CopyIf(Path.Combine(App, "surum_sira.txt"), Path.Combine(Root, "surum_sira.txt"));
    }

    static void Record(string islem)
    {
        try
        {
            string f = Path.Combine(Root, "surum.txt");
            string surum = File.Exists(f) ? File.ReadAllText(f).Trim() : "";
            File.WriteAllText(Path.Combine(G, "son_islem.json"), "{\"islem\": \"" + islem + "\", \"surum\": \"" +
                              surum.Replace("\\", "/").Replace("\"", "'") + "\", \"zaman\": \"" +
                              DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss") + "\"}", new UTF8Encoding(false));
        }
        catch { }
    }

    static void ApplyPending()
    {
        string geri = Path.Combine(G, "geri_don.txt"), hazir = Path.Combine(G, "hazir.json");
        try
        {
            if (File.Exists(geri))
            {
                TryDelete(geri);
                TryDelete(hazir);
                Swap(Path.Combine(G, "onceki"), Path.Combine(G, "geri_alinan"));
                Record("geri_donuldu");
            }
            else if (File.Exists(hazir))
            {
                TryDelete(hazir);
                Swap(Path.Combine(G, "yeni"), Path.Combine(G, "onceki"));
                File.WriteAllText(Path.Combine(G, "denetim.txt"), DateTime.Now.ToString("s"));
            }
        }
        catch (Exception e)
        {
            Record("hata");
            MessageBox.Show("Güncelleme uygulanamadı; mevcut sürümle devam ediliyor.\n" + e.Message, "Halley",
                            MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    static int Uninstall()
    {
        if (MessageBox.Show("Halley bu bilgisayardan kaldırılsın mı?", "Halley'i kaldır", MessageBoxButtons.YesNo,
                            MessageBoxIcon.Question) != DialogResult.Yes) return 1;
        bool keepData = MessageBox.Show("Verileriniz (haber analizleri, işlem günlüğü, raporlar, ayarlar ve API anahtarı) " +
                                        "korunsun mu?\n\nEvet: veriler 'Belgeler\\Halley_yedek' klasörüne taşınır.\nHayır: veriler de silinir.",
                                        "Halley'i kaldır", MessageBoxButtons.YesNo, MessageBoxIcon.Question) == DialogResult.Yes;
        SignalQuit(true);
        try
        {
            if (keepData)
            {
                string dst = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.MyDocuments),
                                          "Halley_yedek_" + DateTime.Now.ToString("yyyy-MM-dd_HHmm"));
                Directory.CreateDirectory(dst);
                if (Directory.Exists(Path.Combine(App, "data"))) Directory.Move(Path.Combine(App, "data"), Path.Combine(dst, "data"));
                if (File.Exists(Path.Combine(App, ".env"))) File.Move(Path.Combine(App, ".env"), Path.Combine(dst, ".env"));
                MessageBox.Show("Verileriniz şuraya taşındı:\n" + dst, "Halley", MessageBoxButtons.OK, MessageBoxIcon.Information);
            }
            foreach (string lnk in new string[] {
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "Halley.lnk"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Halley\\Halley.lnk"),
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Halley\\Halley'i kaldır.lnk") })
                try { if (File.Exists(lnk)) File.Delete(lnk); } catch { }
            try { Directory.Delete(Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Halley"), true); } catch { }
            // çalışan exe kendini silemez: kısa bir komutla, kapandıktan sonra klasörü sil
            string cmd = "/c timeout /t 3 /nobreak >nul & rmdir /s /q \"" + Root + "\"";
            Process.Start(new ProcessStartInfo("cmd.exe", cmd) { CreateNoWindow = true, UseShellExecute = false, WorkingDirectory = Path.GetTempPath() });
            return 0;
        }
        catch (Exception e)
        {
            MessageBox.Show("Kaldırma tamamlanamadı: " + e.Message, "Halley", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 4;
        }
    }
}


// Halley penceresi: içerik Windows'un WebView2 bileşeniyle çizilir; dış bağlantılar (haber kaynağı) varsayılan
// tarayıcıda açılır. WebView2 yoksa (çok eski Windows 10) panel varsayılan tarayıcıda açılır ve bu pencere bilgi verir.
class MainForm : Form
{
    readonly WebView2 web = new WebView2();
    readonly Label status = new Label();
    string pendingUrl;
    bool coreReady, fallback;
    bool? darkTitle;
    readonly System.Windows.Forms.Timer themeTimer = new System.Windows.Forms.Timer();

    [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h, int attr, ref int val, int size);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);

    // Başlık çubuğu panelin temasına uyar (Karanlık mod → koyu başlık). Ayar app\data\ayarlar.json'dan okunur.
    void SyncTitleBar()
    {
        bool dark = false;
        try
        {
            string f = Path.Combine(Halley.App, "data\\ayarlar.json");
            if (File.Exists(f)) dark = System.Text.RegularExpressions.Regex.IsMatch(File.ReadAllText(f), "\"karanlik_mod\"\\s*:\\s*true");
        }
        catch { }
        if (darkTitle.HasValue && darkTitle.Value == dark) return;
        darkTitle = dark;
        int v = dark ? 1 : 0;
        try
        {
            if (DwmSetWindowAttribute(Handle, 20, ref v, 4) != 0) DwmSetWindowAttribute(Handle, 19, ref v, 4);  // Win10 eski sürüm
            SetWindowPos(Handle, IntPtr.Zero, 0, 0, 0, 0, 0x0001 | 0x0002 | 0x0004 | 0x0020);              // çerçeveyi yenile
        }
        catch { }
    }

    public MainForm()
    {
        Text = "Halley";
        try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
        StartPosition = FormStartPosition.CenterScreen;
        Rectangle wa = Screen.PrimaryScreen.WorkingArea;
        ClientSize = new Size(Math.Min(1380, wa.Width - 40), Math.Min(900, wa.Height - 40));
        MinimumSize = new Size(900, 600);
        BackColor = Color.FromArgb(13, 19, 34);
        status.Dock = DockStyle.Fill;
        status.TextAlign = ContentAlignment.MiddleCenter;
        status.ForeColor = Color.FromArgb(226, 232, 240);
        status.Font = new Font("Segoe UI", 15f);
        status.Text = "Halley açılıyor…";
        web.Dock = DockStyle.Fill;
        web.DefaultBackgroundColor = Color.FromArgb(13, 19, 34);
        Controls.Add(web);
        Controls.Add(status);
        status.BringToFront();   // panel çizilene kadar Halley açılış ekranı üstte (WebView2 gizlenirse sayfa yavaşlayabilir)
        HandleCreated += (s, e) => SyncTitleBar();
        themeTimer.Interval = 1500;
        themeTimer.Tick += (s, e) => SyncTitleBar();
        themeTimer.Start();
        Shown += async (s, e) => await InitWeb();
        FormClosing += (s, e) => { if (!Halley.Quitting) Halley.Shutdown(); };
    }

    async Task InitWeb()
    {
        try
        {
            string udf = Path.Combine(Halley.App, "data\\pencere");
            Directory.CreateDirectory(udf);
            CoreWebView2Environment env = await CoreWebView2Environment.CreateAsync(null, udf);
            await web.EnsureCoreWebView2Async(env);
            CoreWebView2Settings st = web.CoreWebView2.Settings;
            st.AreDevToolsEnabled = false;
            st.IsStatusBarEnabled = false;
            st.IsZoomControlEnabled = true;
            web.CoreWebView2.NewWindowRequested += (s, e) => { e.Handled = true; OpenExternal(e.Uri); };
            web.CoreWebView2.NavigationStarting += (s, e) =>
            {   // panel dışına giden bağlantılar uygulama içinde değil, tarayıcıda açılsın
                if (pendingUrl != null && !e.Uri.StartsWith(pendingUrl)) { e.Cancel = true; OpenExternal(e.Uri); }
            };
            web.CoreWebView2.NavigationCompleted += (s, e) => WaitForContent();
            coreReady = true;
            if (pendingUrl != null) web.CoreWebView2.Navigate(pendingUrl);
        }
        catch (WebView2RuntimeNotFoundException)
        {
            Fallback("Bu bilgisayarda Microsoft WebView2 bileşeni bulunamadı.\nHalley şimdilik varsayılan tarayıcıda açılacak.\n\n" +
                     "Bileşeni Microsoft'tan ücretsiz kurmak için: https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n" +
                     "Bu pencereyi kapatınca Halley kapanır.");
        }
        catch (Exception ex)
        {
            Fallback("Halley penceresi hazırlanamadı (" + ex.Message + ").\nHalley varsayılan tarayıcıda açılacak.\n\n" +
                     "Bu pencereyi kapatınca Halley kapanır.");
        }
    }

    // Sayfa iskeleti yüklenince değil, panelin kendisi (üst bant) çizilince göster: arada boş beyaz sayfa görünmesin.
    readonly System.Windows.Forms.Timer contentTimer = new System.Windows.Forms.Timer();
    DateTime contentWaitStart;

    void WaitForContent()
    {
        if (!status.Visible) return;
        contentWaitStart = DateTime.Now;
        contentTimer.Interval = 400;
        contentTimer.Tick -= ContentTick;
        contentTimer.Tick += ContentTick;
        contentTimer.Start();
    }

    async void ContentTick(object sender, EventArgs e)
    {
        contentTimer.Stop();
        bool ready = false;
        try
        {
            string r = await web.CoreWebView2.ExecuteScriptAsync(
                "!!(document.querySelector('.hero') || document.querySelector('[data-testid=\"stException\"]'))");
            ready = r == "true";
        }
        catch { }
        if (ready || (DateTime.Now - contentWaitStart).TotalSeconds > 120)
        {
            status.Visible = false;
        }
        else contentTimer.Start();
    }

    void Fallback(string msg)
    {
        fallback = true;
        status.Font = new Font("Segoe UI", 11f);
        status.Text = msg;
        if (pendingUrl != null) OpenExternal(pendingUrl);
    }

    static void OpenExternal(string url)
    {
        try { Process.Start(url); } catch { }
    }

    public void Ready(string url)
    {
        pendingUrl = url;
        if (coreReady) web.CoreWebView2.Navigate(url);
        else if (fallback) OpenExternal(url);
    }
}
