"""Enlaces de consulta de artículos, con prioridad para identificadores propios."""

from __future__ import annotations

import re
from urllib.parse import quote


DOI = re.compile(r"^10\.\d{4,9}/\S+$", re.I)


def article_resource(row: dict[str, object]) -> str:
    """Return an article-level URL; ISSN alone identifies a journal, not an article."""
    for field in ("DOI", "DOI_WoS"):
        value = str(row.get(field, "") or "").strip()
        value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value, flags=re.I)
        if DOI.fullmatch(value):
            return "https://doi.org/" + quote(value, safe="/;():-._~")
    for field in ("DOI Link", "Link"):
        value = str(row.get(field, "") or "").strip()
        if re.match(r"^https?://", value, re.I):
            return value
    pubmed = str(row.get("PubMed ID", "") or "").strip()
    if pubmed.isdigit():
        return f"https://pubmed.ncbi.nlm.nih.gov/{pubmed}/"
    eid = str(row.get("EID", "") or "").strip()
    if re.fullmatch(r"2-s2\.0-\d+", eid):
        return "https://www.scopus.com/record/display.uri?eid=" + quote(eid)
    title = str(row.get("titulo_analisis") or row.get("Title") or "").strip()
    return "https://scholar.google.com/scholar?q=" + quote(title)
