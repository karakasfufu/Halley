"""KAP "Finansal Rapor" bildirimlerinden kompakt finansal özet çıkarır.

Bildirim sayfasının ana metni rakam içermiyor; tablolar KAP'ın Excel dışa aktarımında
(/tr/api/notification/export/excel/<index>, aslında HTML tablo) duruyor. Buradan gelir
tablosu ve bilançonun ana kalemleri alınır. Yüzde değişimler KOD tarafından hesaplanır
(dil modelinin aritmetik hatası riskini ortadan kaldırmak için).
"""
import html
import re
from typing import List, Optional

from . import config

# Bilançoda gösterilecek ana kalemler (büyük harfli toplamlar ayrıca otomatik alınır).
BALANCE_KEYS = ("Nakit ve Nakit Benzerleri", "Kısa Vadeli Borçlanmalar", "Uzun Vadeli Borçlanmalar",
                "Ana Ortaklığa Ait Özkaynaklar")


def _rows(page: str) -> List[List[str]]:
    rows = []
    for tr in re.findall(r"<tr\b.*?</tr>", page, flags=re.S | re.I):
        cells = [re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", td))).strip()
                 for td in re.findall(r"<t[dh]\b.*?</t[dh]>", tr, flags=re.S | re.I)]
        cells = [c for c in cells if c]
        if cells:
            rows.append(cells)
    return rows


def _tables(page: str):
    """Rol (tablo) bazında [(etiket, [değerler])]. Değerler hücredeki ham sayıdan (title) okunur."""
    tables = {}
    for ch in re.split(r'(?=<tr class="general_role_)', page)[1:]:
        m = re.match(r'<tr class="(general_role_\d+)-row-\d+([^"]*)"', ch)
        if not m or "taxonomy-hidden-row" in m.group(2):
            continue
        lm = re.search(r'content-tr"[^>]*>(.*?)</div>', ch, flags=re.S)
        label = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", lm.group(1)))).strip() if lm else ""
        t = tables.setdefault(m.group(1), {"title": "", "rows": []})
        if not t["title"] and "Tablosu" in label:
            t["title"] = label
        vals = re.findall(r'class="taxonomy-context-value[^"]*">\s*<div>\s*<div[^>]*?title="(-?\d+(?:\.\d+)?)"', ch)
        if label and vals:
            t["rows"].append((label, [float(v) for v in vals]))
    return list(tables.values())


def _change(cur: float, prev: float) -> str:
    if prev == 0:
        return "önceki dönem 0"
    if prev < 0 <= cur:
        return "zarardan kâra geçiş"
    if prev > 0 > cur:
        return "kârdan zarara geçiş"
    if prev < 0 and cur < 0:
        return f"zarar {'azaldı' if abs(cur) < abs(prev) else 'arttı'} ({(abs(cur) / abs(prev) - 1) * 100:+.1f}%)"
    return f"{(cur / prev - 1) * 100:+.1f}%"


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", ".") if abs(v) >= 100 else f"{v:g}"


def summarize(page: str) -> str:
    simple = _rows(page)
    unit = next((r[1] for r in simple if r[0].startswith("Sunum Para Birimi") and len(r) > 1), "?")
    # Her tablo başlığından hemen önceki "Cari Dönem ..." satırı o tablonun sütunlarıdır.
    periods, last = {}, []
    for r in simple:
        if r[0].startswith("Cari Dönem"):
            last = r
        elif "Tablosu" in r[0] and r[0] not in periods:
            periods[r[0]] = last
    income, balance, changes = [], [], []
    for t in _tables(page):
        title = t["title"]
        if "Kar veya Zarar" in title and not income:
            income += [f"GELİR TABLOSU (birim: {unit})", "Sütunlar: " + " | ".join(periods.get(title, []))]
            for label, vals in t["rows"]:
                if "Yeniden Sınıflandırıl" in label or label.upper().startswith("DİĞER KAPSAMLI GELİR"):
                    break  # diğer kapsamlı gelir kısmı karar için gürültü
                income.append(f"{label}: " + " | ".join(_fmt(v) for v in vals))
                key = label.isupper() or label in ("Hasılat", "Ana Ortaklık Payları")
                if key and len(vals) >= 2 and not any(c.startswith(label + ":") for c in changes):
                    txt = f"{label}: dönem {_change(vals[0], vals[1])}"
                    if len(vals) >= 4:
                        txt += f"; son çeyrek (3 aylık) {_change(vals[2], vals[3])}"
                    changes.append(txt)
        elif "Finansal Durum" in title and not balance:
            balance += [f"BİLANÇO ANA KALEMLER (birim: {unit})", "Sütunlar: " + " | ".join(periods.get(title, []))]
            for label, vals in t["rows"]:
                if (label.isupper() and label != "ARA TOPLAM") or label in BALANCE_KEYS:
                    balance.append(f"{label}: " + " | ".join(_fmt(v) for v in vals))
    if not income and not balance:
        return ""
    parts = ["[FİNANSAL TABLO ÖZETİ — KAP Excel dışa aktarımından]"]
    if changes:
        parts.append("YILLIK DEĞİŞİMLER (kod tarafından hesaplandı, doğru kabul et):\n" + "\n".join(changes))
    parts += ["\n".join(income), "\n".join(balance)]
    return "\n\n".join(p for p in parts if p)[:config.FINANCIAL_SUMMARY_CHARS]


def fetch_summary(index: int) -> str:
    from .kap import _get  # döngüsel içe aktarmayı önlemek için burada
    r = _get(f"{config.KAP_BASE}/tr/api/notification/export/excel/{index}")
    return summarize(r.content.decode("utf-8", "ignore"))
