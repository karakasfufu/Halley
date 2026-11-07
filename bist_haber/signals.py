"""Panelin ve bekçinin ORTAK hisse kararı (W1, 2026-11-07).

Panelde "uygun" görünen senaryo ile bekçinin kaydettiği karar aynı koddan çıkar; iki yer zamanla ayrışmasın.
Her hisse için: önerildi mi, önerilmediyse NEDEN ve hangi modülde elendi (kaçırılan fırsat analizi bunu kullanır).
Yapay zekâ kullanılmaz; kayıtlı haber analizi, fiyat ve takvim verisiyle kodla hesaplanır.
"""
from datetime import date, datetime
from typing import Dict, List, Optional

from . import config, corp_events, earnings, technical, timeline, tradeplan

# Neden kodu → (modül, açıklama şablonu)
REASONS = {
    "ONERILDI": ("—", "Uygun giriş senaryosu var"),
    "HABER_YOK": ("haber", "İlgili haber/KAP bildirimi kayıtlarda yok"),
    "HABER_ANALIZ_BEKLIYOR": ("haber", "Haber var ama henüz analiz edilmedi (metin bekliyor ya da analiz sırasında)"),
    "HABER_ONEMSIZ": ("haber", "Haber var ama önemsiz/rutin bulundu (ön eleme, konu listesi ya da etkisi nötr)"),
    "HABER_OLUMSUZ": ("haber", "Haber etkisi olumsuz"),
    "SKOR_ESIK_ALTI": ("skor", "Haber etkisi olumlu ama skor eşiğin (1,5) altında"),
    "TEKNIK_VERI_YOK": ("teknik", "Fiyat geçmişi yetersiz (en az 30 işlem günü gerekir)"),
    "VERI_KRITIK": ("veri", "Fiyat verisinde kritik sorun (eski fiyat ya da düzeltilmemiş sıçrama)"),
    "LIKIDITE": ("likidite", "Likidite çok düşük (günlük ortalama işlem hacmi 2 milyon TL altı)"),
    "SENARYO_UYGUN_DEGIL": ("senaryo", "Giriş senaryolarının hiçbiri uygun değil (koşul yok ya da risk/getiri elverişsiz)"),
}


class Context:
    """Bir çalıştırma için önbellekli hesap ortamı (panel sayfası ya da bekçi turu)."""

    def __init__(self, conn, today: Optional[date] = None):
        self.conn = conn
        self.today = today or datetime.now(config.TR_TZ).date()
        self._tech, self._earn, self._corp, self._plan = {}, {}, {}, {}
        self._macro = "?"

    def tech(self, ticker: str):
        if ticker not in self._tech:
            self._tech[ticker] = technical.for_ticker(self.conn, ticker, self.today)
        return self._tech[ticker]

    def earning(self, ticker: str) -> dict:
        if ticker not in self._earn:
            self._earn[ticker] = earnings.status(self.conn, ticker, self.today)
        return self._earn[ticker]

    def corp(self, ticker: str) -> dict:
        if ticker not in self._corp:
            self._corp[ticker] = corp_events.upcoming(self.conn, ticker, self.today)
        return self._corp[ticker]

    def macro_risk(self):
        if self._macro == "?":
            self._macro = timeline.macro_risk(self.today, 15)
        return self._macro

    def news_info(self, r: dict) -> dict:
        imp = self.conn.execute("SELECT confidence, persistence, reason, published_at, effective_date FROM impacts "
                                "WHERE ticker=? AND direction!=0 ORDER BY published_at DESC LIMIT 1",
                                (r["ticker"],)).fetchone()
        t = self.tech(r["ticker"])
        move = technical.news_moves_for(self.conn, r["ticker"], imp["effective_date"], t.get("atr")) if imp and t else {}
        ev = self.corp(r["ticker"])
        return {"score": r["score"], "direction": 1 if r["score"] > 0 else (-1 if r["score"] < 0 else 0),
                "confidence": imp["confidence"] if imp else None, "flags": r.get("flags", ""),
                "persistence": imp["persistence"] if imp else "orta",
                "reason": imp["reason"] if imp else "", "summary": r.get("last_news", ""), "hareket": move,
                "bilanco_riski": earnings.window_risk(self.earning(r["ticker"]), self.today, 15),
                "olay_riskleri": corp_events.risk_lines(ev, (t or {}).get("son_fiyat")),
                "makro_riski": self.macro_risk(),
                "temettu": [(e["tarih"], e["brut_tl"] / t["son_fiyat"] * 100) for e in ev["yaklasan"]
                            if e["tur"] == "temettu_hak" and e.get("brut_tl") and t and t.get("son_fiyat")]}

    def plan(self, r: dict) -> dict:
        if r["ticker"] not in self._plan:
            self._plan[r["ticker"]] = tradeplan.plan(self.tech(r["ticker"]), self.news_info(r))
        return self._plan[r["ticker"]]


