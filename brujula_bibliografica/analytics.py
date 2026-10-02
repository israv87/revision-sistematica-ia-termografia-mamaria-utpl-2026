"""Conteos exploratorios con trazabilidad al texto bibliográfico.

Cada conteo representa artículos que mencionan un término en título, resumen
o palabras clave. Una mención no demuestra que el método se haya utilizado.
"""

from __future__ import annotations

import re
from collections import Counter
from itertools import combinations

from core import guess_column, normalize
from resources import article_resource


ANALYTICS_VERSION = "objetivos_texto_v4_recursos"


DATA_TYPES = {
    "Termografía / infrarrojo": r"\b(thermog\w*|thermogram\w*|thermal imag\w*|infrared|termograf\w*|infrarro\w*)\b",
    "Termografía dinámica": r"\b(dynamic thermog\w*|dynamic thermal|dynamic infrared|termografia dinamica)\b",
    "Datos clínicos": r"\b(clinical data|clinical variable\w*|patient data|patient record\w*)\b",
    "Mamografía": r"\b(mammograph\w*|mammogram\w*|mamograf\w*)\b",
    "Ultrasonido": r"\b(ultrasound|ultrasonograph\w*|ecograf\w*)\b",
    "Resonancia magnética": r"\b(magnetic resonance|\bmri\b|resonancia magnetica)\b",
}
DATASETS = {
    "DMR / DMR-IR": r"\b(dmr(?:-ir)?|database (?:for )?mastology research|mastology research with (?:the )?infrared image)\b",
    "INbreast": r"\binbreast\b",
    "Wisconsin Breast Cancer": r"\b(wisconsin breast cancer|wdbc)\b",
    "MIAS": r"\bmias\b",
    "DBT-TU-JU": r"\bdbt-tu-ju\b",
}
ACCESS_PUBLIC = r"\b(publicly available|public(?:ly)? accessible|public dataset\w*|open dataset\w*|open.access dataset\w*|public database\w*)\b"
ACCESS_RESTRICTED = r"\b(private dataset\w*|proprietary dataset\w*|restricted.access|non.public dataset\w*|in.house dataset\w*)\b"
PREPARATION = {
    "Preprocesamiento": r"\b(preprocess\w*|pre.process\w*|preproces\w*)\b",
    "Normalización": r"\b(normaliz\w*|normalis\w*)\b",
    "Mejora de contraste": r"\b(contrast enhanc\w*|\bclahe\b|histogram equaliz\w*)\b",
    "Reducción de ruido": r"\b(denois\w*|noise reduc\w*|noise remov\w*|filtrado de ruido)\b",
    "Segmentación / ROI": r"\b(segment\w*|region of interest|\broi\b)\b",
    "Aumento de datos": r"\b(data augmentation|image augmentation|augment\w*|rotat\w*|flipp\w*)\b",
    "Imágenes sintéticas / GAN": r"\b(synthetic imag\w*|generative adversarial|\bgan\b|\bgans\b)\b",
    "Extracción / selección de rasgos": r"\b(feature extract\w*|feature select\w*|texture feature\w*|radiomic\w*)\b",
}
MODELS = {
    "CNN": r"\b(cnn\w*|convolutional neural network\w*|convolutional network\w*)\b",
    "SVM": r"\b(svm|support vector machine\w*)\b",
    "Random Forest": r"\b(random forest\w*|\brf\b)\b",
    "ResNet": r"\bresnet\w*\b",
    "VGG": r"\bvgg\d*\b",
    "U-Net": r"\b(u.net|unet)\b",
    "Transformer / ViT": r"\b(transformer\w*|vision transformer\w*|\bvit\b)\b",
    "EfficientNet": r"\befficientnet\w*\b",
    "XGBoost": r"\bxgboost\b",
    "KNN": r"\b(k.nearest neighbo\w*|\bknn\b)\b",
    "YOLO": r"\byolo\w*\b",
    "Mask R-CNN": r"\bmask r.cnn\b",
    "Autoencoder": r"\b(autoencoder\w*|auto.encoder\w*)\b",
    "Capsule Network": r"\b(capsule network\w*|capsnet\w*)\b",
    "Extreme Learning Machine": r"\b(extreme learning machine|\belm\b)\b",
}
CLASSIFICATION = {
    "Binaria": r"\b(binary classif\w*|two.class classif\w*|2.class classif\w*|normal (?:and|vs\.?|versus) abnormal|benign (?:and|vs\.?|versus) malignant)\b",
    "Multiclase": r"\b(multi.class|multiclass|three.class|3.class|four.class|4.class|multiple classes)\b",
    "Normal / anormal": r"\b(normal (?:and|vs\.?|versus) abnormal|healthy (?:and|vs\.?|versus) (?:sick|cancer\w*))\b",
    "Benigno / maligno": r"\b(benign (?:and|vs\.?|versus) malignant|benign.{0,30}malignant)\b",
}
TOOLS = {
    "Python": r"\bpython\b",
    "TensorFlow": r"\btensorflow\b",
    "PyTorch": r"\bpytorch\b",
    "Keras": r"\bkeras\b",
    "MATLAB": r"\bmatlab\b",
    "scikit-learn": r"\bscikit.learn\b",
}
METRICS = {
    "Exactitud (accuracy)": r"\b(accuracy|exactitud)\b",
    "Sensibilidad": r"\b(sensitivity|sensibilidad|true positive rate)\b",
    "Especificidad": r"\b(specificity|especificidad|true negative rate)\b",
    "Precisión": r"\b(precision|positive predictive value)\b",
    "Recall": r"\brecall\b",
    "F1": r"\b(f1.score|f1 score|f1)\b",
    "AUC / ROC": r"\b(auc|area under (?:the )?curve|roc.auc|roc curve)\b",
    "Dice": r"\b(dice coefficient|dice score|dice similarity|\bdsc\b)\b",
    "IoU": r"\b(intersection over union|\biou\b)\b",
}
VALIDATION = {
    "Validación cruzada": r"\b(cross.validation|cross validation|k.fold|leave.one.out)\b",
    "Partición entrenamiento/prueba": r"\b(train.test split|training and test\w* set\w*|training.test split|hold.out|held.out)\b",
    "Validación externa": r"\b(external validation|independent validation|external test set|independent test set)\b",
}
LIMITATIONS = {
    "Muestra pequeña / datos limitados": r"\b(small sample|limited sample|small dataset|limited dataset|data scarcity|limited (?:number|amount) of (?:images|data|patients))\b",
    "Desequilibrio de clases": r"\b(class imbalance|imbalanced data|unbalanced data|data imbalance)\b",
    "Sobreajuste": r"\b(overfitt\w*|over.fitt\w*)\b",
    "Generalización limitada": r"\b(limited generaliz\w*|limited generalis\w*|generalizability (?:is )?limited|generalisation (?:is )?limited)\b",
    "Falta de validación externa": r"\b(lack of external validation|no external validation|without external validation)\b",
}


