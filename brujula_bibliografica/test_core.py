import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from api import analyze_one, parse_response
from analisis_local import analyze_rows
from analytics import keyword_network, overview, reason_group
from keyword_graph import keyword_graph_svg
from filtrar_termografia import exclusion_reason
from flow_graph import flow_svg
from resources import article_resource
from core import assign_recommendations, csv_bytes, evidence_record, guess_column, load_table, recommend_local


class RecommenderTests(unittest.TestCase):
    def test_article_resource_prefers_article_link_not_journal_issn(self):
        row = {"DOI": "10.1234/example", "Link": "https://www.scopus.com/test",
               "ISSN": "1234-5678", "Title": "Thermal breast study"}
        self.assertEqual(article_resource(row), "https://doi.org/10.1234/example")
        row["DOI"] = ""
        self.assertEqual(article_resource(row), "https://www.scopus.com/test")
        row["Link"] = ""
        self.assertIn("scholar.google.com/scholar?q=Thermal%20breast%20study",
                      article_resource(row))

    def test_thermography_screen_rejects_other_ir_and_animal_breast(self):
        self.assertEqual(exclusion_reason({"title": "Breast thermal imaging",
                                           "text": "breast thermal imaging and mammography"}), "")
        self.assertIn("Sin mención explícita", exclusion_reason({
            "title": "Breast infrared spectroscopy", "text": "breast infrared spectroscopy"}))
        self.assertIn("mama animal", exclusion_reason({
            "title": "Dairy cow mastitis from thermal images",
            "text": "dairy cow mammary thermal images"}))
        self.assertIn("Sin mención de mama", exclusion_reason({
            "title": "Thyroid thermography", "text": "thyroid thermography"}))

    def test_record_flow_shows_screening_step(self):
        summary = {"scopus": 629, "wos": 264, "unified_rows": 893,
                   "pairs_fused": 227, "deduplicated_rows": 666,
                   "screened_out": 65, "final_rows": 601}
        graphic = flow_svg(summary)
        self.assertIn("−65", graphic)
        self.assertIn("601", graphic)
        self.assertIn("termografía", graphic)

    def test_keyword_links_and_reason_group_follow_article_rows(self):
        rows = [
            {"Author Keywords": "thermography; breast cancer; CNN",
             "motivo_recomendacion": "Tema central. Mayor afinidad calculada: O3."},
            {"Author Keywords": "breast cancer; thermography; SVM",
             "motivo_recomendacion": "Tema central. Mayor afinidad calculada: O1."},
            {"Author Keywords": "thermography; MRI",
             "motivo_recomendacion": "Otro motivo."},
        ]
        network = keyword_network(rows)
        self.assertIn(("breast cancer", "thermography", 2), network["edges"])
        self.assertEqual(reason_group(rows[0]), reason_group(rows[1]))
        self.assertEqual(sum(reason_group(row) == "Tema central." for row in rows), 2)
        self.assertIn("breast cancer", keyword_graph_svg(network))

    def test_objective_overview_uses_only_selected_abstracts(self):
        rows = [
            {"id_articulo": "BB-0001", "titulo_analisis": "Breast thermography with CNN",
             "Abstract": "Using the public dataset DMR-IR and data augmentation, CNN achieved accuracy of 95.5%.",
             "Author Keywords": "thermography; breast cancer", "nivel_recomendacion": "Alta",
             "motivo_recomendacion": "Afinidad temática. Mayor afinidad calculada: O3."},
            {"id_articulo": "BB-0002", "titulo_analisis": "Breast thermography with SVM",
             "Abstract": "A private dataset was analyzed with SVM. AUC score of 0.91.",
             "Author Keywords": "classification", "nivel_recomendacion": "Media",
             "motivo_recomendacion": "Afinidad temática. Mayor afinidad calculada: O3."},
        ]
        all_results = overview(rows)
        self.assertEqual(len(all_results["datasets"]["DMR / DMR-IR"]), 1)
        self.assertEqual(len(all_results["access"]["Solo mención pública"]), 1)
        self.assertEqual(len(all_results["access"]["Solo mención restringida"]), 1)
        self.assertEqual(len(all_results["performance"]), 2)
        self.assertEqual(all_results["reasons"], [("Afinidad temática.", 2)])
        high_only = overview(rows[:1])
        self.assertEqual(len(high_only["models"]["SVM"]), 0)
        self.assertEqual(len(high_only["models"]["CNN"]), 1)
        self.assertEqual(len(high_only["performance"]), 1)

    def test_csv_separator_ignores_semicolons_inside_abstract(self):
        data = 'Title,Abstract,Keywords\r\nOne,"thermal; breast; cancer",classification\r\n'
        headers, rows = load_table("articulos.csv", data.encode("utf-8"))
        self.assertEqual(headers, ["Title", "Abstract", "Keywords"])
        self.assertEqual(rows[0]["Abstract"], "thermal; breast; cancer")

    def test_local_analysis_keeps_original_cells_and_all_rows(self):
        rows = [
            {"Title": "Breast cancer classification in thermal images",
             "Abstract": "Deep learning classifies breast thermograms for cancer detection.",
             "Keywords": "infrared; classification", "DOI": "10.1/a"},
            {"Title": "Unrelated study", "Abstract": "", "Keywords": "", "DOI": "10.1/b"},
        ]
        result = analyze_rows(rows, "Title", "Abstract", ["Keywords"])
        self.assertEqual(len(result), 2)
        self.assertEqual([item["id_articulo"] for item in result], ["BB-0001", "BB-0002"])
        self.assertEqual(result[0]["DOI"], "10.1/a")
        self.assertEqual(result[1]["DOI"], "10.1/b")
        self.assertEqual(result[1]["nivel_recomendacion"], "Sin resumen")

    def test_csv_multiline_and_flexible_columns(self):
        data = '\ufeff"Título","Resumen","Palabras clave"\r\n"Uno","Primera línea\nsegunda línea","imagen; IA"\r\n'
        headers, rows = load_table("articulos.csv", data.encode("utf-8"))
        self.assertEqual(len(rows), 1)
        self.assertIn("segunda línea", rows[0]["Resumen"])
        self.assertEqual(guess_column(headers, "abstract"), "Resumen")
        self.assertEqual(guess_column(headers, "keywords"), "Palabras clave")

    def test_all_four_objectives_and_empty_text(self):
        rows = [
            {"Title": "A", "Abstract": "thermal image neural network", "Keywords": "classification"},
            {"Title": "B", "Abstract": "", "Keywords": ""},
        ]
        objectives = ["thermal image classification", "preprocessing noise",
                      "neural network models", "clinical validation"]
        ranked = recommend_local(rows, "Abstract", ["Keywords"], objectives, "Title")
        assign_recommendations(ranked)
        self.assertEqual(len(ranked), 2)
        self.assertGreater(ranked[0]["afinidad_objetivo_1"], 0)
        self.assertGreater(ranked[0]["afinidad_objetivo_3"], 0)
        self.assertEqual(ranked[1]["texto_disponible"], "No")
        self.assertEqual(ranked[1]["afinidad_objetivo_1"], 0)
        self.assertEqual(len([key for key in ranked[0] if key.startswith("afinidad_objetivo_")]), 4)
        self.assertEqual(ranked[1]["veredicto"], "Sin texto para evaluar")
        self.assertEqual(ranked[0]["veredicto"], "Revisar primero")
        exported = csv_bytes(ranked).decode("utf-8-sig")
        self.assertIn("decision_revisor", exported)

    def test_evidence_has_source_hash(self):
        source = b"example"
        item = evidence_record("papers.csv", source, 2, "Abstract", [], ["a", "b", "c", "d"])
        self.assertEqual(item["sha256_entrada"], hashlib.sha256(source).hexdigest())
        self.assertEqual(item["registros_entrada"], 2)

    def test_structured_api_response_validation(self):
        result = {"recomendacion": "Sí", "motivo_general": "Aborda termografía mamaria."}
        result.update({f"objetivo_{i}": {"afinidad": i * 20, "motivo": "Texto"}
                       for i in range(1, 5)})
        payload = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(result)}]}],
            "usage": {"input_tokens": 20}}
        parsed, usage = parse_response(payload)
        self.assertEqual(parsed["objetivo_4"]["afinidad"], 80)
        self.assertEqual(usage["input_tokens"], 20)
        result["objetivo_1"]["afinidad"] = 120
        payload["output"][0]["content"][0]["text"] = json.dumps(result)
        with self.assertRaises(ValueError):
            parse_response(payload)

    def test_api_request_is_structured_and_does_not_store_response(self):
        result = {"recomendacion": "No", "motivo_general": "Otro órgano."}
        result.update({f"objetivo_{i}": {"afinidad": 5, "motivo": "Sin relación"}
                       for i in range(1, 5)})
        response = {"output": [{"type": "message", "content": [
            {"type": "output_text", "text": json.dumps(result)}]}]}
        captured = {}

        def fake_urlopen(request, timeout):
            captured["url"] = request.full_url
            captured["body"] = json.loads(request.data)
            return io.BytesIO(json.dumps(response).encode("utf-8"))

        with patch("urllib.request.urlopen", side_effect=fake_urlopen):
            parsed, _ = analyze_one("test-key", "gpt-5-mini", "Título", "Resumen",
                                    "palabras", "objetivo general",
                                    ["uno", "dos", "tres", "cuatro"])
        self.assertEqual(parsed["recomendacion"], "No")
        self.assertTrue(captured["url"].endswith("/v1/responses"))
        self.assertFalse(captured["body"]["store"])
        self.assertEqual(captured["body"]["text"]["format"]["type"], "json_schema")
        self.assertIn("objetivo general", captured["body"]["input"])


if __name__ == "__main__":
    unittest.main()
