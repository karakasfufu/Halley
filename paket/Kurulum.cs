// Halley kurulum programı (2026-11-09). İçine gömülü payload.zip'i kullanıcı klasörüne açar (yönetici izni gerekmez).
// Kuruluysa GÜNCELLER (kullanıcı isteği: "kuruluysa üstüne yazsın, tekrar tekrar kurulmasın; eski veriler
// kaybolmasın"): her zaman aynı klasör; açık Halley ve arka plan işlemleri kapatılır; güncellemeden ÖNCE veriler
// app\data\yedek\guncelleme_oncesi_<zaman>\ altına yedeklenir; app\data\ altındaki MEVCUT dosyalara ve app\.env'e
// (OpenAI / Telegram anahtarları) dokunulmaz; güncellemeden SONRA veri dosyaları denetlenir, eksik varsa yedekten
// geri konur. Aynı sürüm zaten kuruluysa yeniden kurmaz (isterse "Yeniden kur").
// Komutlar: Halley_Kurulum.exe [/sessiz] [/hedef=KLASÖR] [/kisayolsuz] [/baslatma] [/zorla]
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Threading;
using System.Windows.Forms;

static class Kurulum
{
    static string Target = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "Programs\\Halley");
    static bool Silent = false, NoShortcuts = false, NoLaunch = false, Force = false;
    const int KeepBackups = 3;

    [STAThread]
    static int Main(string[] args)
    {
        foreach (string a in args)
        {
            string l = a.ToLowerInvariant();
            if (l == "/sessiz") Silent = true;
            else if (l == "/kisayolsuz") NoShortcuts = true;
            else if (l == "/baslatma") NoLaunch = true;
            else if (l == "/zorla") Force = true;
            else if (l.StartsWith("/hedef=")) Target = a.Substring(7).Trim('"');
        }
        if (Silent)
        {
            string log = Path.Combine(Path.GetTempPath(), "halley_kurulum.log");
            try
            {
                if (IsInstalled() && !Force && InstalledVersion() == NewVersion())
                {
                    File.WriteAllText(log, "ZATEN GUNCEL: " + NewVersion() + " " + Target);
                    return 0;
                }
                string r = Install(null);
                File.WriteAllText(log, "KURULUM TAMAM: " + Target + "\r\n" + r);
                return 0;
            }
            catch (Exception e) { File.WriteAllText(log, "KURULUM HATASI: " + e); return 1; }
        }
        Application.EnableVisualStyles();
        Application.Run(new SetupForm());
        return 0;
    }

    static string AppData { get { return Path.Combine(Target, "app\\data"); } }

    public static string LogPath { get { return Path.Combine(Path.GetTempPath(), "halley_kurulum.log"); } }

    static void Log(string text)
    {
        try { File.WriteAllText(LogPath, DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " " + text); } catch { }
    }

    public static bool IsInstalled() { return File.Exists(Path.Combine(Target, "Halley.exe")); }

    public static string InstalledVersion()
    {
        string f = Path.Combine(Target, "surum.txt");
        try { return File.Exists(f) ? File.ReadAllText(f).Trim() : (IsInstalled() ? "eski sürüm (sürüm bilgisi yok)" : ""); }
        catch { return "?"; }
    }

    static string _new;
    public static string NewVersion()
    {
        if (_new != null) return _new;
        try
        {
            using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
            using (ZipArchive zip = new ZipArchive(s, ZipArchiveMode.Read))
            {
                ZipArchiveEntry e = zip.GetEntry("surum.txt");
                if (e != null) using (StreamReader r = new StreamReader(e.Open())) _new = r.ReadToEnd().Trim();
            }
        }
        catch { }
        return _new ?? "?";
    }

    // Kullanıcı verisi: veritabanları, ayarlar, takvim, takip/fırsat kayıtları (app\data kökündeki dosyalar) + anahtarlar
    static List<string> DataFiles()
    {
        List<string> l = new List<string>();
        if (Directory.Exists(AppData))
            foreach (string f in Directory.GetFiles(AppData))
            {
                string ext = Path.GetExtension(f).ToLowerInvariant();
                if (ext == ".db" || ext == ".json" || ext == ".csv" || ext == ".txt") l.Add(f);
            }
        string env = Path.Combine(Target, "app\\.env");
        if (File.Exists(env)) l.Add(env);
        return l;
    }

    static string Backup(Action<int, string> progress)
    {
        List<string> files = DataFiles();
        if (files.Count == 0) return null;
        progress(2, "Verileriniz yedekleniyor (" + files.Count + " dosya)…");
        string root = Path.Combine(AppData, "yedek");
        string dir = Path.Combine(root, "guncelleme_oncesi_" + DateTime.Now.ToString("yyyyMMdd_HHmmss"));
        Directory.CreateDirectory(dir);
        foreach (string f in files)
            File.Copy(f, Path.Combine(dir, Path.GetFileName(f)), true);
        string rap = Path.Combine(AppData, "raporlar");          // rapor arşivi küçük; o da yedeklenir
        if (Directory.Exists(rap))
            foreach (string f in Directory.GetFiles(rap, "*", SearchOption.AllDirectories))
            {
                string dst = Path.Combine(dir, "raporlar", f.Substring(rap.Length + 1));
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                File.Copy(f, dst, true);
            }
        // eski güncelleme yedeklerinden yalnız son birkaçı tutulur (disk dolmasın)
        string[] old = Directory.GetDirectories(root, "guncelleme_oncesi_*");
        Array.Sort(old);
        for (int i = 0; i < old.Length - KeepBackups; i++) { try { Directory.Delete(old[i], true); } catch { } }
        return dir;
    }

    static void StopHalley(Action<int, string> progress)
    {
        string exe = Path.Combine(Target, "Halley.exe");
        if (File.Exists(exe))
        {
            progress(1, "Açık Halley kapatılıyor…");
            try { Process p = Process.Start(new ProcessStartInfo(exe, "--kapat") { UseShellExecute = false, CreateNoWindow = true }); p.WaitForExit(30000); }
            catch { }
        }
        // bu klasörden çalışan arta kalan işlemler (Python, Halley) de kapatılır; başka programlara dokunulmaz
        string full = Path.GetFullPath(Target);
        foreach (Process p in Process.GetProcesses())
        {
            try
            {
                if (p.Id == Process.GetCurrentProcess().Id) continue;
                string n = p.ProcessName.ToLowerInvariant();
                if (n != "python" && n != "pythonw" && n != "halley") continue;
                string path = p.MainModule.FileName;
                if (path.StartsWith(full, StringComparison.OrdinalIgnoreCase)) { p.Kill(); p.WaitForExit(10000); }
            }
            catch { }
        }
    }

    public static string Install(Action<int, string> progress)
    {
        if (progress == null) progress = delegate { };
        bool update = IsInstalled();
        Directory.CreateDirectory(Target);
        string drive = Path.GetPathRoot(Path.GetFullPath(Target));
        try
        {
            long free = new DriveInfo(drive).AvailableFreeSpace;
            if (free < 900L * 1024 * 1024) throw new IOException("Diskte yeterli yer yok (en az 900 MB gerekir).");
        }
        catch (ArgumentException) { }

        StopHalley(progress);
        Dictionary<string, long> before = new Dictionary<string, long>(StringComparer.OrdinalIgnoreCase);
        foreach (string f in DataFiles()) before[f] = new FileInfo(f).Length;
        string backup = Backup(progress);

        // eski program dosyaları (veri hariç)
        progress(4, "Eski program dosyaları kaldırılıyor…");
        foreach (string d in new string[] { "python", "app\\bist_haber", "app\\.streamlit" })
        {
            string full = Path.Combine(Target, d);
            for (int i = 0; i < 5 && Directory.Exists(full); i++)
            {
                try { Directory.Delete(full, true); } catch { Thread.Sleep(1500); }
            }
            if (Directory.Exists(full)) throw new IOException("Eski dosyalar silinemedi (Halley hâlâ açık olabilir): " + full);
        }

        int kept = 0;
        using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using (ZipArchive zip = new ZipArchive(s, ZipArchiveMode.Read))
        {
            int n = zip.Entries.Count, i = 0;
            foreach (ZipArchiveEntry e in zip.Entries)
            {
                i++;
                string rel = e.FullName.Replace('/', '\\');
                string dst = Path.GetFullPath(Path.Combine(Target, rel));
                if (!dst.StartsWith(Path.GetFullPath(Target), StringComparison.OrdinalIgnoreCase)) continue;  // güvenlik
                if (rel.EndsWith("\\")) { Directory.CreateDirectory(dst); continue; }
                bool isData = rel.StartsWith("app\\data\\", StringComparison.OrdinalIgnoreCase);
                if (isData && File.Exists(dst)) { kept++; continue; }     // kullanıcının verisi korunur
                if (rel.Equals("app\\.env", StringComparison.OrdinalIgnoreCase) && File.Exists(dst)) continue;
                Directory.CreateDirectory(Path.GetDirectoryName(dst));
                e.ExtractToFile(dst, true);
                if (i % 200 == 0) progress(5 + (int)(88.0 * i / n), "Dosyalar kopyalanıyor… " + i + "/" + n);
            }
        }

        // veri denetimi: güncellemeden önce var olan her veri dosyası hâlâ yerinde ve boyutu korunmuş olmalı
        progress(94, "Verileriniz denetleniyor…");
        int restored = 0;
        foreach (KeyValuePair<string, long> kv in before)
        {
            bool ok = File.Exists(kv.Key) && new FileInfo(kv.Key).Length == kv.Value;
            if (!ok && backup != null)
            {
                string src = Path.Combine(backup, Path.GetFileName(kv.Key));
                if (File.Exists(src)) { File.Copy(src, kv.Key, true); restored++; }
            }
        }

        string exe = Path.Combine(Target, "Halley.exe");
        if (!NoShortcuts)
        {
            progress(98, "Kısayollar güncelleniyor…");                 // aynı adla üstüne yazılır; çift kısayol olmaz
            string desk = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string menu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Halley");
            Directory.CreateDirectory(menu);
            Shortcut(Path.Combine(desk, "Halley.lnk"), exe, "", "Halley — BIST haber paneli");
            Shortcut(Path.Combine(menu, "Halley.lnk"), exe, "", "Halley — BIST haber paneli");
            Shortcut(Path.Combine(menu, "Halley'i kaldır.lnk"), exe, "--kaldir", "Halley'i bu bilgisayardan kaldır");
        }
        File.WriteAllText(Path.Combine(Target, "kurulum.txt"), (update ? "Güncellendi: " : "Kuruldu: ") +
                          DateTime.Now.ToString("yyyy-MM-dd HH:mm") + " · sürüm " + NewVersion() +
                          (backup != null ? "\r\nYedek: " + backup : "") + "\r\n");
        string summary = (update ? "Halley güncellendi" : "Halley kuruldu") + " (sürüm " + NewVersion() + ")." +
                         (before.Count > 0 ? "\nVerileriniz korundu (" + before.Count + " veri dosyası" +
                                             (restored > 0 ? ", " + restored + " tanesi yedekten geri kondu" : "") + ")." : "") +
                         (backup != null ? "\nGüncelleme öncesi yedek: " + backup : "");
        progress(100, summary);
        return summary;
    }

    static void Shortcut(string path, string target, string args, string desc)
    {
        Type t = Type.GetTypeFromProgID("WScript.Shell");
        object sh = Activator.CreateInstance(t);
        object lnk = t.InvokeMember("CreateShortcut", BindingFlags.InvokeMethod, null, sh, new object[] { path });
        Type lt = lnk.GetType();
        lt.InvokeMember("TargetPath", BindingFlags.SetProperty, null, lnk, new object[] { target });
        lt.InvokeMember("Arguments", BindingFlags.SetProperty, null, lnk, new object[] { args });
        lt.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, lnk, new object[] { Path.GetDirectoryName(target) });
        lt.InvokeMember("IconLocation", BindingFlags.SetProperty, null, lnk, new object[] { target + ",0" });
        lt.InvokeMember("Description", BindingFlags.SetProperty, null, lnk, new object[] { desc });
        lt.InvokeMember("Save", BindingFlags.InvokeMethod, null, lnk, null);
    }

    class SetupForm : Form
    {
        Label info = new Label();
        ProgressBar bar = new ProgressBar();
        Button go = new Button(), alt = new Button(), cancel = new Button();
        bool installed = false;

        public SetupForm()
        {
            Text = "Halley Kurulum";
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(560, 250);
            Font = new Font("Segoe UI", 10f);
            info.SetBounds(20, 16, 520, 150);
            bar.SetBounds(20, 170, 520, 22);
            go.SetBounds(240, 204, 100, 32);
            alt.SetBounds(345, 204, 100, 32);
            cancel.Text = "İptal"; cancel.SetBounds(450, 204, 90, 32);
            alt.Visible = false;
            bool isUpd = IsInstalled();
            string cur = InstalledVersion(), nw = NewVersion();
            if (isUpd && cur == nw && !Force)
            {
                info.Text = "Halley bu bilgisayarda zaten kurulu ve güncel.\n\nKurulu sürüm: " + cur +
                            "\n\nYeniden kurmanız gerekmez. İsterseniz \"Yeniden kur\" ile program dosyalarını yenileyebilirsiniz; " +
                            "verileriniz yine korunur.";
                go.Text = "Halley'i aç"; installed = true;
                alt.Text = "Yeniden kur"; alt.Visible = true;
                alt.Click += delegate { alt.Visible = false; Begin(); };
            }
            else if (isUpd)
            {
                info.Text = "Halley bu bilgisayarda zaten kurulu — GÜNCELLENECEK (yeniden kurulmaz).\n\n" +
                            "Kurulu sürüm: " + cur + "\nYeni sürüm: " + nw +
                            "\n\nHalley kapatılır, program dosyaları yenilenir. Verileriniz (haberler, analizler, işlem günlüğü, " +
                            "takip listesi, ayarlar) ve API / Telegram anahtarlarınız korunur; güncellemeden önce ayrıca yedeklenir.";
                go.Text = "Güncelle";
            }
            else
            {
                info.Text = "Halley bu bilgisayara kurulacak.\n\nKlasör: " + Target + "\nSürüm: " + nw +
                            "\n\nYönetici izni gerekmez. Başka bilgisayardaki verilerinizi Halley içinden içe aktarabilirsiniz " +
                            "(⚙️ Ayarlar → 💾 Veri ve gelişmiş).";
                go.Text = "Kur";
            }
            cancel.Click += delegate { Close(); };
            go.Click += delegate
            {
                if (!installed) { Begin(); return; }
                try { Process.Start(Path.Combine(Target, "Halley.exe")); } catch { }
                Close();
            };
            Controls.AddRange(new Control[] { info, bar, go, alt, cancel });
            AcceptButton = go;
        }

        void Begin()
        {
            go.Enabled = false; cancel.Enabled = false; installed = false;
            new Thread(delegate ()
            {
                try
                {
                    string r = Install(delegate (int p, string m) { BeginInvoke((MethodInvoker)delegate { bar.Value = Math.Min(100, p); info.Text = m; }); });
                    Log("KURULUM TAMAM: " + Target + "\r\n" + r);
                    BeginInvoke((MethodInvoker)delegate
                    {
                        info.Text = r + "\n\nMasaüstündeki Halley simgesiyle açabilirsiniz.";
                        installed = true;
                        go.Text = "Halley'i aç"; go.Enabled = !NoLaunch; cancel.Text = "Kapat"; cancel.Enabled = true;
                    });
                }
                catch (Exception e)
                {
                    Log("KURULUM HATASI (" + Environment.OSVersion + "): " + e);   // tanı için (pencere kipinde de)
                    BeginInvoke((MethodInvoker)delegate
                    {
                        MessageBox.Show(this, "Kurulum tamamlanamadı:\n" + e.Message + "\n\nVerileriniz silinmedi.\n" +
                                        "Ayrıntı: " + LogPath,
                                        "Halley Kurulum", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        cancel.Text = "Kapat"; cancel.Enabled = true;
                    });
                }
            }) { IsBackground = true }.Start();
        }
    }
}
