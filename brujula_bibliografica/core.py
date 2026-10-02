"""Carga y puntuacion local para Brújula Bibliográfica.

La puntuación es una similitud léxica TF-IDF, no una probabilidad ni una
decisión de inclusión. Cada objetivo se evalúa de forma independiente.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


VERSION = "0.1.0"
METHOD = "tfidf_abstract_keywords_v1"
STOPWORDS = set("""
a al algo algunas algunos ante antes como con contra cual cuando de del desde donde
dos el ella ellas ellos en entre era es esa ese eso esta estas este estos fue han
hasta hay la las le les lo los mas me mi mis no nos o para pero por porque que se
segun ser si sin sobre son su sus tambien te tiene todas todos tu un una unas uno
unos y ya the a an and are as at be been by can for from has have in into is it
its of on or our this that their these those to was were which with using use
used study studies article paper method methods result results approach based
""".split())


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value.casefold())
    return "".join(char for char in value if not unicodedata.combining(char))


def tokens(value: str) -> list[str]:
    return [word for word in re.findall(r"[^\W_]+", normalize(value))
            if word not in STOPWORDS and (len(word) > 2 or word in {"ai", "ml", "dl"})]


def guess_column(headers: list[str], kind: str) -> str | None:
    aliases = {
        "abstract": ["abstract", "resumen", "summary"],
        "title": ["title", "article title", "titulo", "título"],
        "doi": ["doi"],
        "keywords": ["author keywords", "keywords", "palabras clave", "keywords plus", "index keywords"],
    }[kind]
    normalized = {header: normalize(header).strip() for header in headers}
    for alias in aliases:
        match = next((header for header, value in normalized.items() if value == normalize(alias)), None)
        if match:
            return match
    return next((header for header, value in normalized.items()
                 if any(normalize(alias) in value for alias in aliases)), None)


def load_table(name: str, content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    suffix = Path(name).suffix.casefold()
    if suffix == ".csv":
        decoded = None
        encodings = ("utf-16", "utf-8-sig", "cp1252") if content.startswith((b"\xff\xfe", b"\xfe\xff")) else ("utf-8-sig", "utf-16", "cp1252")
        for encoding in encodings:
            try:
                decoded = content.decode(encoding)
                break
            except UnicodeDecodeError:
                continue
        if decoded is None:
            raise ValueError("No se pudo leer la codificación del CSV.")
        # La primera fila determina el separador. Sniffer puede confundir los
        # puntos y coma dentro de resúmenes extensos con el delimitador real.
        def header_width(delimiter: str) -> int:
            try:
                return len(next(csv.reader(io.StringIO(decoded, newline=""),
                                           delimiter=delimiter)))
            except (StopIteration, csv.Error):
                return 0

        delimiter = max((",", ";", "\t"), key=header_width)
        reader = csv.DictReader(io.StringIO(decoded, newline=""), delimiter=delimiter)
        headers = list(reader.fieldnames or [])
        rows = [{header: text(row.get(header)) for header in headers} for row in reader]
    elif suffix == ".xlsx":
        try:
            import openpyxl
        except ImportError as exc:
            raise ValueError("Para abrir XLSX instala openpyxl.") from exc
        book = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = book.active
        iterator = sheet.iter_rows(values_only=True)
        headers = [text(value) for value in next(iterator, ())]
        rows = [{header: text(value) for header, value in zip(headers, values)}
                for values in iterator if any(value is not None for value in values)]
        book.close()
    else:
        raise ValueError("Formato no admitido. Usa CSV o XLSX.")
    if not headers or len(headers) != len(set(headers)) or any(not h for h in headers):
        raise ValueError("El archivo debe tener encabezados únicos y no vacíos.")
    if not rows:
        raise ValueError("El archivo no contiene registros.")
    return headers, rows


def _vector(words: list[str], idf: dict[str, float]) -> dict[str, float]:
    counts = Counter(words)
    return {word: (1 + math.log(count)) * idf[word]
            for word, count in counts.items() if word in idf}


def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
    if not left or not right:
        return 0.0
    dot = sum(weight * right.get(word, 0.0) for word, weight in left.items())
    norm_left = math.sqrt(sum(weight * weight for weight in left.values()))
    norm_right = math.sqrt(sum(weight * weight for weight in right.values()))
    return dot / (norm_left * norm_right) if norm_left and norm_right else 0.0


def recommend_local(
    rows: list[dict[str, str]], abstract_column: str, keyword_columns: list[str],
    objectives: list[str], title_column: str | None = None,
) -> list[dict[str, object]]:
    if len(objectives) != 4 or any(not objective.strip() for objective in objectives):
        raise ValueError("Escribe los cuatro objetivos antes de analizar.")
    if any(abstract_column not in row for row in rows):
        raise ValueError(f"No existe la columna de resumen: {abstract_column}")
    for column in keyword_columns:
        if any(column not in row for row in rows):
            raise ValueError(f"No existe la columna de palabras clave: {column}")

    documents = []
    for row in rows:
        abstract_words = tokens(row.get(abstract_column, ""))
        keyword_words = [word for column in keyword_columns
                         for word in tokens(row.get(column, ""))]
        documents.append(abstract_words + keyword_words * 2)
    objective_words = [tokens(objective) for objective in objectives]
    frequencies = Counter(word for words in documents for word in set(words))
    n = len(documents)
    idf = {word: math.log((n + 1) / (count + 1)) + 1
           for word, count in frequencies.items()}
    doc_vectors = [_vector(words, idf) for words in documents]
    objective_vectors = [_vector(words, idf) for words in objective_words]

    output = []
    for number, (source, words, doc_vector) in enumerate(zip(rows, documents, doc_vectors), 1):
        result: dict[str, object] = dict(source)
        result["fila_origen"] = number
        result["texto_disponible"] = "Sí" if words else "No"
        scores = []
        for i, (objective_tokens, objective_vector) in enumerate(
            zip(objective_words, objective_vectors), 1
        ):
            score = round(100 * _cosine(doc_vector, objective_vector), 2)
            scores.append(score)
            overlap = set(words) & set(objective_tokens)
            matched = sorted(overlap, key=lambda word: (-idf.get(word, 0), word))[:10]
            result[f"afinidad_objetivo_{i}"] = score
            result[f"terminos_objetivo_{i}"] = ", ".join(matched)
        best = max(range(4), key=lambda i: scores[i]) if max(scores) > 0 else None
        result["objetivo_mayor_afinidad"] = f"Objetivo {best + 1}" if best is not None else ""
        result["decision_revisor"] = "Pendiente"
        result["nota_revisor"] = ""
        output.append(result)
    return output


def assign_recommendations(results: list[dict[str, object]]) -> None:
    """Add a relative review priority without making inclusion decisions."""
    scores = sorted(
        max(float(row[f"afinidad_objetivo_{i}"]) for i in range(1, 5))
        for row in results if row["texto_disponible"] == "Sí"
    )
    cutoff = scores[int(0.75 * (len(scores) - 1))] if scores else 0.0
    for row in results:
        best = max(float(row[f"afinidad_objetivo_{i}"]) for i in range(1, 5))
        row["afinidad_maxima"] = best
        if row["texto_disponible"] == "No":
            row["veredicto"] = "Sin texto para evaluar"
        elif best == 0:
            row["veredicto"] = "Sin coincidencias textuales"
        elif best >= cutoff:
            row["veredicto"] = "Revisar primero"
        else:
            row["veredicto"] = "Revisar"


def csv_bytes(rows: list[dict[str, object]]) -> bytes:
    if not rows:
        raise ValueError("No hay resultados que exportar.")
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]), extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return ("\ufeff" + stream.getvalue()).encode("utf-8")


def evidence_record(source_name: str, source_bytes: bytes, row_count: int,
                    abstract_column: str, keyword_columns: list[str],
                    objectives: list[str], method: str = METHOD,
                    extra: dict[str, object] | None = None) -> dict[str, object]:
    return {
        "app": "Brújula Bibliográfica",
        "version": VERSION,
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "archivo_entrada": Path(source_name).name,
        "sha256_entrada": hashlib.sha256(source_bytes).hexdigest(),
        "registros_entrada": row_count,
        "columna_resumen": abstract_column,
        "columnas_palabras_clave": keyword_columns,
        "objetivos": objectives,
        "metodo": method,
        "detalle": extra or {},
    }


def save_run(directory: Path, results: list[dict[str, object]],
             evidence: dict[str, object]) -> tuple[Path, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    csv_path = directory / "recomendaciones.csv"
    json_path = directory / "evidencia_ejecucion.json"
    csv_path.write_bytes(csv_bytes(results))
    json_path.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, json_path
