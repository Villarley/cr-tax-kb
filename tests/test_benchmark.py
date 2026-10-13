import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from benchmark import agent, retrieval  # noqa: E402


class RetrievalBenchmarkTest(unittest.TestCase):
    RECALL3_MIN = 0.74
    MRR_MIN = 0.58

    @classmethod
    def setUpClass(cls):
        from cr_tax_kb.search import KnowledgeBase

        cls.kb = KnowledgeBase()
        cls._has_norms = bool(cls.kb.units)

    def test_retrieval_recall_floor(self):
        if not self._has_norms:
            self.skipTest("laws/ has no ingested norms")
        data = retrieval.run(k_latency_reps=1)
        block = data["retrieval"]["no_area_filter"]
        r3 = block["recall@3"]
        mrr = block["mrr@10"]
        print(f"measured recall@3={r3:.4f} mrr@10={mrr:.4f}")
        self.assertGreaterEqual(r3, self.RECALL3_MIN)
        self.assertGreaterEqual(mrr, self.MRR_MIN)


class AgentHarnessTest(unittest.TestCase):
    _sample_stream = [
        json.dumps(
            {
                "type": "assistant",
                "message": {
                    "content": [{"type": "tool_use", "name": "mcp__cr-tax-kb__search_law", "id": "t1"}],
                },
            }
        ),
        json.dumps(
            {
                "type": "result",
                "result": "Respuesta de prueba",
                "usage": {"input_tokens": 10, "output_tokens": 5},
                "total_cost_usd": 0.01,
                "duration_ms": 100,
                "num_turns": 2,
                "is_error": False,
                "modelUsage": {"sonnet": {}},
            }
        ),
    ]

    def test_build_command_flags(self):
        q = {
            "id": "lab-02",
            "style": "client",
            "area": "laboral",
            "covered": True,
            "question": "test?",
            "expected": ["ley-2:art-29"],
            "answer": "x",
        }
        argv_a, _ = agent.build_command("A", q, "sonnet", claude_bin="claude")
        self.assertIn("--mcp-config", argv_a)
        self.assertIn("--strict-mcp-config", argv_a)
        self.assertIn("mcp__cr-tax-kb__search_law", " ".join(argv_a))
        argv_b, _ = agent.build_command("B", q, "sonnet", claude_bin="claude")
        self.assertNotIn("--mcp-config", argv_b)
        self.assertIn("--strict-mcp-config", argv_b)
        argv_c, _ = agent.build_command("C", q, "sonnet", claude_bin="claude")
        self.assertIn("--append-system-prompt", argv_c)
        self.assertEqual(argv_c.count("--tools"), 1)

    def test_parse_stream(self):
        parsed = agent.parse_stream(self._sample_stream)
        self.assertEqual(parsed["tool_calls"], 1)
        self.assertEqual(parsed["result_text"], "Respuesta de prueba")
        self.assertEqual(parsed["usage"]["input_tokens"], 10)
        self.assertEqual(parsed["model_id"], "sonnet")

    def test_parse_judge_raw_fenced_result(self):
        inner = json.dumps({"verdict": "correct", "reason": "Coincide con la referencia."})
        fenced = f"```json\n{inner}\n```"
        outer = {"result": fenced, "usage": {"input_tokens": 1}, "total_cost_usd": 0.001}
        raw = json.dumps(outer)
        verdict, reason = agent.parse_judge_raw(raw)
        self.assertEqual(verdict, "correct")
        self.assertEqual(reason, "Coincide con la referencia.")

    def test_parse_stream_message_model_fallback(self):
        stream = [
            json.dumps(
                {
                    "type": "assistant",
                    "message": {"model": "claude-sonnet-4-20250514", "content": []},
                }
            ),
            json.dumps({"type": "result", "result": "ok", "usage": {}, "is_error": False}),
        ]
        parsed = agent.parse_stream(stream)
        self.assertEqual(parsed["model_id"], "claude-sonnet-4-20250514")

    def test_summarize_rate_denominators(self):
        records = [
            {
                "condition": "A",
                "status": "ok",
                "question": {"covered": True},
                "grades": {
                    "right_unit": True,
                    "quote_verbatim": False,
                    "false_refusal": False,
                    "refusal_correct": False,
                },
                "usage": {"input_tokens": 100},
                "total_cost_usd": 0.01,
                "tool_calls": 2,
                "judge": {"verdict": "correct", "total_cost_usd": 0.005},
            },
            {
                "condition": "A",
                "status": "ok",
                "question": {"covered": True},
                "grades": {
                    "right_unit": False,
                    "quote_verbatim": True,
                    "false_refusal": True,
                    "refusal_correct": False,
                },
                "usage": {"input_tokens": 200},
                "total_cost_usd": 0.02,
                "tool_calls": 0,
            },
            {
                "condition": "A",
                "status": "ok",
                "question": {"covered": False},
                "grades": {
                    "right_unit": True,
                    "quote_verbatim": True,
                    "false_refusal": True,
                    "refusal_correct": True,
                },
                "usage": {"input_tokens": 50},
                "total_cost_usd": 0.001,
                "tool_calls": 0,
            },
        ]
        s = agent._summarize(records, "A")
        self.assertEqual(s["n_covered"], 2)
        self.assertEqual(s["n_not_covered"], 1)
        self.assertAlmostEqual(s["right_unit_rate"], 0.5)
        self.assertAlmostEqual(s["quote_verbatim_rate"], 0.5)
        self.assertAlmostEqual(s["false_refusal_rate"], 0.5)
        self.assertAlmostEqual(s["refusal_correct_rate"], 1.0)
        self.assertAlmostEqual(s["total_cost_usd"], 0.01 + 0.005 + 0.02 + 0.001)
        self.assertAlmostEqual(s["mean_judge_cost"], 0.005)

    def test_grade_quotes(self):
        art_path = ROOT / "laws" / "ley-2" / "articles.jsonl"
        if not art_path.is_file():
            self.skipTest("laws/ley-2 missing")
        unit = None
        for line in art_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row["id"] == "ley-2:art-29":
                unit = row
                break
        self.assertIsNotNone(unit)
        from cr_tax_kb.laws import Unit

        units = {"ley-2:art-29": Unit(**{k: unit[k] for k in unit})}
        snippet = unit["text"].split("\n")[0][:80]
        question = {
            "covered": True,
            "expected": ["ley-2:art-29"],
            "question": "q",
        }
        good_footer = {
            "cited": ["ley-2:art-29"],
            "quotes": [snippet],
            "covered": True,
        }
        g = agent.grade({"parsed_footer": good_footer}, question, units)
        self.assertTrue(g["right_unit"])
        self.assertTrue(g["quote_verbatim"])
        bad_footer = {
            "cited": ["ley-2:art-29"],
            "quotes": ["texto inventado que no existe en la ley"],
            "covered": True,
        }
        g2 = agent.grade({"parsed_footer": bad_footer}, question, units)
        self.assertFalse(g2["quote_verbatim"])

    @classmethod
    def _kb_units(cls):
        from cr_tax_kb.search import KnowledgeBase

        kb = KnowledgeBase()
        if not kb.units:
            raise unittest.SkipTest("laws/ has no ingested norms")
        return kb.units

    def test_quote_ellipsis_split(self):
        units = self._kb_units()
        quote = (
            "La Caja podrá ordenar, administrativamente, el cierre del establecimiento, local o centro "
            "donde se realiza la actividad cuando: [...] b) Cuando exista mora por más de dos meses "
            "en el pago de las cuotas correspondientes, siempre y cuando no medie ningún proceso de "
            "arreglo de pago o declaratorio de derechos entre el patrono y la Caja."
        )
        footer = {"cited": ["ley-17:art-48"], "quotes": [quote], "covered": True}
        question = {"covered": True, "expected": ["ley-17:art-48"]}
        g = agent.grade({"parsed_footer": footer}, question, units)
        self.assertTrue(g["quote_verbatim"])
        self.assertTrue(g["quote_checks"][0]["ok"])

    def test_quote_trailing_punctuation(self):
        units = self._kb_units()
        quote = (
            "Salvo lo dicho en disposiciones especiales o que se tratare de un caso protegido por la "
            "Ley de Seguro Social, la única obligación del patrono es la de dar licencia al trabajador, "
            "hasta su total restablecimiento, siempre que éste se produzca dentro del lapso indicado."
        )
        footer = {"cited": ["ley-2:art-79"], "quotes": [quote], "covered": True}
        question = {"covered": True, "expected": ["ley-2:art-79"]}
        g = agent.grade({"parsed_footer": footer}, question, units)
        self.assertTrue(g["quote_verbatim"])

    def test_quote_first_letter_case(self):
        units = self._kb_units()
        quote = (
            "no deduzca la cuota obrera mencionada en el artículo 30 de esta ley, no pague la cuota "
            "patronal o que le corresponde como trabajador independiente."
        )
        footer = {"cited": ["ley-17:art-44"], "quotes": [quote], "covered": True}
        question = {"covered": True, "expected": ["ley-17:art-30"]}
        g = agent.grade({"parsed_footer": footer}, question, units)
        self.assertTrue(g["quote_verbatim"])

    def test_quote_stitched_sentences_fail(self):
        units = self._kb_units()
        quote = (
            "La trabajadora podrá optar por la reinstalación o dar por terminado el contrato de trabajo "
            "con responsabilidad patronal. En todo caso, el empleador o la empleadora deberán pagarle, "
            "además de la indemnización a que tenga derecho y en concepto de daños y perjuicios, las sumas "
            "correspondientes al subsidio de preparto y posparto, y los salarios que hubiera dejado de "
            "percibir desde el momento del despido, hasta completar ocho meses de embarazo."
        )
        footer = {
            "cited": ["ley-2:art-94", "ley-2:art-94-bis"],
            "quotes": [quote],
            "covered": True,
        }
        question = {"covered": True, "expected": ["ley-2:art-94"]}
        g = agent.grade({"parsed_footer": footer}, question, units)
        self.assertFalse(g["quote_verbatim"])
        self.assertFalse(g["quote_checks"][0]["ok"])


if __name__ == "__main__":
    unittest.main()
