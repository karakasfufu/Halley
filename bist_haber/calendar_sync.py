"""Takvimi resmi kaynaklardan yeniden kontrol etme (2026-11-07, kullanıcı isteği: "takvimi yenileyen düğme / her
açılışta otomatik kontrol").

Kullanıcının bilgisayarından erişilebilen RESMİ sayfalar okunur:
- TCMB "PPK toplantıları ve rapor takvimi" tablosu → PPK kararı, PPK özeti, Enflasyon Raporu, Finansal İstikrar Raporu
- federalreserve.gov FOMC takvimi → Fed karar günleri ve projeksiyonlu toplantılar
- TÜİK ana sitesinin takvim verisi (www.tuik.gov.tr/Home/GetTakvim, gün gün JSON) → TÜFE açıklama günü ve saati.
  Sitenin kendi takvim kutusu bu adresi kullanıyor (js/main.min.js, 2026-11-07). Her ayın ilk 10 günündeki iş günleri
  taranır (2026'da TÜFE her ay 3–5'inde); bulunamazsa "takvimde yok" denir, tarih tahmin edilmez.
Otomatik okunamayan (elle kontrol gerekir): Borsa İstanbul tatilleri (site bağlantıyı reddediyor).

Güvenlik: sayfa yapısı beklenenden farklıysa ya da herhangi bir tarih okunamazsa O KAYNAK İÇİN HİÇBİR ŞEY
DEĞİŞTİRİLMEZ ("kontrol edilemedi"). Tarih tahmin edilmez. Sonuç data/takvim_guncel.json'a yazılır; yerleşik
takvimle farklar ayrıca raporlanır. Yapay zekâ kullanılmaz, ücretsizdir.
"""
import json
import os
import re
from datetime import date, datetime, timedelta
from html import unescape
from typing import Callable, Dict, List, Optional, Tuple

from . import config

TCMB_URL = "https://www.tcmb.gov.tr/wps/wcm/connect/TR/TCMB+TR/Main+Menu/Duyurular/Takvim"
FED_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
                         "Chrome/120 Safari/537.36"}
TIMEOUT = 15
CHECK_EVERY_HOURS = 24
TR_MONTHS = {"ocak": 1, "şubat": 2, "mart": 3, "nisan": 4, "mayıs": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
             "eylül": 9, "ekim": 10, "kasım": 11, "aralık": 12}
EN_MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                          "september", "october", "november", "december"], start=1)}
TCMB_COLUMNS = ["Para Politikası Kurulu Toplantı Kararı", "Para Politikası Kurulu Toplantı Özeti", "Enflasyon Raporu",
                "Finansal İstikrar Raporu"]
TCMB_KINDS = ["ppk", "ozet", "er", "fir"]
TUIK_URL = "https://www.tuik.gov.tr/Home/GetTakvim/"
TUIK_MONTHS_AHEAD = 3
TUIK_SCAN_DAYS = 10


class ParseError(ValueError):
    pass


