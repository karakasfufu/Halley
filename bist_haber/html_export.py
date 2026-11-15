"""Hisse Analizi ekranını tek dosya .html olarak indirme (2026-11-15, kullanıcı isteği).

Yaklaşım: ekranı çizen fonksiyonlar (app.py) aynen çalıştırılır; yalnız `st` geçici olarak bu dosyadaki Kaydedici
ile değiştirilir. Böylece dosyadaki sayılar ve metinler ekrandakiyle AYNI hesaplardan gelir (ikinci bir kopya kod yok).
Yapay zekâ çağrısı yok. Grafik Vega-Lite olarak gömülür; görüntülemek için internet gerekir (yoksa grafik yerine not
görünür, geri kalan her şey çevrimdışı okunur).
"""
import html
import json
import itertools
import re
from contextlib import contextmanager
from typing import Callable, List

_IDS = itertools.count(1)
_TONE = {"info": ("#1d4ed8", "#e8f0ff"), "warning": ("#a16207", "#fff7e0"), "error": ("#b91c1c", "#fde8e8"),
         "success": ("#15803d", "#e7f7ec")}


def _inline(s: str) -> str:
    """Kod tarafından üretilen markdown'ın kullanılan alt kümesi: \\-kaçışları, **kalın**, *eğik*."""
    s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"(?<![\w*\\])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", s)
    return re.sub(r"\\([~*_`$\\])", r"\1", s)


def md_to_html(text: str, allow_html: bool = False) -> str:
    """Satır başı "- " madde, boş satır paragraf, satır sonu iki boşluk = alt satır. allow_html yoksa metin kaçırılır."""
    text = str(text if text is not None else "")
    if not allow_html:
        text = html.escape(text, quote=False)
    out, items, para = [], [], []

    def flush():
        if para:
            out.append("<p>" + "<br>".join(_inline(x) for x in para) + "</p>")
            para.clear()
        if items:
            out.append("<ul>" + "".join(f"<li>{_inline(x)}</li>" for x in items) + "</ul>")
            items.clear()

    for ln in text.split("\n"):
        st_ = ln.strip()
        if st_.startswith("- "):
            if para:
                flush()
            items.append(st_[2:])
        elif not st_:
            flush()
        else:
            if items:
                flush()
            para.append(st_)
    flush()
    return "".join(out)


class Recorder:
    """Streamlit'in ekran fonksiyonlarında kullanılan alt kümesini HTML'e yazar. Etkileşimli öğeler (radio, düğme)
    varsayılan değeri döndürür; dosyada çizilmez."""

    def __init__(self, parts: List[str] = None):
        self.parts = parts if parts is not None else []

    # yazı
    def markdown(self, body="", unsafe_allow_html=False, **_):
        self.parts.append(f"<div class='md'>{md_to_html(body, unsafe_allow_html)}</div>")

    write = markdown

    def caption(self, body="", unsafe_allow_html=False, **_):
        self.parts.append(f"<div class='cap'>{md_to_html(body, unsafe_allow_html)}</div>")

    def _box(self, kind, body):
        fg, bg = _TONE[kind]
        self.parts.append(f"<div class='box' style='border-color:{fg};background:{bg}'>{md_to_html(body)}</div>")

    def info(self, body="", **_):
        self._box("info", body)

    def warning(self, body="", **_):
        self._box("warning", body)

    def error(self, body="", **_):
        self._box("error", body)

    def success(self, body="", **_):
        self._box("success", body)

    def metric(self, label, value, delta=None, **_):
        d = f"<div class='md-delta'>{html.escape(str(delta))}</div>" if delta not in (None, "") else ""
        self.parts.append(f"<div class='metric'><div class='m-l'>{html.escape(str(label))}</div>"
                          f"<div class='m-v'>{html.escape(str(value))}</div>{d}</div>")

    def dataframe(self, data=None, **_):
        try:
            d = data.astype(object).where(data.notna(), "—")            # boş hücre "None" görünmesin
            self.parts.append("<div class='tbl'>" + d.to_html(index=False, escape=True, border=0) + "</div>")
        except AttributeError:
            self.markdown(str(data))

    table = dataframe

    def altair_chart(self, fig, **_):
        d = fig.to_dict()
        for sub in d.get("vconcat", []) or [d]:          # sayfa genişliğinde (ekranda kap genişliği kullanılıyor)
            sub.setdefault("width", 960)
        spec = json.dumps(d, ensure_ascii=False, default=str).replace("</", "<\\/")
        i = next(_IDS)
        self.parts.append(f"<div id='ch{i}' class='chart'><div class='cap'>📈 Grafik yükleniyor… (görüntülemek için "
                          f"internet bağlantısı gerekir)</div></div><script>window._ch=window._ch||[];"
                          f"window._ch.push(['#ch{i}',{spec}]);</script>")

    # düzen
    def columns(self, spec, **_):
        n = spec if isinstance(spec, int) else len(spec)
        self.parts.append("<div class='row'>")
        cols = [Recorder() for _ in range(n)]
        self.parts.append(_RowEnd(cols))
        return cols

    @contextmanager
    def container(self, **_):
        yield self

    @contextmanager
    def expander(self, label="", **_):
        self.parts.append(f"<details open><summary>{html.escape(str(label))}</summary>")
        try:
            yield self
        finally:
            self.parts.append("</details>")

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    # etkileşimli: dosyada yok, varsayılanı döndür
    def radio(self, label, options, index=0, **_):
        options = list(options)
        return options[index] if options else None

    def selectbox(self, label, options, index=0, **_):
        return self.radio(label, options, index)

    def button(self, *a, **k):
        return False

    def checkbox(self, label="", value=False, **_):
        return value

    toggle = checkbox

    def __getattr__(self, name):          # bilinmeyen çağrı dosyayı bozmasın: sessizce atla
        return lambda *a, **k: None

    def html(self) -> str:
        out = []
        for p in self.parts:
            out.append(p.render() if isinstance(p, _RowEnd) else p)
        return "".join(out)


