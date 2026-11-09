// Halley başlatıcısı (2026-11-09). Paketin kökünde durur: python\ (gömülü Python 3.9) ve app\ (uygulama) klasörleriyle.
// Siyah pencere açmadan paneli ve KAP okuyucusunu başlatır, saatin yanına simge koyar, kapatınca hepsini kapatır.
// Derleme: Windows'taki .NET Framework 4 derleyicisi (csc.exe, C# 5). Bkz. paket/build_package.py.
//
// Komutlar:  Halley.exe                 → başlat (zaten açıksa yalnız paneli tarayıcıda açar)
//            Halley.exe --kapat         → açık olan Halley'i kapatır
//            Halley.exe --port 8503     → başka port (deneme için)
//            Halley.exe --tarayici-yok  → tarayıcıyı açma (deneme için)
//            Halley.exe --kaldir        → programı kaldırır (veriler isteğe bağlı korunur)
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Halley
{
    const string MutexName = "Local\\HalleyPanel_Tek";
    const string QuitEventName = "Local\\HalleyPanel_Kapat";
    const string OpenEventName = "Local\\HalleyPanel_Ac";

    static string Root, Py, App, LogDir;
    static int Port = 8501;
    static bool NoBrowser = false;
    static Process Panel, Reader;
    static NotifyIcon Tray;
    static volatile bool Quitting = false;

    [STAThread]
    static int Main(string[] args)
    {
        Root = AppDomain.CurrentDomain.BaseDirectory.TrimEnd('\\');
        Py = Path.Combine(Root, "python\\python.exe");
        App = Path.Combine(Root, "app");
        LogDir = Path.Combine(App, "data\\gunluk");
        bool quit = false, uninstall = false;
        for (int i = 0; i < args.Length; i++)
        {
            string a = args[i].ToLowerInvariant();
            if (a == "--kapat") quit = true;
            else if (a == "--kaldir") uninstall = true;
            else if (a == "--tarayici-yok") NoBrowser = true;
            else if (a == "--port" && i + 1 < args.Length) { Port = int.Parse(args[i + 1]); i++; }
        }
        if (quit) return SignalQuit(true) ? 0 : 1;
        if (uninstall) return Uninstall();

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
        if (!File.Exists(Py) || !File.Exists(Path.Combine(App, "app.py")))
        {
            MessageBox.Show("Halley dosyaları eksik görünüyor:\n" + Py + "\n\nLütfen Halley_Kurulum.exe ile yeniden kurun.",
                            "Halley", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 2;
        }
        Directory.CreateDirectory(LogDir);
        if (!PortFree(Port))
        {
            int p = Port;
            for (int k = 1; k <= 20 && !PortFree(p); k++) p = Port + k;
            Port = p;
        }

        Tray = new NotifyIcon();
        try { Tray.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { Tray.Icon = SystemIcons.Application; }
        Tray.Text = "Halley açılıyor…";
        ContextMenuStrip menu = new ContextMenuStrip();
        menu.Items.Add("Paneli aç", null, delegate { OpenBrowser(); });
        menu.Items.Add("Günlük klasörünü aç", null, delegate { Process.Start("explorer.exe", "\"" + LogDir + "\""); });
        menu.Items.Add(new ToolStripSeparator());
        menu.Items.Add("Halley'i kapat", null, delegate { Shutdown(); });
        Tray.ContextMenuStrip = menu;
        Tray.DoubleClick += delegate { OpenBrowser(); };
        Tray.Visible = true;

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
            Tray.Visible = false;
            MessageBox.Show("Halley başlatılamadı: " + e.Message, "Halley", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 3;
        }

        // kapat / aç sinyalleri (ikinci Halley.exe veya --kapat)
        EventWaitHandle quitEv = new EventWaitHandle(false, EventResetMode.AutoReset, QuitEventName);
        EventWaitHandle openEv = new EventWaitHandle(false, EventResetMode.AutoReset, OpenEventName);
        Control ui = new Control();    // arka plan iş parçacıklarından arayüze dönmek için (görünmez)
        ui.CreateControl();
        IntPtr unused = ui.Handle;
        new Thread(delegate ()
        {
            WaitHandle[] hs = new WaitHandle[] { quitEv, openEv };
            while (!Quitting)
            {
                int w = WaitHandle.WaitAny(hs, 1000);
                if (w == 0) { ui.BeginInvoke((MethodInvoker)delegate { Shutdown(); }); break; }
                if (w == 1) ui.BeginInvoke((MethodInvoker)delegate { OpenBrowser(); });
                if (Panel != null && Panel.HasExited && !Quitting)
                {
                    ui.BeginInvoke((MethodInvoker)delegate
                    {
                        if (Quitting) return;
                        MessageBox.Show("Halley paneli beklenmedik şekilde kapandı.\nAyrıntı: " + Path.Combine(LogDir, "panel.log"),
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
            ui.BeginInvoke((MethodInvoker)delegate
            {
                if (Quitting) return;
                if (ok)
                {
                    Tray.Text = "Halley açık (sağ tık: menü)";
                    if (!NoBrowser) OpenBrowser();
                    Tray.ShowBalloonTip(4000, "Halley açık", "Panel tarayıcıda açıldı. Kapatmak için saatin yanındaki Halley simgesine sağ tıklayın.", ToolTipIcon.Info);
                }
                else
                {
                    MessageBox.Show("Halley paneli 2 dakikada açılamadı.\nAyrıntı: " + Path.Combine(LogDir, "panel.log"),
                                    "Halley", MessageBoxButtons.OK, MessageBoxIcon.Warning);
                    Shutdown();
                }
            });
        }) { IsBackground = true }.Start();
        Application.ApplicationExit += delegate { KillAll(); };
        Application.Run(new ApplicationContext());
        KillAll();
        Tray.Visible = false;
        return 0;
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

    static void OpenBrowser()
    {
        try { Process.Start("http://localhost:" + Port); } catch { }
    }

    static void Shutdown()
    {
        if (Quitting) return;
        Quitting = true;
        try { Tray.Text = "Halley kapanıyor…"; } catch { }
        KillAll();
        try { Tray.Visible = false; } catch { }
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

    static bool SignalQuit(bool wait)
    {
        try
        {
            EventWaitHandle.OpenExisting(QuitEventName).Set();
            if (wait)
            {
                for (int i = 0; i < 40; i++)
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
