from __future__ import annotations

import re


def normalize_whitespace(text: str) -> str:
    """Collapses consecutive whitespace sequences into a single space and strips boundaries."""
    return " ".join(text.strip().split())


def find_normalized_span(text: str, query: str) -> tuple[int, int] | None:
    """Locates the character span (start, end) of query in text, tolerating arbitrary internal whitespace differences.

    Matches query words in sequence allowing any whitespace (including newlines) between them.
    Returns 0-indexed [start, end) offsets in original text, or None if ungrounded.
    """
    clean_query = query.strip()
    if not clean_query or not text:
        return None

    tokens = clean_query.split()
    if not tokens:
        return None

    escaped = [re.escape(t) for t in tokens]
    pattern = re.compile(r"\s+".join(escaped))
    match = pattern.search(text)
    if match is None:
        return None
    return match.start(), match.end()
