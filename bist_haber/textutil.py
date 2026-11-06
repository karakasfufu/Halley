"""Türkçe metin ve zaman yardımcıları."""
import html
import re
from datetime import date, datetime, timedelta

from . import config


def tr_lower(s: str) -> str:
    """Türkçe kurallarına göre küçük harf (I→ı, İ→i)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def html_to_text(s: str) -> str:
    s = re.sub(r"<(script|style)\b.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</tr>|</div>", "\n", s, flags=re.I)
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    s = re.sub(r"[ \t\xa0]+", " ", s)
    return re.sub(r"\n\s*\n+", "\n", s).strip()


_TR_CHARS = re.compile(r"[çğıöşüÇĞİÖŞÜ]")
_EN_WORDS = set("""
the of and to in on for by with as at from that this is are was were be been has have had will would
our its it an a or which who whose than then there these those such any all not no into upon under
over per via within without also both each other same about regarding related hereby herein thereof
notification flag disclosure announcement content explanations explanation date previous subject update
correction postponed material event general forward looking evaluations evaluation statement translated
translation version english turkish prevail prevails discrepancy inconsistency case between purposes
informational respectfully announced public company companys companies shares share shareholders board
directors capital total amount aggregate value excluding including executed sales agreements agreement
within scope project portfolio units timeshare investors investor information basis taken provided
pursuant accordance decided decision resolution meeting registered issued increase decrease approved
""".split())


def _is_english(line: str) -> bool:
    words = re.findall(r"[A-Za-zçğıöşüÇĞİÖŞÜ']+", line)
    if len(words) < 2:
        return False
    # Türkçe harf içeren kelimeler çoğunluktaysa satır Türkçedir. İngilizce satırda yalnızca
    # özel isimler (ör. "Sinpaş Kızılbük") Türkçe harf içerebilir.
    tr_words = sum(bool(_TR_CHARS.search(w)) for w in words)
    if tr_words / len(words) > 0.25:
        return False
    share = sum(w.lower().strip("'") in _EN_WORDS for w in words) / len(words)
    return share >= 0.5 or (len(words) >= 6 and share >= 0.3)


def strip_translation(text: str) -> str:
    """KAP metinlerindeki İngilizce çeviri satırlarını atar (Türkçe asıl metin korunur).

    KAP bildirimlerinin çoğu aynı içeriği Türkçe + İngilizce verir; çeviri atılınca metin
    yaklaşık yarıya iner, bilgi kaybolmaz. Belge tamamen İngilizceyse (ör. yabancı ihraççı)
    ya da geriye çok az Türkçe kalırsa metin olduğu gibi döndürülür.
    """
    if not text:
        return text
    lines = text.splitlines()
    kept = [ln for ln in lines if not _is_english(ln.strip())]
    result = "\n".join(kept)
    if len(result) < 200 and len(text) > 2 * max(len(result), 1):
        return text  # çeviri değil asıl metin İngilizce olabilir; dokunma
    return result


_STAMP_LINE = re.compile(r"doğrulama kodu|dogrulama kodu|spk\.gov\.tr|dokuman-dogrulama", re.I)
_PAGE_NO = re.compile(r"^[\s\d|/.\-]{0,12}$")  # yalnızca kısa sayfa numarası satırı (ör. "3", "01 07")


def page_is_blank(text: str) -> bool:
    """Sayfa okunabilir içerik taşımıyor mu?

    SPK onaylı belgeler taranmış resimdir; her sayfada yalnızca "Doğrulama Kodu … spk.gov.tr"
    damgası metin olarak okunur. Damga ve kısa sayfa numarası satırları atılınca 40 karakterden
    az metin kalıyorsa sayfa boş (taranmış) sayılır. Rakam tablosu satırları atılmaz.
    """
    kept = [ln for ln in (text or "").splitlines()
            if not _STAMP_LINE.search(ln) and not _PAGE_NO.match(ln.strip())]
    return len("".join(kept).strip()) < 40


def title_key(title: str) -> str:
    """Farklı sitelerdeki aynı haberi yakalamak için normalize başlık."""
    return re.sub(r"[^0-9a-zçğıöşü]+", "", tr_lower(title))[:80]


def next_weekday(d: date) -> date:
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d


def effective_date(published: datetime) -> str:
    """Haberin en erken işlem görebileceği gün (Dipnot 7).

    Hafta içi seans kapanışından önce → aynı gün; sonra ya da hafta sonu → sonraki
    iş günü. Resmi tatiller henüz hesaba katılmıyor.
    """
    local = published.astimezone(config.TR_TZ)
    d = local.date()
    if d.weekday() >= 5 or local.hour >= config.SESSION_CLOSE_HOUR:
        return next_weekday(d).isoformat()
    return d.isoformat()