class _RowEnd:
    def __init__(self, cols):
        self.cols = cols

    def render(self) -> str:
        return "".join(f"<div class='col'>{c.html()}</div>" for c in self.cols) + "</div>"


CSS = """
body{font-family:Segoe UI,Arial,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1f2937;
background:#fff;line-height:1.45;font-size:15px}
h1{font-size:24px;margin:0 0 4px}.sub{color:#6b7280;font-size:13px;margin-bottom:16px}
.cap{color:#6b7280;font-size:13px;margin:4px 0 10px}.md{margin:8px 0}.md p{margin:6px 0}
.box{border-left:4px solid;padding:8px 12px;border-radius:6px;margin:8px 0}
.row{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}.col{flex:1;min-width:140px}
.metric{border:1px solid #e5e7eb;border-radius:8px;padding:8px 10px}.m-l{font-size:12px;color:#6b7280}
.m-v{font-size:20px;font-weight:600}.md-delta{font-size:12px;color:#374151}
.tbl{overflow-x:auto;margin:8px 0}table{border-collapse:collapse;width:100%;font-size:13px}
th,td{border-bottom:1px solid #e5e7eb;padding:5px 8px;text-align:left;vertical-align:top}th{background:#f3f4f6}
.news-card{border:1px solid #e5e7eb;border-radius:8px;padding:10px;margin:8px 0}.news-meta{color:#6b7280;font-size:12px}
.chip{display:inline-block;border-radius:10px;padding:1px 8px;font-size:12px;margin-right:6px;background:#eef2ff}
.chip.pos{background:#dcfce7}.chip.neg{background:#fee2e2}.chip.warn{background:#fef3c7}
.sec{font-weight:600;font-size:17px;margin:14px 0 6px}.sec .cnt,.sec .note{margin-left:8px;font-size:12px;color:#6b7280}
.page-h{font-size:20px;font-weight:600;margin:8px 0}.chart{margin:8px 0}.foot{margin-top:24px;color:#6b7280;font-size:12px;
border-top:1px solid #e5e7eb;padding-top:8px}details{margin:8px 0}summary{cursor:pointer;font-weight:600}
"""

VEGA = """<script src="https://cdn.jsdelivr.net/npm/vega@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-lite@5"></script>
<script src="https://cdn.jsdelivr.net/npm/vega-embed@6"></script>
<script>window.addEventListener('load',function(){if(!window.vegaEmbed){(window._ch||[]).forEach(function(c){
document.querySelector(c[0]).innerHTML="<div class='cap'>📈 Grafik için internet bağlantısı gerekir; diğer bölümler çevrimdışı okunur.</div>";});return;}
(window._ch||[]).forEach(function(c){vegaEmbed(c[0],c[1],{actions:false}).catch(function(){});});});</script>"""


def page(title: str, sub: str, body: str, foot: str) -> str:
    return (f"<!DOCTYPE html><html lang='tr'><head><meta charset='utf-8'><meta name='viewport' "
            f"content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{CSS}</style>"
            f"</head><body><h1>{html.escape(title)}</h1><div class='sub'>{html.escape(sub)}</div>{body}"
            f"<div class='foot'>{html.escape(foot)}</div>{VEGA}</body></html>")


def capture(namespace: dict, draw: Callable[[], None], **overrides) -> str:
    """namespace içindeki `st`'yi (ve verilen diğer adları, ör. DARK=False: dosya açık zeminli) geçici olarak
    değiştirip draw()'u çalıştırır; HTML gövdesini döndürür. Hata olsa da eski değerler her zaman geri konur."""
    rec = Recorder()
    new = dict(overrides, st=rec)
    old = {k: namespace.get(k) for k in new}
    namespace.update(new)
    try:
        draw()
    finally:
        namespace.update(old)
    return rec.html()
