import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cr_tax_kb.laws import load_registry  # noqa: E402
from cr_tax_kb.search import KnowledgeBase, excerpt, format_units, load_concepts  # noqa: E402


class ConceptMapTest(unittest.TestCase):
    kb = KnowledgeBase()
    concepts = load_concepts()
    registry = {r["id"] for r in load_registry()}

    def test_concepts_are_valid(self):
        ids = [c["id"] for c in self.concepts]
        self.assertEqual(len(ids), len(set(ids)), "duplicate concept ids")
        for c in self.concepts:
            with self.subTest(concept=c["id"]):
                self.assertTrue(c["label"] and c["triggers"])
                self.assertTrue(c["anchors"] or c["pending"], "a concept needs anchors or pending norms")
                for uid in c["anchors"]:
                    self.assertIn(uid, self.kb.units, f"anchor {uid} is not a stored article")
                for nid in c["pending"]:
                    self.assertIn(nid, self.registry, f"pending norm {nid} is not in laws/registry.json")

    def test_everyday_wording_finds_central_article(self):
        hits = self.kb.search_law("tengo jefe y horario pero facturo, ¿soy empleado?", 3)
        self.assertEqual(hits[0]["id"], "ley-2:art-18")
        self.assertTrue(hits[0]["why"])

    def test_filters_apply_to_anchors(self):
        hits = self.kb.search_law("tengo jefe pero facturo, ¿soy empleado?", 5, area="tributario")
        self.assertNotIn("ley-2:art-18", [h["id"] for h in hits])

    def test_coverage_warning_for_pending_norm(self):
        warnings = self.kb.coverage_warnings("¿cuándo se paga el aguinaldo?")
        self.assertIn("ley-2412", [w["norm"] for w in warnings])
        out = format_units([], "aguinaldo", warnings)
        self.assertIn("Coverage warning", out)

    def test_search_output_is_compact(self):
        long_unit = max(self.kb.units.values(), key=lambda u: len(u.text))
        cut = excerpt(long_unit.text, "tarifa")
        self.assertLess(len(cut), 1300)
        out = format_units([{**long_unit.__dict__, "why": None}], "tarifa")
        self.assertIn("get_article", out)
        self.assertIn(long_unit.text, format_units([long_unit.__dict__]))


if __name__ == "__main__":
    unittest.main()
