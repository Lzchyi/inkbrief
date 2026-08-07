from __future__ import annotations

import html
import re
import unicodedata
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

_TRACKING_PREFIXES = ("utm_",)
_TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}
_SPACE_RE = re.compile(r"\s+")
_TITLE_TOKEN_RE = re.compile(r"[^\w]+", re.UNICODE)
_MOJIBAKE_MARKERS = ("Ã", "Â", "â€", "â€™", "â€œ", "â€“", "â€”", "â€¦", "ðŸ", "ï»¿")
_MOJIBAKE_FRAGMENT_RE = re.compile(r"(?:Ã.|Â.|â..|ð...|ï..)")
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "for",
    "from",
    "in",
    "is",
    "of",
    "on",
    "the",
    "to",
    "with",
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def _mojibake_score(value: str) -> int:
    markers = sum(value.count(marker) for marker in _MOJIBAKE_MARKERS)
    controls = sum(0x80 <= ord(character) <= 0x9F for character in value)
    return markers + controls * 2 + value.count("\ufffd") * 3


def _decoded_candidate(value: str) -> str:
    best = value
    best_score = _mojibake_score(value)
    for encoding in ("cp1252", "latin-1"):
        try:
            candidate = value.encode(encoding).decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        score = _mojibake_score(candidate)
        if score < best_score:
            best = candidate
            best_score = score
    return best


def repair_mojibake(value: str) -> str:
    """Repair likely UTF-8-as-Western-text damage without changing clean Unicode."""

    current = value.replace("\ufffd", "?")
    if _mojibake_score(current) == 0:
        return current
    for _ in range(2):
        best = _decoded_candidate(current)
        if best == current:
            best = _MOJIBAKE_FRAGMENT_RE.sub(
                lambda match: _decoded_candidate(match.group(0)), current
            )
        if best == current:
            break
        current = best
    return current


def strip_markup(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        text = " ".join(parser.parts)
    except Exception:
        text = re.sub(r"<[^>]+>", " ", value)
    return _SPACE_RE.sub(" ", html.unescape(text)).strip()


def canonical_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parts = urlsplit(value)
    scheme = parts.scheme.lower() or "https"
    host = (parts.hostname or "").lower()
    if not host:
        return value
    port = parts.port
    netloc = host
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{host}:{port}"
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if path != "/":
        path = path.rstrip("/")
    query = [
        (key, item)
        for key, item in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in _TRACKING_KEYS
        and not any(key.lower().startswith(prefix) for prefix in _TRACKING_PREFIXES)
    ]
    return urlunsplit((scheme, netloc, path, urlencode(sorted(query)), ""))


def normalized_title(value: str) -> str:
    value = unicodedata.normalize("NFKC", strip_markup(value)).casefold()
    tokens = [token for token in _TITLE_TOKEN_RE.split(value) if token and token not in _STOPWORDS]
    return " ".join(tokens)


def title_tokens(value: str) -> frozenset[str]:
    return frozenset(normalized_title(value).split())