def _cell_text(html: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", html))).strip()


def _tr_date(text: str) -> date:
    m = re.fullmatch(r"(\d{1,2}) (\w+) (\d{4})", text)
    if not m or m.group(2).lower().replace("i̇", "i") not in TR_MONTHS:
        raise ParseError(f"tarih okunamadı: {text!r}")
    return date(int(m.group(3)), TR_MONTHS[m.group(2).lower()], int(m.group(1)))


def parse_tcmb(html: str) -> Dict[str, List[str]]:
    """TCMB takvim tablosu → {"ppk": [...], "ozet": [...], "er": [...], "fir": [...]} (ISO tarih)."""
    m = re.search(r'<table[^>]*id="midTable"[^>]*>(.*?)</table>', html, re.S)
    if not m:
        raise ParseError("TCMB takvim tablosu bulunamadı (sayfa yapısı değişmiş olabilir)")
    table = m.group(1)
    head = re.search(r"<thead>(.*?)</thead>", table, re.S)
    titles = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", head.group(1), re.S)] if head else []
    if titles != TCMB_COLUMNS:
        raise ParseError(f"TCMB tablo başlıkları beklenenden farklı: {titles}")
    out = {k: [] for k in TCMB_KINDS}
    for row in re.findall(r"<tr[^>]*>(.*?)</tr>", re.search(r"<tbody>(.*?)</tbody>", table, re.S).group(1), re.S):
        cells = [_cell_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if not cells:
            continue
        if len(cells) != 4:
            raise ParseError(f"TCMB satırında 4 hücre yok: {cells}")
        for kind, text in zip(TCMB_KINDS, cells):
            if text:
                out[kind].append(_tr_date(text).isoformat())
    _validate_tcmb(out)
    return out


def _validate_tcmb(d: Dict[str, List[str]]) -> None:
    if len(d["ppk"]) < 4 or len(d["ppk"]) != len(d["ozet"]):
        raise ParseError("TCMB tablosunda PPK/özet sayısı tutarsız")
    for kind, values in d.items():
        if values != sorted(values):
            raise ParseError(f"TCMB {kind} tarihleri sıralı değil")
        for v in values:
            if date.fromisoformat(v).weekday() >= 5:
                raise ParseError(f"TCMB {kind} tarihi hafta sonuna düşüyor: {v}")
    for k, o in zip(d["ppk"], d["ozet"]):
        if not 1 <= (date.fromisoformat(o) - date.fromisoformat(k)).days <= 14:
            raise ParseError(f"PPK özeti karardan beklenmedik uzaklıkta: {k} → {o}")


def parse_fed(html: str) -> List[Tuple[str, bool]]:
    """Fed FOMC takvimi → [(karar günü ISO, projeksiyonlu mu)]. Karar günü toplantının son günüdür."""
    parts = re.split(r"<h4><a[^>]*>(\d{4}) FOMC Meetings</a></h4>", html)
    if len(parts) < 3:
        raise ParseError("Fed takvim bölümleri bulunamadı (sayfa yapısı değişmiş olabilir)")
    out = []
    for year, body in zip(parts[1::2], parts[2::2]):
        y = int(year)
        months = re.findall(r'fomc-meeting__month[^"]*"[^>]*><strong>([^<]+)</strong>', body)
        days = re.findall(r'fomc-meeting__date[^"]*"[^>]*>([^<]+)</div>', body)
        if len(months) != len(days):
            raise ParseError(f"Fed {y}: ay ve gün sayısı tutmuyor")
        for mon, day in zip(months, days):
            text = day.strip()
            if re.search(r"unscheduled|notation|cancel", text, re.I):
                continue  # planlanmamış/iptal toplantılar takvime alınmaz
            sep = "*" in text
            m = re.fullmatch(r"(\d{1,2})(?:-(\d{1,2}))?\*?(?:\s*\(.*\))?", text)
            if not m:
                raise ParseError(f"Fed {y} {mon}: gün okunamadı {text!r}")
            # İki aya yayılan toplantılar kısaltmayla yazılıyor (ör. "Jan/Feb" 31-1): karar günü ikinci ayda.
            last_month = mon.split("/")[-1].strip().lower()
            month = next((i for name, i in EN_MONTHS.items() if len(last_month) >= 3 and name.startswith(last_month)), None)
            if month is None:
                raise ParseError(f"Fed {y}: ay okunamadı {mon!r}")
            d = date(y, month, int(m.group(2) or m.group(1)))
            if d.weekday() >= 5:
                raise ParseError(f"Fed karar günü hafta sonu: {d}")
            out.append((d.isoformat(), sep))
    if len(out) < 8:
        raise ParseError("Fed takviminde beklenenden az toplantı")
    return sorted(out)


def parse_tuik_day(items) -> List[Tuple[str, str, str]]:
    """TÜİK günlük takvim JSON'u → [(tarih, dönem, saat)] yalnız onaylı "Tüketici Fiyat Endeksi"."""
    if not isinstance(items, list):
        raise ParseError("TÜİK takvim cevabı liste değil")
    out = []
    for x in items:
        if not isinstance(x, dict) or "adi" not in x or "g_TARIH" not in x:
            raise ParseError("TÜİK takvim kaydının yapısı beklenenden farklı")
        if x["adi"].strip() == "Tüketici Fiyat Endeksi" and x.get("g_ONAY") == 1:
            t = datetime.fromisoformat(x["g_TARIH"])
            if t.weekday() >= 5:
                raise ParseError(f"TÜFE tarihi hafta sonu: {t}")
            if not re.fullmatch(r"\w+ \d{4}", (x.get("donemi") or "").strip()):
                raise ParseError(f"TÜFE dönemi okunamadı: {x.get('donemi')!r}")
            out.append((t.date().isoformat(), x["donemi"].strip(), t.strftime("%H:%M")))
    return out


def fetch_tuik(get: Callable, today: date) -> Dict:
    """Önümüzdeki aylar için TÜFE açıklama günü. {"data": [(tarih, dönem, saat)], "aylar": [taranan ay sonu...]}."""
    found, scanned = [], []
    y, m = today.year, today.month
    for _ in range(TUIK_MONTHS_AHEAD + 1):
        hit = None
        for day in range(1, TUIK_SCAN_DAYS + 1):
            d = date(y, m, day)
            if d.weekday() >= 5:
                continue
            r = get(TUIK_URL, params={"value": d.strftime("%d/%m/%Y"), "dilId": 1},
                    headers=dict(HEADERS, **{"X-Requested-With": "XMLHttpRequest"}), timeout=TIMEOUT)
            r.raise_for_status()
            rows = parse_tuik_day(r.json())
            if rows:
                hit = rows
                break
        last = (date(y + (m == 12), 1 if m == 12 else m + 1, 1) - timedelta(days=1)).isoformat()
        if hit:
            found += hit
            scanned.append(last)
        else:
            break  # bu ayın takvimi yok (ör. yeni yıl takvimi yayımlanmadı): sonrası da bilinmez
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return {"data": found, "kapsam_sonu": scanned[-1] if scanned else None}


def _fetch(url: str, get: Callable) -> str:
    r = get(url, headers=HEADERS, timeout=TIMEOUT)
    r.raise_for_status()
    return r.text


def state_file():
    return config.DATA / "takvim_guncel.json"


def load() -> Dict:
    try:
        return json.loads(state_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def check(get: Optional[Callable] = None, now: Optional[datetime] = None) -> Dict:
    """Resmi kaynakları okur, geçerli olanları kaydeder, yerleşik takvimle farkları döndürür."""
    if get is None:
        import requests
        get = requests.get
    from . import macro_calendar
    now = now or datetime.now(config.TR_TZ)
    prev = load()
    state = {"checked_at": now.isoformat(), "sources": dict(prev.get("sources", {}))}
    report = {}
    for name, url, parser in (("tcmb", TCMB_URL, parse_tcmb), ("fed", FED_URL, parse_fed)):
        try:
            data = parser(_fetch(url, get))
            if name == "fed":  # sayfada geçmiş yıllar da var; yalnız bu yıl ve sonrası
                data = [x for x in data if x[0][:4] >= str(now.year)]
                if not data:
                    raise ParseError("Fed takviminde bu yıl ve sonrası için toplantı yok")
        except Exception as e:  # ağ hatası ya da yapı değişikliği: o kaynak için değişiklik yok
            report[name] = {"durum": "kontrol edilemedi", "neden": str(e)[:200]}
            continue
        state["sources"][name] = {"data": data, "fetched_at": now.isoformat(), "url": url}
        report[name] = {"durum": "güncel", "farklar": macro_calendar.diff_with_builtin(name, data)}
    try:
        tuik = fetch_tuik(get, now.date())
        if not tuik["data"]:
            raise ParseError("TÜİK takviminde bu ay ve sonrası için TÜFE kaydı bulunamadı")
        state["sources"]["tuik"] = {"data": tuik["data"], "kapsam_sonu": tuik["kapsam_sonu"],
                                    "fetched_at": now.isoformat(), "url": TUIK_URL}
        report["tuik"] = {"durum": "güncel", "farklar": macro_calendar.diff_with_builtin("tuik", tuik["data"])}
    except Exception as e:
        report["tuik"] = {"durum": "kontrol edilemedi", "neden": str(e)[:200]}
    report["elle"] = ["Borsa İstanbul tatil/yarım gün takvimi (site otomatik erişimi reddediyor)"]
    state["report"] = report
    path = state_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    return report


def auto_check() -> Optional[Dict]:
    """Panel açılışında: son kontrolden 24 saat geçtiyse resmi sayfaları kontrol eder. Hata paneli durdurmaz.
    HALLEY_OFFLINE ortam değişkeni varsa (testler) ağa çıkmaz."""
    if os.environ.get("HALLEY_OFFLINE") or not due():
        return None
    try:
        return check()
    except Exception as e:  # yazma hatası vb.: panel yine açılsın
        return {"hata": str(e)[:200]}


def summary_line() -> str:
    """Kısa durum: "Son kontrol 07.11 12:00 · TCMB: güncel · Fed: güncel"."""
    st = load()
    if not st.get("checked_at"):
        return "Takvim henüz resmi kaynaklardan kontrol edilmedi (yerleşik takvim kullanılıyor)."
    t = datetime.fromisoformat(st["checked_at"])
    rep = st.get("report", {})
    parts = [f"{label}: {rep.get(k, {}).get('durum', '—')}" for k, label in (("tcmb", "TCMB"), ("fed", "Fed"),
                                                                                  ("tuik", "TÜİK"))]
    return f"Takvim son kontrol {t:%d.%m %H:%M} · " + " · ".join(parts)


def due(now: Optional[datetime] = None) -> bool:
    """Son kontrolden bu yana 24 saat geçtiyse True (açılışta otomatik kontrol için)."""
    last = load().get("checked_at")
    if not last:
        return True
    now = now or datetime.now(config.TR_TZ)
    try:
        return now - datetime.fromisoformat(last) >= timedelta(hours=CHECK_EVERY_HOURS)
    except ValueError:
        return True
