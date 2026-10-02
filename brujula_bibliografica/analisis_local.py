"""Genera una matriz de prioridad de revisión sin usar una API de IA.

El método combina señales explícitas del tema con similitud TF-IDF por objetivo.
Los puntajes sirven para priorizar lectura; no son probabilidades ni decisiones
de inclusión. La salida conserva todas las filas y columnas originales.
"""

from __future__ import annotations

import argparse
import math
import re
from collections import Counter
from pathlib import Path

from core import csv_bytes, guess_column, load_table, normalize, recommend_local


PROJECT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT / "outputs" / "dataset_scopus_wos" / "dataset_final.xlsx"
DEFAULT_OUTPUT = PROJECT / "outputs" / "dataset_scopus_wos" / "dataset_analizado.csv"
VERSION = "prioridad_tfidf_tema_v3"
CONTEXT = "breast cancer classification using thermographic infrared images"
OBJECTIVES = [
    "To characterize the datasets used in eligible studies, quantify their frequency of use, and document access conditions, with particular attention to publicly accessible resources.",
    "To categorize image preparation and data augmentation techniques according to their purpose and frequency of use within classification workflows.",
    "To identify and categorize the machine learning and deep learning models used for classification, including their training approaches and frequency of use.",
    "To summarize evaluation metrics, validation procedures, reported performance, and methodological limitations that affect interpretation of the results.",
]
TOPIC_PATTERNS = {
    "mama": r"\b(breast|mammary|mamari\w*|mama|seno\w*)\b",
    "cáncer": r"\b(cancer|tumou?r\w*|neoplasm\w*|carcinoma\w*|malignan\w*|lesion\w*)\b",
    "termografía": r"\b(thermog\w*|thermogram\w*|thermal|infrared|infrarro\w*|termograf\w*|termogram\w*)\b",
    "IA/modelos": r"\b(artificial intelligence|machine learning|deep learning|neural|cnn|svm|classifier\w*|classification|clasific\w*|inteligencia artificial|aprendizaje automatico|transfer learning)\b",
    "clasificación/detección": r"\b(classif\w*|detect\w*|diagnos\w*|screen\w*|predict\w*|identif\w*|segment\w*|clasific\w*|detecc\w*|diagnost\w*)\b",
}
TOPIC_WEIGHTS = {"mama": 25, "cáncer": 15, "termografía": 30,
                 "IA/modelos": 15, "clasificación/detección": 15}


