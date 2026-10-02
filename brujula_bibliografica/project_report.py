"""Cifras verificables para la portada del proyecto Scopus + Web of Science."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUTPUT = ROOT / "outputs" / "dataset_scopus_wos"
FILES = {
    "scopus": DATA / "SC1.csv",
    "wos": DATA / "WS1.xls",
    "unified": OUTPUT / "dataset_unificado.xlsx",
    "duplicates": OUTPUT / "dataset_unificado_duplicados.xlsx",
    "deduplicated": OUTPUT / "dataset_final_deduplicado.xlsx",
    "final": OUTPUT / "dataset_final.xlsx",
    "analyzed": OUTPUT / "dataset_analizado.csv",
    "screened_out": OUTPUT / "descartados_filtro_termografia.csv",
}
SCOPUS_LOGO = ROOT / "outputs" / "consolidado_4_busquedas" / "Soporte" / "logos" / "Scopus_logo.svg.png"
WOS_LOGO = ROOT / "outputs" / "consolidado_4_busquedas" / "Soporte" / "logos" / "Web_of_Science_Logo_12.2023.svg.png"


def _nonempty(series: pd.Series) -> int:
    return int(series.fillna("").astype(str).str.strip().ne("").sum())


def project_summary() -> dict[str, object]:
    """Derive flow counts from the saved project files, not presentation literals."""
    unified = pd.read_excel(FILES["unified"], dtype=str).fillna("")
    duplicates = pd.read_excel(FILES["duplicates"], dtype=str).fillna("")
    deduplicated = pd.read_excel(FILES["deduplicated"], dtype=str).fillna("")
    final = pd.read_excel(FILES["final"], dtype=str).fillna("")
    analyzed = pd.read_csv(FILES["analyzed"], dtype=str, low_memory=False).fillna("")
    screened_out = pd.read_csv(FILES["screened_out"], dtype=str, low_memory=False).fillna("")
    source_counts = Counter(unified["Database"])
    duplicate_counts = Counter(duplicates["Estado"])
    fused_counts = Counter(deduplicated["Registros_fusionados"])
    return {
        "scopus": source_counts["Scopus"],
        "wos": source_counts["Web of Science"],
        "unified_rows": len(unified),
        "unified_columns": len(unified.columns),
        "duplicates_columns": len(duplicates.columns),
        "duplicate_rows": duplicate_counts["Duplicado"],
        "pairs_fused": fused_counts["2"],
        "deduplicated_rows": len(deduplicated),
        "screened_out": len(screened_out),
        "shared_doi_distinct_titles": sum("distinto" in str(v) for v in duplicates["Estado"]),
        "without_doi": duplicate_counts["Sin DOI"],
        "doi_original": _nonempty(unified["DOI"]),
        "doi_final": _nonempty(final["DOI"]),
        "final_rows": len(final),
        "final_columns": len(final.columns),
        "analyzed_rows": len(analyzed),
        "analyzed_columns": len(analyzed.columns),
        "analysis_columns": len(analyzed.columns) - len(final.columns),
        "levels": Counter(analyzed["nivel_recomendacion"]),
    }