def _first(row: dict[str, object], candidates: list[str]) -> str:
    return next((str(row[name]).strip() for name in candidates if name in row and row[name]), "")


def prepare_records(rows: list[dict[str, object]]) -> list[dict[str, str]]:
    """Use original metadata, never generated recommendation reasons, as evidence."""
    if not rows:
        return []
    headers = list(rows[0])
    abstract_guess = guess_column(headers, "abstract")
    keywords = [name for name in ("Author Keywords", "Keywords Plus", "Keywords", "Palabras clave")
                if name in headers]
    if not keywords:
        keyword_guess = guess_column(headers, "keywords")
        keywords = [keyword_guess] if keyword_guess else []
    records = []
    for row in rows:
        title = _first(row, ["titulo_analisis", "Title", "Título", "Titulo"])
        abstract = _first(row, ["Abstract", "Abstract_WoS", "Resumen", "resumen"]
                          + ([abstract_guess] if abstract_guess else []))
        keyword_text = " ".join(str(row.get(name, "") or "") for name in keywords)
        original = " ".join([title, abstract, keyword_text])
        records.append({
            "id": str(row.get("id_articulo", "")), "title": title,
            "abstract": abstract, "text": normalize(original),
            "resource": article_resource(row),
        })
    return records


def matches(records: list[dict[str, str]], patterns: dict[str, str]) -> dict[str, list[int]]:
    compiled = {name: re.compile(pattern) for name, pattern in patterns.items()}
    return {name: [i for i, row in enumerate(records) if regex.search(row["text"])]
            for name, regex in compiled.items()}


def access_mentions(records: list[dict[str, str]]) -> dict[str, list[int]]:
    public, restricted = re.compile(ACCESS_PUBLIC), re.compile(ACCESS_RESTRICTED)
    output = {"Solo mención pública": [], "Solo mención restringida": [],
              "Ambas menciones": [], "No indicado": []}
    for i, record in enumerate(records):
        yes_public, yes_restricted = bool(public.search(record["text"])), bool(restricted.search(record["text"]))
        label = ("Ambas menciones" if yes_public and yes_restricted else
                 "Solo mención pública" if yes_public else
                 "Solo mención restringida" if yes_restricted else "No indicado")
        output[label].append(i)
    return output