def percentile95(values: list[float]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 1.0
    position = .95 * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return max(1.0, ordered[low] + (ordered[high] - ordered[low]) * (position - low))


def topic_signals(title: str, abstract: str, keywords: str) -> dict[str, bool]:
    combined = normalize(" ".join([title, abstract, keywords]))
    return {name: bool(re.search(pattern, combined))
            for name, pattern in TOPIC_PATTERNS.items()}


def analyze_rows(rows: list[dict[str, str]], title_col: str, abstract_col: str,
                 keyword_cols: list[str], objectives: list[str] | None = None) -> list[dict[str, object]]:
    selected_objectives = objectives if objectives is not None else OBJECTIVES
    contextual = [CONTEXT + ". " + objective for objective in selected_objectives]
    raw = recommend_local(rows, abstract_col, keyword_cols, contextual, title_col)
    scales = {
        i: percentile95([float(item[f"afinidad_objetivo_{i}"]) for item in raw])
        for i in range(1, 5)
    }
    output = []
    for number, (source, item) in enumerate(zip(rows, raw), 1):
        keywords = " ".join(source.get(col, "") for col in keyword_cols)
        title = source.get(title_col, "")
        abstract = source.get(abstract_col, "")
        signals = topic_signals(title,
                                abstract, keywords)
        title_signals = topic_signals(title, "", "")
        abstract_normalized = normalize(abstract)
        breast_mentions = len(re.findall(TOPIC_PATTERNS["mama"], abstract_normalized))
        thermal_mentions = len(re.findall(TOPIC_PATTERNS["termografía"], abstract_normalized))
        coverage = sum(TOPIC_WEIGHTS[name] for name, found in signals.items() if found)
        valid_text = bool(abstract.strip())
        scores = [
            round(min(100.0, float(item[f"afinidad_objetivo_{i}"]) / scales[i] * 100)
                  * coverage / 100, 1)
            for i in range(1, 5)
        ] if valid_text else [0.0] * 4
        best = max(range(4), key=lambda index: scores[index]) if max(scores) else None
        general = round(.65 * coverage + .35 * max(scores), 1) if valid_text else 0.0
        if not (signals["mama"] and signals["termografía"]):
            general = min(general, 49.0)
        if not signals["cáncer"]:
            general = min(general, 49.0)
        if not (signals["IA/modelos"] and signals["clasificación/detección"]):
            general = min(general, 74.0)
        title_focus = (
            (title_signals["mama"] and title_signals["termografía"])
            or (title_signals["mama"] and thermal_mentions >= 2)
            or (title_signals["termografía"] and breast_mentions >= 2)
        )
        if not title_focus:
            general = min(general, 74.0)
        if not title_signals["mama"]:
            general = min(general, 74.0)
        if not (title_signals["mama"] or title_signals["cáncer"]):
            general = min(general, 49.0)
        if not (title_signals["mama"] or title_signals["termografía"]):
            if breast_mentions < 2 or thermal_mentions < 2:
                general = min(general, 49.0)
        title_normalized = normalize(title)
        retracted = bool(re.search(r"\bretract\w*\b", title_normalized))
        review_article = bool(re.search(r"\b(review|survey|bibliometric|meta.analysis)\b",
                                        title_normalized))
        if retracted:
            general = min(general, 20.0)
        elif review_article:
            general = min(general, 49.0)
        objective_ceiling = 100.0
        if not title_focus or not title_signals["mama"]:
            objective_ceiling = min(objective_ceiling, 74.0)
        if not (title_signals["mama"] or title_signals["cáncer"]):
            objective_ceiling = min(objective_ceiling, 49.0)
        if review_article:
            objective_ceiling = min(objective_ceiling, 49.0)
        if retracted:
            objective_ceiling = min(objective_ceiling, 20.0)
        scores = [min(score, objective_ceiling) for score in scores]
        best = max(range(4), key=lambda index: scores[index]) if max(scores) else None
        if not valid_text:
            level, stars = "Sin resumen", "—"
            reason = "No hay resumen en la columna seleccionada; requiere revisión manual."
        elif retracted:
            level, stars = "Baja", "★"
            reason = "El título indica que el artículo fue retractado; comprobar su estado editorial."
        elif review_article:
            level, stars = "Baja", "★"
            reason = "El título indica un artículo de revisión; puede servir como contexto, pero no como estudio primario."
        elif (general >= 82 and title_focus and title_signals["mama"]
              and signals["mama"] and signals["termografía"]
              and signals["IA/modelos"] and signals["clasificación/detección"]):
            level, stars = "Alta", "★★★"
            reason = "Coinciden los términos del tema central y hay afinidad con los objetivos."
        elif general >= 60 and signals["mama"] and signals["termografía"]:
            level, stars = "Media", "★★"
            reason = "Se detectan mama y termografía; conviene comprobar el alcance en el texto completo."
        else:
            level, stars = "Baja", "★"
            missing = [name for name in ("mama", "termografía", "IA/modelos") if not signals[name]]
            if missing:
                reason = ("No se detectan en título, resumen o palabras clave: "
                          + ", ".join(missing) + ".")
            elif not title_signals["mama"] and not title_signals["cáncer"]:
                reason = "El título no identifica cáncer de mama como tema central; la mención en el resumen puede ser secundaria."
            elif not signals["cáncer"]:
                reason = "No se detecta una relación explícita con cáncer en los campos analizados."
            else:
                reason = "Afinidad temática o textual limitada según la regla de priorización."
        if best is not None and valid_text:
            reason += f" Mayor afinidad calculada: O{best + 1}."
        result: dict[str, object] = {
            "id_articulo": f"BB-{number:04d}",
            "fila_origen": number,
            "titulo_analisis": source.get(title_col, ""),
            "puntaje_general": general,
            "nivel_recomendacion": level,
            "estrellas": stars,
            "motivo_recomendacion": reason,
            "objetivo_mayor_afinidad": f"O{best + 1}" if best is not None else "",
            "afinidad_O1": scores[0],
            "afinidad_O2": scores[1],
            "afinidad_O3": scores[2],
            "afinidad_O4": scores[3],
            "senal_mama": "Sí" if signals["mama"] else "No",
            "senal_cancer": "Sí" if signals["cáncer"] else "No",
            "senal_termografia": "Sí" if signals["termografía"] else "No",
            "senal_ia_modelos": "Sí" if signals["IA/modelos"] else "No",
            "senal_clasificacion": "Sí" if signals["clasificación/detección"] else "No",
            "terminos_O1": item["terminos_objetivo_1"],
            "terminos_O2": item["terminos_objetivo_2"],
            "terminos_O3": item["terminos_objetivo_3"],
            "terminos_O4": item["terminos_objetivo_4"],
            "metodo_recomendacion": VERSION,
        }
        result.update(source)
        output.append(result)
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    headers, rows = load_table(args.input.name, args.input.read_bytes())
    title_col, abstract_col = guess_column(headers, "title"), guess_column(headers, "abstract")
    if not title_col or not abstract_col:
        raise SystemExit("El archivo necesita columnas de título y resumen.")
    keyword_cols = [name for name in ("Author Keywords", "Keywords Plus") if name in headers]
    results = analyze_rows(rows, title_col, abstract_col, keyword_cols)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(csv_bytes(results))
    print(f"Archivo: {args.output}")
    print(f"Filas: {len(results)}; columnas originales: {len(headers)}; columnas finales: {len(results[0])}")
    print("Niveles:", dict(Counter(item["nivel_recomendacion"] for item in results)))


if __name__ == "__main__":
    main()
