"""Cribado bibliográfico previo al dataset final de termografía mamaria.

Conserva los identificadores originales y registra cada exclusión. La regla
comprueba menciones en título, resumen y palabras clave; no sustituye la
revisión de elegibilidad en texto completo.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

from analisis_local import analyze_rows
from analytics import prepare_records
from core import csv_bytes, guess_column, normalize


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs" / "dataset_scopus_wos"
SOURCE_FINAL = OUTPUT / "dataset_final_deduplicado.xlsx"
SOURCE_ANALYZED = OUTPUT / "dataset_analizado_deduplicado.csv"

# "Infrared" solo no basta: también describe espectroscopía y fluorescencia NIR.
THERMOGRAPHY = re.compile(
    r"\b(thermog\w*|thermogram\w*|termograf\w*|termogram\w*|"
    r"thermal imag\w*|thermal breast|breast thermal|infrared imag\w*|"
    r"infrarro\w* imag\w*)\b"
)
BREAST = re.compile(r"\b(breast|mammary|mamari\w*|mama|seno\w*)\b")
ANIMAL_TITLE = re.compile(
    r"\b(cow|cows|bovine|buffalo\w*|poultry|broiler\w*|veterinar\w*|"
    r"sheep|goat\w*|swine|equine|livestock|udder|chicken\w*|dairy|mastitis)\b"
)


def exclusion_reason(record: dict[str, str]) -> str:
    title = normalize(record["title"])
    text = record["text"]
    if not THERMOGRAPHY.search(text):
        return "Sin mención explícita de termografía o imagen térmica/infrarroja"
    if not BREAST.search(text):
        return "Sin mención de mama"
    if ANIMAL_TITLE.search(title):
        return "Título referido a mama animal u otro contexto veterinario"
    return ""


def run() -> dict[str, object]:
    original = pd.read_excel(SOURCE_FINAL, dtype=str).fillna("")
    analyzed = pd.read_csv(SOURCE_ANALYZED, dtype=str, keep_default_na=False,
                           low_memory=False).fillna("")
    if len(original) != len(analyzed):
        raise ValueError("Los archivos bibliográfico y analizado no tienen las mismas filas.")
    records = prepare_records(analyzed.to_dict("records"))
    decisions = [exclusion_reason(record) for record in records]
    keep = [i for i, reason in enumerate(decisions) if not reason]
    drop = [i for i, reason in enumerate(decisions) if reason]
    if len(keep) + len(drop) != len(original):
        raise AssertionError("El cribado no concilia con el archivo de origen.")

    original.iloc[keep].to_csv(OUTPUT / "dataset_final_termografia.csv", index=False,
                               encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    selected_rows = original.iloc[keep].to_dict("records")
    headers = list(original.columns)
    title_col, abstract_col = guess_column(headers, "title"), guess_column(headers, "abstract")
    if not title_col or not abstract_col:
        raise ValueError("No se encontraron las columnas de título y resumen.")
    keyword_cols = [name for name in ("Author Keywords", "Keywords Plus") if name in headers]
    rescored = analyze_rows(selected_rows, title_col, abstract_col, keyword_cols)
    for item, source_index in zip(rescored, keep):
        item["id_articulo"] = analyzed.iloc[source_index]["id_articulo"]
        item["fila_origen"] = analyzed.iloc[source_index]["fila_origen"]
    (OUTPUT / "dataset_analizado.csv").write_bytes(csv_bytes(rescored))
    excluded = analyzed.iloc[drop].copy()
    excluded.insert(0, "motivo_exclusion_termografia", [decisions[i] for i in drop])
    excluded.to_csv(OUTPUT / "descartados_filtro_termografia.csv", index=False,
                    encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)
    manifest = {
        "registros_deduplicados": len(original),
        "conservados_termografia_mamaria": len(keep),
        "descartados": len(drop),
        "motivos_descarte": dict(Counter(decisions[i] for i in drop)),
        "criterio": "Mención de termografía/imagen térmica o infrarroja y mama en título, resumen o palabras clave; se apartan títulos veterinarios explícitos.",
        "puntajes_recalculados_sobre_filtrados": True,
        "nota": "Cribado textual reproducible; la elegibilidad de cada estudio requiere verificar el texto completo.",
    }
    (OUTPUT / "filtro_termografia_resumen.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
