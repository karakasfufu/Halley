// Halley kurulum programı (2026-11-09). İçine gömülü payload.zip'i kullanıcı klasörüne açar (yönetici izni gerekmez).
// Yeniden kurulum / güncelleme: app\data\ altındaki MEVCUT dosyalara ve app\.env'e (API anahtarı) dokunmaz;
// yalnız eksik veri dosyalarını ekler. Program dosyaları (python\, app\bist_haber\ ...) yenilenir.
// Komutlar: Halley_Kurulum.exe [/sessiz] [/hedef=KLASÖR] [/kisayolsuz] [/baslatma]
using System;
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
    static bool Silent = false, NoShortcuts = false, NoLaunch = false;

    [STAThread]
    static int Main(string[] args)
    {
        foreach (string a in args)
        {
            string l = a.ToLowerInvariant();
            if (l == "/sessiz") Silent = true;
            else if (l == "/kisayolsuz") NoShortcuts = true;
            else if (l == "/baslatma") NoLaunch = true;
            else if (l.StartsWith("/hedef=")) Target = a.Substring(7).Trim('"');
        }
        if (Silent)
        {
            string log = Path.Combine(Path.GetTempPath(), "halley_kurulum.log");
            try { Install(null); File.WriteAllText(log, "KURULUM TAMAM: " + Target); return 0; }
            catch (Exception e) { File.WriteAllText(log, "KURULUM HATASI: " + e); return 1; }
        }
        Application.EnableVisualStyles();
        Application.Run(new SetupForm());
        return 0;
    }

    public static void Install(Action<int, string> progress)
    {
        if (progress == null) progress = delegate { };
        Directory.CreateDirectory(Target);
        string drive = Path.GetPathRoot(Path.GetFullPath(Target));
        try
        {
            long free = new DriveInfo(drive).AvailableFreeSpace;
            if (free < 900L * 1024 * 1024) throw new IOException("Diskte yeterli yer yok (en az 900 MB gerekir).");
        }
        catch (ArgumentException) { }

        // açık Halley varsa kapat
        string exe = Path.Combine(Target, "Halley.exe");
        if (File.Exists(exe))
        {
            progress(1, "Açık Halley kapatılıyor…");
            try { Process p = Process.Start(new ProcessStartInfo(exe, "--kapat") { UseShellExecute = false, CreateNoWindow = true }); p.WaitForExit(30000); }
            catch { }
        }
        // eski program dosyaları (veri hariç)
        progress(3, "Eski program dosyaları kaldırılıyor…");
        foreach (string d in new string[] { "python", "app\\bist_haber", "app\\.streamlit" })
        {
            string full = Path.Combine(Target, d);
            for (int i = 0; i < 5 && Directory.Exists(full); i++)
            {
                try { Directory.Delete(full, true); } catch { Thread.Sleep(1500); }
            }
            if (Directory.Exists(full)) throw new IOException("Eski dosyalar silinemedi (Halley hâlâ açık olabilir): " + full);
        }

        using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("payload.zip"))
        using (ZipArchive zip = new ZipArchive(s, ZipArchiveMode.Read))
        {
            int n = zip.Entries.Count, i = 0, kept = 0;
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
                if (i % 200 == 0) progress(5 + (int)(90.0 * i / n), "Dosyalar kopyalanıyor… " + i + "/" + n);
            }
            progress(96, kept > 0 ? ("Mevcut verileriniz korundu (" + kept + " dosya).") : "Dosyalar kopyalandı.");
        }

        if (!NoShortcuts)
        {
            progress(98, "Kısayollar oluşturuluyor…");
            string desk = Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory);
            string menu = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "Halley");
            Directory.CreateDirectory(menu);
            Shortcut(Path.Combine(desk, "Halley.lnk"), exe, "", "Halley — BIST haber paneli");
            Shortcut(Path.Combine(menu, "Halley.lnk"), exe, "", "Halley — BIST haber paneli");
            Shortcut(Path.Combine(menu, "Halley'i kaldır.lnk"), exe, "--kaldir", "Halley'i bu bilgisayardan kaldır");
        }
        File.WriteAllText(Path.Combine(Target, "kurulum.txt"), "Kuruldu: " + DateTime.Now.ToString("yyyy-MM-dd HH:mm") + "\r\n");
        progress(100, "Kurulum tamamlandı.");
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
        Button go = new Button(), cancel = new Button();
        bool installed = false;

        public SetupForm()
        {
            Text = "Halley Kurulum";
            try { Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath); } catch { }
            FormBorderStyle = FormBorderStyle.FixedDialog; MaximizeBox = false; MinimizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            ClientSize = new Size(520, 210);
            Font = new Font("Segoe UI", 10f);
            info.SetBounds(20, 18, 480, 100);
            info.Text = "Halley bu bilgisayara kurulacak.\n\nKlasör: " + Target +
                        "\n\nYönetici izni gerekmez. Daha önce kurulduysa verileriniz ve API anahtarınız korunur.";
            bar.SetBounds(20, 125, 480, 22);
            go.Text = "Kur"; go.SetBounds(300, 160, 95, 32);
            cancel.Text = "İptal"; cancel.SetBounds(405, 160, 95, 32);
            cancel.Click += delegate { Close(); };
            go.Click += delegate
            {
                if (!installed) { Begin(); return; }
                try { Process.Start(Path.Combine(Target, "Halley.exe")); } catch { }
                Close();
            };
            Controls.AddRange(new Control[] { info, bar, go, cancel });
            AcceptButton = go;
        }

        void Begin()
        {
            go.Enabled = false; cancel.Enabled = false;
            new Thread(delegate ()
            {
                try
                {
                    Install(delegate (int p, string m) { BeginInvoke((MethodInvoker)delegate { bar.Value = Math.Min(100, p); info.Text = m; }); });
                    BeginInvoke((MethodInvoker)delegate
                    {
                        info.Text = "Halley kuruldu.\n\nMasaüstündeki Halley simgesiyle açabilirsiniz. Program açıkken saatin yanında " +
                                    "Halley simgesi görünür; kapatmak için ona sağ tıklayın.";
                        installed = true;
                        go.Text = "Halley'i aç"; go.Enabled = !NoLaunch; cancel.Text = "Kapat"; cancel.Enabled = true;
                    });
                }
                catch (Exception e)
                {
                    BeginInvoke((MethodInvoker)delegate
                    {
                        MessageBox.Show(this, "Kurulum tamamlanamadı:\n" + e.Message, "Halley Kurulum", MessageBoxButtons.OK, MessageBoxIcon.Error);
                        cancel.Text = "Kapat"; cancel.Enabled = true;
                    });
                }
            }) { IsBackground = true }.Start();
        }
    }
}
