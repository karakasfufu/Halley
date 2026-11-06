"""Faz 4 başlangıcı: ayrı veritabanında, bütçeli KAP olay pilotu.

Örneklenmiş olaylar tam günlük skor geçmişi değildir; eşik kalibrasyonu yapmaz.
Bugünkü evreni/piyasa değerini geçmişe taşımaz. Eksikleri sonuçlardan gizlemez.
"""
import hashlib
import json
import math
from bisect import bisect_right
from datetime import date, datetime, timedelta
from typing import Optional

from . import analyzer, config, db, kap

MODEL = "gpt-5-mini"
BUDGET_NANO = 1_000_000_000  # bütün pilot veritabanı için 1 USD; önceki harcamalar korunur
MAX_NEWS_PER_RUN = 10
INPUT_NANO = 250             # 1M token için 0.25 USD (2026-11-06)
OUTPUT_NANO = 2000           # 1M token için 2 USD, düşünme tokenları dahil
MAX_OUTPUT = 16000           # kesilen yanıt sonuç sayılmaz, otomatik yeniden denenmez
BENCHMARK = "XU100"
LIMITATIONS = (
    "Bu bir KAP olay pilotudur; günlük birleşik skor veya portföy backtest'i değildir.",
    "Hisseler geçmiş bildirim kodlarından alınır. Tarihsel kotasyon listesi doğrulanmadı; "
    "evren kapsamı ve kapanmış hisselerin fiyat eksikleri sonuçları etkileyebilir.",
    "Güncel piyasa değeri ve son fiyat kullanılmaz. Tarihli şirket büyüklüğü verisi henüz yoktur.",
    "Resim PDF, Excel ekleri, okunmayan veya kesilen metinler ayrıntı kaybına yol açabilir. "
    "Pilot belge kontrolü bunları işaretler; tam doğruluk garantisi vermez.",
    "İşlem günleri endeks fiyat tarihlerinden türetilir; resmi tatil/yarım gün takvimiyle "
    "henüz doğrulanmadı. Fiyat servisi eksikleri tatille karışabilir.",
    "Modelin geçmiş olayları bilmesi yalnızca talimatla tamamen engellenemez. "
    "Eşik değiştirmeden önce ayrı dönem ve ileriye dönük takip gerekir.",
    "Örnekleme, aynı hisseye ait yakın olaylar ve örtüşen vadeler bağımsız gözlem sayılmaz. "
    "Özet oranlar istatistiksel kanıt veya yatırım önerisi değildir.",
)


class BudgetStop(RuntimeError):
    pass


