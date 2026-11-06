"""Hisse evreni ve hisse eşleme (Dipnot 1 ve 3)."""
import csv
import io
import re
from typing import Dict, List, Set

import openpyxl
import requests

from . import config
from .textutil import tr_lower

COMPANY_LIST_URL = config.KAP_BASE + "/tr/api/company/generic/excel/IGS/A"


def refresh_companies(conn) -> int:
    """KAP'tan güncel şirket listesini indirip veritabanına yazar."""
    r = requests.get(COMPANY_LIST_URL, headers=config.HTTP_HEADERS, timeout=60)
    r.raise_for_status()
    wb = openpyxl.load_workbook(io.BytesIO(r.content), read_only=True)
    conn.execute("DELETE FROM companies")  # listeden çıkan şirketler de silinsin
    count = 0
    for row in wb.active.iter_rows(values_only=True):
        code, name, city = (list(row) + [None, None, None])[:3]
        if not code or not name or code == "Kod":
            continue
        # Bazı şirketlerin birden fazla kodu var ("TVB, VAKBN"). 3 harfli olanlar borçlanma
        # aracı ihraççı kodları; pay kodu (4+ harf) varsa onları at. Ayrı işlem gören pay
        # grupları (KRDMA/KRDMB/KRDMD) korunur.
        codes = [c for c in re.split(r"[,\s]+", str(code).strip()) if re.fullmatch(r"[A-Z0-9]{3,6}", c)]
        if any(len(c) >= 4 for c in codes):
            codes = [c for c in codes if len(c) >= 4]
        for t in codes:
            conn.execute(
                "INSERT INTO companies(ticker,name,city) VALUES(?,?,?) "
                "ON CONFLICT(ticker) DO UPDATE SET name=excluded.name, city=excluded.city",
                (t, str(name).strip(), city),
            )
            count += 1
    conn.commit()
    return count


def load_universe(conn) -> Dict[str, str]:
    """{ticker: şirket adı}. data/universe.txt doluysa sadece oradaki hisseler."""
    companies = {r["ticker"]: r["name"] for r in conn.execute("SELECT ticker,name FROM companies")}
    wanted: Set[str] = set()
    if config.UNIVERSE_FILE.exists():
        for line in config.UNIVERSE_FILE.read_text(encoding="utf-8").splitlines():
            line = line.split("#")[0].strip().upper()
            if line:
                wanted.add(line)
    if not wanted:
        return companies
    missing = wanted - companies.keys()
    if missing:
        print(f"[uyarı] universe.txt içinde KAP listesinde olmayan kodlar: {', '.join(sorted(missing))}")
    return {t: n for t, n in companies.items() if t in wanted}


class Matcher:
    """Serbest metindeki (RSS) hisse adlarını/kodlarını bulur."""

    def __init__(self, universe: Dict[str, str]):
        self.universe = universe
        self.patterns: List = []  # (regex, ticker)
        if config.ALIASES_FILE.exists():
            with open(config.ALIASES_FILE, encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    t = row["ticker"].strip().upper()
                    if t not in universe:
                        continue  # evrende yok veya kod değişmiş
                    for alias in row["aliases"].split("|"):
                        alias = tr_lower(alias.strip())
                        if alias:
                            pat = re.compile(r"(?<![0-9a-zçğıöşü])" + re.escape(alias) + r"(?![0-9a-zçğıöşü])")
                            self.patterns.append((pat, t))

    def find(self, text: str) -> List[str]:
        found = set()
        # 1) Metinde büyük harfle geçen hisse kodları (ör. "THYAO")
        for word in re.findall(r"\b[A-ZÇĞİÖŞÜ]{4,6}\b", text):
            if word in self.universe:
                found.add(word)
        # 2) Elle hazırlanmış takma adlar (ör. "Türk Hava Yolları", "THY")
        low = tr_lower(text)
        for pat, t in self.patterns:
            if pat.search(low):
                found.add(t)
        return sorted(found)