def _code_from_plan(p: dict) -> str:
    if p.get("durum") == "senaryo":
        g = p.get("girisler") or {}
        return "ONERILDI" if g.get("en_uygun") else "SENARYO_UYGUN_DEGIL"
    text = p.get("neden_yok", "")
    if text.startswith("Teknik veri yok"):
        return "TEKNIK_VERI_YOK"
    if text.startswith("Fiyat verisinde kritik"):
        return "VERI_KRITIK"
    if text.startswith("Likidite"):
        return "LIKIDITE"
    return "SKOR_ESIK_ALTI"


def decide(ctx: Context, r: dict) -> Dict:
    """Haber skoru olan bir hisse için karar kaydı."""
    t = ctx.tech(r["ticker"])
    base = {"ticker": r["ticker"], "haber_skoru": r["score"], "haber_sayisi": r.get("news_count"),
            "son_fiyat": (t or {}).get("son_fiyat"), "fiyat_gunu": (t or {}).get("tarih"), "detay": {}}
    if r["score"] <= -1.5:
        code = "HABER_OLUMSUZ"
    elif r["score"] < 1.5:
        code = "SKOR_ESIK_ALTI"
    else:
        p = ctx.plan(r)
        code = _code_from_plan(p)
        base["risk_seviyesi"] = p.get("risk_seviyesi")
        base["detay"]["riskler"] = p.get("riskler", [])[:12]
        g = p.get("girisler") or {}
        best = next((s for s in g.get("senaryolar", []) if s["tur"] == g.get("en_uygun")), None)
        if best:
            base.update(senaryo=best["tur"], giris=best["giris"], sl=best["sl"], tp1=best["tp1"], tp2=best["tp2"],
                        risk_seviyesi=best.get("risk_seviyesi"))
        else:
            base["detay"]["senaryolar"] = [{"tur": s["tur"], "durum": s.get("uygulanamaz") or s.get("kalite")}
                                           for s in g.get("senaryolar", [])]
            if p.get("neden_yok"):
                base["detay"]["neden_yok"] = p["neden_yok"]
        base["detay"]["fiyatlanmis"] = any(x.startswith("Haberden bu yana fiyat") for x in p.get("riskler", []))
    mod, text = REASONS[code]
    base.update(karar="onerildi" if code == "ONERILDI" else "onerilmedi", neden_kodu=code, modul=mod, neden=text)
    return base


def no_news_reason(conn, ticker: str, since_day: str) -> str:
    """Haber skoru olmayan hisse: hiç haber yok mu, analiz mi bekliyor, önemsiz mi bulundu?"""
    like = f"%,{ticker},%"
    rows = conn.execute("SELECT status, body FROM news WHERE (','||candidates||',') LIKE ? AND effective_date>? "
                        "AND status!='context'", (like, since_day)).fetchall()
    if not rows:
        return "HABER_YOK"
    if any(r["status"] == "new" for r in rows):
        return "HABER_ANALIZ_BEKLIYOR"
    return "HABER_ONEMSIZ"


def decisions_all(conn, universe: Dict[str, str], rows: List[dict], today: Optional[date] = None,
                  window: int = 7, ctx: Optional[Context] = None) -> List[Dict]:
    """Evrendeki her hisse için karar (haber skoru olanlar ayrıntılı, olmayanlar nedenle)."""
    from datetime import timedelta
    ctx = ctx or Context(conn, today)
    since = (ctx.today - timedelta(days=window)).isoformat()
    out, seen = [], set()
    for r in rows:
        out.append(decide(ctx, r))
        seen.add(r["ticker"])
    for ticker in sorted(universe):
        if ticker in seen:
            continue
        code = no_news_reason(conn, ticker, since)
        mod, text = REASONS[code]
        out.append({"ticker": ticker, "karar": "onerilmedi", "neden_kodu": code, "modul": mod, "neden": text,
                    "haber_skoru": None, "detay": {}})
    return out