def connect(path=None):
    conn = db.connect(path or config.DATA / "backtest" / "pilot.db")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS pilot_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS pilot_selection (news_id TEXT PRIMARY KEY);
        CREATE TABLE IF NOT EXISTS pilot_documents (
            news_id TEXT PRIMARY KEY, sha256 TEXT, issues TEXT NOT NULL,
            original_chars INTEGER, checked_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pilot_calls (
            fingerprint TEXT PRIMARY KEY, news_id TEXT NOT NULL, purpose TEXT NOT NULL,
            state TEXT NOT NULL, reserved_nano INTEGER NOT NULL, charged_nano INTEGER NOT NULL DEFAULT 0,
            input_tokens INTEGER, output_tokens INTEGER, result_json TEXT,
            request_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pilot_bars (
            ticker TEXT NOT NULL, date TEXT NOT NULL, open REAL, high REAL, low REAL, close REAL,
            PRIMARY KEY(ticker,date)
        );
    """)
    return conn


def _meta(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO pilot_meta VALUES(?,?)", (key, json.dumps(value, ensure_ascii=False)))


def metadata(conn):
    return {r["key"]: json.loads(r["value"]) for r in conn.execute("SELECT * FROM pilot_meta")}


def wallet(conn):
    row = conn.execute("SELECT COALESCE(SUM(charged_nano),0) charged, "
                       "COALESCE(SUM(reserved_nano),0) reserved FROM pilot_calls").fetchone()
    return {"charged_usd": row["charged"] / 1e9, "reserved_usd": row["reserved"] / 1e9,
            "remaining_usd": max(0, BUDGET_NANO - row["charged"] - row["reserved"]) / 1e9}


def _issuer_codes(item):
    # Dolaylı etkilenen şirketler örnek evrenini belirlemez; güncel şirket listesi çağrılmaz.
    import re
    return sorted(set(c for c in re.split(r"[,\s]+", item.get("stockCodes") or "")
                      if re.fullmatch(r"[A-Z0-9]{4,6}", c)))


def select_items(items, limit):
    eligible = {}
    for item in items:
        if _issuer_codes(item) and not any(s in (item.get("subject") or "") for s in config.KAP_SKIP_SUBJECTS):
            eligible[str(item["disclosureIndex"])] = item
    # Fiyat veya model sonucuna bakmadan, tekrar üretilebilir örnekleme.
    selected = sorted(eligible.values(), key=lambda it: hashlib.sha256(
        ("halley-pilot-v1:" + str(it["disclosureIndex"])).encode()).hexdigest())[:limit]
    return selected, len(eligible)


def document_issues(body, subject):
    issues = []
    if not body or len(body.strip()) < 100:
        issues.append("Metin yok veya güvenilir analiz için çok kısa.")
    if len(body or "") > config.MAX_BODY_CHARS:
        issues.append("Metin analiz sınırını aşıyor; sessizce kesilerek analiz edilmedi.")
    if "Finansal Rapor" in subject and "[FİNANSAL TABLO ÖZETİ" not in (body or ""):
        issues.append("Finansal tablo özeti alınamadı.")
    return issues


def fetch_document(index, subject):
    """Pilot için eksik/kesilmiş ekleri de denetler. Günlük akıştan bağımsızdır."""
    issues = []
    if "Finansal Rapor" in subject:
        body = kap.fetch_body(index, subject)
        issues.extend(document_issues(body, subject))
        # Finansal özet zaten kırpılmış olabilir; eşikteki belgeyi tam kabul etme.
        if len(body) >= config.FINANCIAL_SUMMARY_CHARS:
            issues.append("Finansal özet uzunluk sınırına ulaştı.")
        return body, issues
    body, attachments = kap._parse_page(kap._get(kap.DETAIL_URL.format(index=index)).text)
    # Pilotta tüm ekleri denetle; eksik materyal olan bildirime para harcama.
    import time
    from .textutil import strip_translation
    # Rutin ekler (hazirun, vekaletname...) ve Türkçesi olan İngilizce kopyalar sınırı doldurmaz;
    # atlananlar metinde açıkça listelenir.
    pdfs, skipped = kap.select_attachments(attachments)
    if any(str(a.get("fileExtension", "")).lower() not in ("pdf",) for a in attachments):
        issues.append("PDF dışındaki ekler okunmadı.")
    if len(pdfs) > config.KAP_MAX_ATTACHMENTS:
        issues.append("PDF ek sayısı okuma sınırını aşıyor.")
    if skipped:
        body += "\n\n[ATLANAN RUTİN/ÇEVİRİ EKLER: " + "; ".join(skipped) + "]"
    for a in pdfs[:config.KAP_MAX_ATTACHMENTS]:
        time.sleep(config.KAP_REQUEST_DELAY)
        if not a.get("objId"):
            issues.append("PDF ek adresi yok.")
            continue
        data = kap._get(f"{config.KAP_BASE}/tr/api/file/download/{a['objId']}").content
        try:
            import io
            from pypdf import PdfReader
            start = data.find(b"%PDF")
            if start < 0 or len(data) > 5_000_000:
                raise ValueError("PDF dosyası okunamadı veya boyut sınırını aşıyor.")
            reader = PdfReader(io.BytesIO(data[start:]))
            if len(reader.pages) > config.KAP_ATTACHMENT_PAGES:
                issues.append("PDF sayfa sınırını aşıyor.")
            texts = [p.extract_text() or "" for p in reader.pages[:config.KAP_ATTACHMENT_PAGES]]
            blank = [i for i, t in enumerate(texts) if not t.strip()]
            note = ""
            if blank == [len(reader.pages) - 1] and len(texts) >= 2:
                # Yalnızca son sayfa boşsa bu genelde imza/kaşe sayfasıdır: engelleme, modele bildir.
                note = "\n[NOT: Son sayfada metin yok; muhtemelen imza/kaşe sayfası.]"
            elif blank:
                issues.append("PDF içinde metni okunamayan sayfa var.")
            text = strip_translation("\n".join(texts)) + note
            if len(text) > config.KAP_ATTACHMENT_CHARS:
                issues.append("PDF metni uzunluk sınırını aşıyor.")
            body += f"\n\n[EK: {a.get('fileName', 'PDF')}]\n{text[:config.KAP_ATTACHMENT_CHARS]}"
        except Exception:
            issues.append("PDF okunamadı; resim/bozuk/şifreli olabilir.")
    issues.extend(document_issues(body, subject))
    return body, sorted(set(issues))


def prepare(conn, start, end, limit=100, progress=None):
    if not isinstance(start, date) or not isinstance(end, date) or start > end:
        raise ValueError("Geçerli bir tarih aralığı seçin.")
    if (end - start).days > 31 or end >= datetime.now(config.TR_TZ).date() - timedelta(days=21):
        raise ValueError("Pilot en fazla 32 gün olmalı ve en az 21 gün önce bitmeli.")
    if limit not in (100, 200):
        raise ValueError("Pilot boyutu 100 veya 200 olmalı.")
    say = progress or (lambda m, p: None)
    say("Geçmiş KAP listesi alınıyor...", 0.01)
    items = kap.list_disclosures(start, end)
    selected, eligible = select_items(items, limit)
    if not selected:
        raise ValueError("Bu aralıkta uygun bildirim bulunamadı; önceki seçim korunuyor.")
    conn.execute("DELETE FROM pilot_selection")
    _meta(conn, "collection_note", None)
    _meta(conn, "selection", {"start": start.isoformat(), "end": end.isoformat(), "limit": limit,
                             "listed": len(items), "eligible": eligible, "selected": len(selected),
                             "sampling": "sha256(halley-pilot-v1:bildirim_id)"})
    _meta(conn, "limitations", LIMITATIONS)
    now = datetime.now(config.TR_TZ).isoformat()
    from .textutil import effective_date
    for it in selected:
        nid = f"kap:{it['disclosureIndex']}"
        published = datetime.strptime(it["publishDate"], "%d.%m.%Y %H:%M:%S").replace(tzinfo=config.TR_TZ)
        if not start <= published.date() <= end:
            raise ValueError("KAP istenen tarih aralığı dışında bildirim döndürdü.")
        codes = _issuer_codes(it)
        conn.execute("INSERT OR IGNORE INTO news(id,source,published_at,effective_date,title,subject,url,"
                     "candidates,fetched_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (nid, "kap", published.isoformat(), effective_date(published),
                      it.get("summary") or it.get("subject") or nid, it.get("subject") or "",
                      kap.DETAIL_URL.format(index=it["disclosureIndex"]), ",".join(codes), now))
        conn.execute("INSERT INTO pilot_selection VALUES(?)", (nid,))
    conn.commit()
    rows = conn.execute("SELECT n.* FROM news n JOIN pilot_selection s ON s.news_id=n.id ORDER BY n.published_at").fetchall()
    import time
    for i, row in enumerate(rows):
        say(f"Belgeler denetleniyor ({i + 1}/{len(rows)})...", (i + 1) / len(rows))
        old = conn.execute("SELECT issues FROM pilot_documents WHERE news_id=?", (row["id"],)).fetchone()
        if old and not json.loads(old["issues"]):
            continue
        if row["status"] == "analyzed":
            continue  # sonuç üreten belge ve istek kaydı sonradan değiştirilmez
        try:
            body, issues = fetch_document(int(row["id"].split(":")[1]), row["subject"])
        except kap.RateLimited:
            _meta(conn, "collection_note", "KAP istek sınırı uyguladı; hazırlanmayı daha sonra sürdürün.")
            conn.commit()
            break
        except Exception as e:
            body, issues = "", ["Belge alınamadı: " + type(e).__name__]
        finally:
            time.sleep(config.KAP_REQUEST_DELAY)
        conn.execute("UPDATE news SET body=?,note=? WHERE id=?", (body, "; ".join(issues) or None, row["id"]))
        conn.execute("INSERT OR REPLACE INTO pilot_documents VALUES(?,?,?,?,?)",
                     (row["id"], hashlib.sha256(body.encode()).hexdigest(), json.dumps(issues, ensure_ascii=False),
                      len(body), datetime.now(config.TR_TZ).isoformat()))
        conn.commit()
    return overview(conn)


def price_coverage(conn):
    keys = {(r["ticker"], r["date"]) for r in conn.execute(
        "SELECT ticker,date FROM pilot_bars WHERE open>0 AND close>0")}
    sessions = sorted(d for t, d in keys if t == BENCHMARK)
    ready = set()
    for row in conn.execute("SELECT n.id,n.candidates,n.published_at FROM news n JOIN pilot_selection s ON s.news_id=n.id"):
        day = datetime.fromisoformat(row["published_at"]).astimezone(config.TR_TZ).date().isoformat()
        idx = bisect_right(sessions, day)
        future = sessions[idx:idx + 10]
        codes = [c for c in row["candidates"].split(",") if c]
        if len(future) == 10 and codes and all((c, d) in keys for c in codes for d in future):
            ready.add(row["id"])
    return ready


def overview(conn):
    rows = conn.execute("SELECT n.id,n.status,n.body,d.issues FROM news n JOIN pilot_selection s ON s.news_id=n.id "
                        "LEFT JOIN pilot_documents d ON d.news_id=n.id").fetchall()
    covered = price_coverage(conn)
    return {"selected": len(rows), "ready": sum(r["status"] == "new" and r["issues"] == "[]" for r in rows),
            "priced_ready": sum(r["status"] == "new" and r["issues"] == "[]" and r["id"] in covered for r in rows),
            "missing_prices": sum(r["id"] not in covered for r in rows),
            "analyzed": sum(r["status"] == "analyzed" for r in rows),
            "incomplete": sum(r["issues"] is None or r["issues"] != "[]" for r in rows),
            "wallet": wallet(conn), "metadata": metadata(conn)}


class PilotLLM:
    """Kalıcı istek önbelleği ve çağrı ÖNCESİ maliyet rezervasyonu; otomatik tekrar yok."""
    def __init__(self, conn, news_id, client=None):
        self.conn, self.news_id, self.sequence = conn, news_id, 0
        if client is None:
            from openai import OpenAI
            client = OpenAI(max_retries=0)
        self.client = client

    def parse(self, model, system, user, schema, reasoning_effort: Optional[str] = None):
        if model != MODEL:
            raise ValueError("Pilot yalnızca gpt-5-mini kullanır; model ayarını kontrol edin.")
        purpose = "primary" if self.sequence == 0 else "second"
        self.sequence += 1
        request = dict(model=model, system=system, user=user, schema=schema.model_json_schema(),
                       reasoning_effort=reasoning_effort, max_completion_tokens=MAX_OUTPUT,
                       news_id=self.news_id, purpose=purpose, version=1)
        raw = json.dumps(request, ensure_ascii=False, sort_keys=True)
        fingerprint = hashlib.sha256(raw.encode()).hexdigest()
        previous = self.conn.execute("SELECT * FROM pilot_calls WHERE fingerprint=?", (fingerprint,)).fetchone()
        if previous:
            if previous["state"] != "done":
                raise BudgetStop("Önceki çağrının harcaması belirsiz; otomatik tekrar gönderilmedi.")
            # İkinci görüşün ayrı purpose anahtarı var; ilk görüş önbelleği teyit sayılmaz.
            return schema.model_validate_json(previous["result_json"]), 0, 0
        # UTF-8 bayt sayısı + geniş şema/mesaj payı, girdi tokenı için ihtiyatlı üst sınır.
        input_bound = len(raw.encode("utf-8")) + 4096
        reserve = input_bound * INPUT_NANO + MAX_OUTPUT * OUTPUT_NANO
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            used = self.conn.execute("SELECT COALESCE(SUM(charged_nano+reserved_nano),0) FROM pilot_calls").fetchone()[0]
            if used + reserve > BUDGET_NANO:
                raise BudgetStop("1 USD pilot sınırında duruldu; sonuçlar saklandı.")
            self.conn.execute("INSERT INTO pilot_calls(fingerprint,news_id,purpose,state,reserved_nano,request_json,created_at) "
                              "VALUES(?,?,?,'reserved',?,?,?)",
                              (fingerprint, self.news_id, purpose, reserve, raw, datetime.now(config.TR_TZ).isoformat()))
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        kwargs = dict(model=model, response_format=schema, max_completion_tokens=MAX_OUTPUT,
                      messages=[{"role": "system", "content": system}, {"role": "user", "content": user}])
        if reasoning_effort:
            kwargs["reasoning_effort"] = reasoning_effort
        try:
            resp = self.client.chat.completions.parse(**kwargs)
            usage = resp.usage
            if usage is None:
                raise RuntimeError("Kullanım bilgisi gelmedi; rezervasyon korunuyor.")
            tin, tout = usage.prompt_tokens, usage.completion_tokens
            charged = tin * INPUT_NANO + tout * OUTPUT_NANO
            # Hatalı/ret/kesilmiş yanıtta da bilinen harcama saklanır; kullanılabilir sonuç üretilmez.
            self.conn.execute("UPDATE pilot_calls SET charged_nano=?,reserved_nano=0,input_tokens=?,output_tokens=? "
                              "WHERE fingerprint=?", (charged, tin, tout, fingerprint))
            self.conn.commit()
            choice = resp.choices[0]
            if choice.finish_reason != "stop" or choice.message.refusal or choice.message.parsed is None:
                raise RuntimeError("Yanıt tamamlanmadı veya doğrulanamadı; sonuç kullanılmadı.")
            result = schema.model_validate(choice.message.parsed.model_dump())
            self.conn.execute("UPDATE pilot_calls SET state='done',result_json=? WHERE fingerprint=?",
                              (result.model_dump_json(), fingerprint))
            self.conn.commit()
            return result, tin, tout
        except Exception:
            self.conn.execute("UPDATE pilot_calls SET state='uncertain' WHERE fingerprint=?", (fingerprint,))
            self.conn.commit()
            raise


def analyze(conn, progress=None, client=None, max_items=MAX_NEWS_PER_RUN):
    if not isinstance(max_items, int) or not 1 <= max_items <= MAX_NEWS_PER_RUN:
        raise ValueError("Bir turda en fazla 10 bildirim analiz edilebilir.")
    if config.MODEL_ANALYSIS != MODEL:
        raise ValueError("Model ayarı gpt-5-mini olmalı.")
    if not config.SECOND_OPINION:
        raise ValueError("Doğruluk pilotu için ikinci görüş kontrolü açık olmalı.")
    stats = {"analyzed": 0, "filtered_out": 0, "errors": 0, "impacts": 0, "dropped_tickers": 0,
             "flagged": 0, "input_tokens": 0, "output_tokens": 0, "skipped_prices": 0}
    rows = conn.execute("SELECT n.*, d.sha256 AS document_sha FROM news n JOIN pilot_selection s ON s.news_id=n.id "
                        "JOIN pilot_documents d ON d.news_id=n.id WHERE n.status='new' AND d.issues='[]' "
                        "ORDER BY n.published_at,n.id").fetchall()
    covered = price_coverage(conn)
    for i, row in enumerate(rows):
        if stats["analyzed"] >= max_items:
            break
        if progress:
            progress(f"Pilot analiz ediliyor ({i + 1}/{len(rows)})...", i / max(1, len(rows)))
        if row["id"] not in covered:
            stats["skipped_prices"] += 1
            continue  # ölçülemeyecek olaya API harcaması yapma; kaydı silme veya nötr sayma
        if any(s in (row["subject"] or "") for s in config.KAP_SKIP_SUBJECTS):
            # Seçimden sonra rutin sayılan konu (ör. fon piyasa yapıcılığı): para harcama, kaydı silme.
            stats["skipped_routine"] = stats.get("skipped_routine", 0) + 1
            continue
        # Yalnızca bildirimin o tarihte taşıdığı ihraççı kodları; bugünkü evren ve fiyat çağrılmaz.
        universe = {c: c for c in row["candidates"].split(",") if c}
        try:
            if hashlib.sha256((row["body"] or "").encode()).hexdigest() != row["document_sha"]:
                raise ValueError("Denetimden sonra belge metni değişti; yeniden belge denetimi gerekiyor.")
            llm = PilotLLM(conn, row["id"], client=client)
            result = analyzer._work(llm, row, universe, {})
            analyzer._store(conn, row, universe, result, stats)
        except Exception as e:
            # Başarılı ilk görüş saklıdır; ikinci görüş/bağlantı hatası sahte teyit oluşturmaz.
            stats["stopped"] = str(e)[:250]
            break
    return stats


def _number(v):
    try:
        f = float(v)
        return f if math.isfinite(f) and f > 0 else None
    except (ValueError, TypeError):
        return None


def update_prices(conn):
    """OHLC ve endeks tarihleri. Güncel piyasa değeri indirilmez."""
    import pandas as pd
    import yfinance as yf
    selection = metadata(conn).get("selection")
    if not selection:
        raise ValueError("Önce pilot belgelerini hazırlayın.")
    start = date.fromisoformat(selection["start"]) - timedelta(days=5)
    end = min(date.fromisoformat(selection["end"]) + timedelta(days=40), datetime.now(config.TR_TZ).date())
    tickers = sorted({c for r in conn.execute("SELECT n.candidates FROM news n JOIN pilot_selection s ON s.news_id=n.id")
                      for c in r[0].split(",") if c} | {BENCHMARK})
    symbols = [t + ".IS" for t in tickers]
    frame = yf.download(symbols, start=start.isoformat(), end=end.isoformat(), interval="1d",
                        auto_adjust=True, progress=False, group_by="ticker", threads=False)
    count = 0
    # Başarılı yeni yanıtla bu aralığı değiştir; eski fiyatları yeni indirmeyle karıştırma.
    if frame.empty:
        raise ValueError("Fiyat servisi veri döndürmedi; önceki fiyatlar korunuyor.")
    for ticker, symbol in zip(tickers, symbols):
        conn.execute("DELETE FROM pilot_bars WHERE ticker=? AND date>=? AND date<?",
                     (ticker, start.isoformat(), end.isoformat()))
        if isinstance(frame.columns, pd.MultiIndex):
            if symbol not in frame.columns.get_level_values(0):
                continue
            sub = frame[symbol]
        else:
            sub = frame
        for idx, r in sub.iterrows():
            values = [_number(r.get(c)) for c in ("Open", "High", "Low", "Close")]
            if values[0] is None or values[3] is None:
                continue
            conn.execute("INSERT OR REPLACE INTO pilot_bars VALUES(?,?,?,?,?,?)",
                         (ticker, idx.date().isoformat(), *values))
            count += 1
    _meta(conn, "prices", {"downloaded_at": datetime.now(config.TR_TZ).isoformat(), "rows": count,
                          "adjustment": "yfinance auto_adjust=True; fiyat düzeltmeleri bağımsız doğrulanmadı"})
    conn.commit()
    return count


def evaluate(conn, cost_bps=20):
    """Her bildirim için olay ölçümü. Eksik giriş/çıkış daha sonraki güne kaydırılmaz."""
    if not 0 <= cost_bps <= 1000:
        raise ValueError("Geçersiz toplam işlem maliyeti.")
    bars = {(r["ticker"], r["date"]): dict(r) for r in conn.execute("SELECT * FROM pilot_bars")}
    sessions = sorted(d for (t, d) in bars if t == BENCHMARK)
    impacts = conn.execute("SELECT i.* FROM impacts i JOIN pilot_selection s ON s.news_id=i.news_id ORDER BY i.published_at").fetchall()
    out = []
    for impact in impacts:
        published = datetime.fromisoformat(impact["published_at"]).astimezone(config.TR_TZ)
        entry_idx = bisect_right(sessions, published.date().isoformat())
        for horizon in (1, 3, 5, 10):
            record = {"bildirim": impact["news_id"], "hisse": impact["ticker"], "yön": impact["direction"],
                      "vade": horizon, "giriş": None, "çıkış": None, "getiri_%": None,
                      "net_getiri_%": None, "endekse_göre_%": None, "en_düşük_%": None, "eksik": "",
                      "uygulanabilirlik": ""}
            exit_idx = entry_idx + horizon - 1
            if exit_idx >= len(sessions):
                record["eksik"] = "İşlem takvimi veya ileri fiyat dönemi eksik."
                out.append(record)
                continue
            entry, exit_day = sessions[entry_idx], sessions[exit_idx]
            record.update({"giriş": entry, "çıkış": exit_day})
            a, b = bars.get((impact["ticker"], entry)), bars.get((impact["ticker"], exit_day))
            interval = [bars.get((impact["ticker"], d)) for d in sessions[entry_idx:exit_idx + 1]]
            if a is None or b is None or any(r is None for r in interval):
                record["eksik"] = "Hisse fiyatı eksik veya işlem durması var; tarih kaydırılmadı."
            else:
                gross = (b["close"] / a["open"] - 1) * 100
                bm_a, bm_b = bars[(BENCHMARK, entry)], bars[(BENCHMARK, exit_day)]
                benchmark_return = (bm_b["close"] / bm_a["open"] - 1) * 100
                lows = [r["low"] for r in interval if r["low"] is not None]
                record.update({"getiri_%": gross, "net_getiri_%": gross - cost_bps / 100,
                               "endekse_göre_%": gross - benchmark_return - cost_bps / 100,
                               "en_düşük_%": (min(lows) / a["open"] - 1) * 100 if len(lows) == horizon else None,
                               "uygulanabilirlik": _lock_note(a, b)})
            out.append(record)
    return out


def _locked(bar) -> bool:
    """Açılış = en yüksek = en düşük = kapanış: gün boyu tek fiyat (çoğunlukla tavan/taban kilidi)."""
    values = [bar.get(k) for k in ("open", "high", "low", "close")]
    return all(v is not None for v in values) and max(values) - min(values) < 1e-9


def _lock_note(entry_bar, exit_bar) -> str:
    # Bu günlerde emir karşılanmamış olabilir; getiri hesaplanır ama "uygulanamaz olabilir" diye işaretlenir.
    notes = []
    if _locked(entry_bar):
        notes.append("giriş günü tek fiyat (tavan/taban kilidi olabilir; alış gerçekleşmeyebilirdi)")
    if _locked(exit_bar):
        notes.append("çıkış günü tek fiyat (tavan/taban kilidi olabilir; satış gerçekleşmeyebilirdi)")
    return "; ".join(notes)