def performance_values(records: list[dict[str, str]]) -> list[dict[str, str]]:
    """Extract explicit percentages or AUC decimals adjacent to a metric."""
    names = {
        "Exactitud": r"accuracy|exactitud",
        "Sensibilidad": r"sensitivity|sensibilidad",
        "Especificidad": r"specificity|especificidad",
        "Precisión": r"precision",
        "F1": r"f1(?:.score| score)?",
        "AUC": r"auc(?:.roc)?",
    }
    found = []
    for record in records:
        abstract = record["abstract"]
        for label, alias in names.items():
            expression = re.compile(
                rf"\b(?:{alias})\b(?:\s+(?:score|of|was|is|at|reached|achieved))?\s*(?:=|:|of|was|is|at)?\s*(\d{{1,3}}(?:[.,]\d+)?\s*%)",
                re.I,
            )
            match = expression.search(abstract)
            if not match:
                match = re.search(rf"(\d{{1,3}}(?:[.,]\d+)?\s*%)\s+(?:for\s+|in\s+)?(?:the\s+)?\b(?:{alias})\b",
                                  abstract, re.I)
            if not match and label == "AUC":
                match = re.search(r"\bauc(?:.roc)?\b(?:\s+(?:score|of|was|is|at))?\s*(?:=|:|of|was|is|at)?\s*(0[.,]\d+)\b",
                                  abstract, re.I)
            if match:
                start, end = max(0, match.start() - 45), min(len(abstract), match.end() + 45)
                found.append({"Recurso": record["resource"], "Título": record["title"],
                              "Métrica": label, "Valor citado": match.group(1).replace(" ", ""),
                              "Extracto del resumen": abstract[start:end].replace("\n", " ")})
    return found


def _keyword_sets(rows: list[dict[str, object]]) -> list[set[str]]:
    if not rows:
        return []
    columns = [name for name in ("Author Keywords", "Keywords Plus", "Keywords", "Palabras clave")
               if name in rows[0]]
    article_terms = []
    for row in rows:
        terms = set()
        for column in columns:
            for candidate in re.split(r"[;|]", str(row.get(column, "") or "")):
                term = normalize(candidate).strip(" .,\t\n")
                if len(term) > 2:
                    terms.add(term)
        article_terms.append(terms)
    return article_terms


def keyword_counts(rows: list[dict[str, object]]) -> list[tuple[str, int]]:
    counts: Counter[str] = Counter()
    for terms in _keyword_sets(rows):
        counts.update(terms)
    return counts.most_common(30)


def keyword_network(rows: list[dict[str, object]], node_limit: int = 14,
                    edge_limit: int = 30) -> dict[str, object]:
    """Connect keywords that occur together in the same bibliographic record."""
    articles = _keyword_sets(rows)
    counts: Counter[str] = Counter()
    for terms in articles:
        counts.update(terms)
    nodes = counts.most_common(node_limit)
    selected = {term for term, _ in nodes}
    pairs: Counter[tuple[str, str]] = Counter()
    for terms in articles:
        pairs.update(combinations(sorted(terms & selected), 2))
    edges = [(left, right, count) for (left, right), count in pairs.most_common(edge_limit)
             if count >= 2]
    return {"nodes": nodes, "edges": edges}


def reason_group(row: dict[str, object]) -> str:
    return str(row.get("motivo_recomendacion", "") or "").split(" Mayor afinidad calculada:")[0].strip()


def reason_counts(rows: list[dict[str, object]]) -> list[tuple[str, int]]:
    counts = Counter(reason_group(row) for row in rows)
    counts.pop("", None)
    return counts.most_common()


def overview(rows: list[dict[str, object]]) -> dict[str, object]:
    records = prepare_records(rows)
    return {
        "records": records,
        "keywords": keyword_counts(rows),
        "keyword_network": keyword_network(rows),
        "reasons": reason_counts(rows),
        "data_types": matches(records, DATA_TYPES),
        "datasets": matches(records, DATASETS),
        "access": access_mentions(records),
        "preparation": matches(records, PREPARATION),
        "models": matches(records, MODELS),
        "classification": matches(records, CLASSIFICATION),
        "tools": matches(records, TOOLS),
        "metrics": matches(records, METRICS),
        "validation": matches(records, VALIDATION),
        "limitations": matches(records, LIMITATIONS),
        "performance": performance_values(records),
    }
