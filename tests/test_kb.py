import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cr_tax_kb.cli import llms_txt  # noqa: E402
from cr_tax_kb.corpus import chunks_of, load_documents  # noqa: E402
from cr_tax_kb.search import KnowledgeBase  # noqa: E402

TOPICS = {"general", "iva", "renta", "cripto", "facturacion", "procedimiento", "ccss"}
STRENGTHS = {"primary", "official", "secondary"}


class CorpusTest(unittest.TestCase):
    docs = load_documents()

    def test_frontmatter(self):
        ids = [d.id for d in self.docs]
        self.assertEqual(len(ids), len(set(ids)), "duplicate ids")
        for d in self.docs:
            with self.subTest(doc=d.id):
                self.assertIn(d.topic, TOPICS)
                self.assertTrue(Path(d.path).parent.name == d.topic or (ROOT / d.path).parent.name == d.topic)
                self.assertIn(d.verified, STRENGTHS)
                self.assertRegex(d.as_of, r"^\d{4}-\d{2}-\d{2}$")
                self.assertTrue(d.keywords_es)
                self.assertTrue(d.sources, "needs at least one source")
                for s in d.sources:
                    self.assertTrue(s.get("url", "").startswith("https://"), s)
                    self.assertIn(s.get("type"), STRENGTHS | {"primary"}, s)

    def test_every_section_has_spanish_keywords(self):
        for d in self.docs:
            for c in chunks_of(d):
                with self.subTest(chunk=c.chunk_id):
                    self.assertTrue(c.keywords, "add <!-- es: ... --> under the heading")
                    self.assertNotIn("<!--", c.text)

    def test_links_resolve(self):
        ids = {d.id for d in self.docs}
        for d in self.docs:
            for link in re.findall(r"\[\[([^\]]+)\]\]", d.body):
                self.assertIn(link, ids, f"{d.id} links to unknown [[{link}]]")

    def test_no_em_dashes(self):
        for path in list(ROOT.rglob("*.md")) + [ROOT / "llms.txt"]:
            # laws/ holds verbatim legal text, which keeps the source's punctuation.
            if ".git" not in path.parts and "laws" not in path.relative_to(ROOT).parts:
                self.assertNotIn("—", path.read_text(encoding="utf-8"), path)

    def test_generated_files_current(self):
        kb = KnowledgeBase()
        self.assertEqual((ROOT / "llms.txt").read_text(encoding="utf-8"), llms_txt(kb), "run cli export")
        index = json.loads((ROOT / "data" / "index.json").read_text(encoding="utf-8"))
        self.assertEqual(index["documents"], [d.summary() for d in kb.docs.values()], "run cli export")


class RetrievalTest(unittest.TestCase):
    def test_eval_questions(self):
        kb = KnowledgeBase()
        qs = json.loads((ROOT / "eval" / "questions.json").read_text(encoding="utf-8"))
        misses = [q["q"] for q in qs if q["expect"] not in [h["doc_id"] for h in kb.search(q["q"], 3)]]
        self.assertLessEqual(len(misses), len(qs) // 10, misses)

    def test_section_eval(self):
        kb = KnowledgeBase()
        qs = json.loads((ROOT / "eval" / "sections.json").read_text(encoding="utf-8"))
        misses = [q["q"] for q in qs if q["expect"] not in [h["chunk_id"] for h in kb.search(q["q"], 3)]]
        self.assertLessEqual(len(misses), len(qs) // 10, misses)

    def test_topic_filter(self):
        hits = KnowledgeBase().search("tarifa", 10, topic="iva")
        self.assertTrue(hits)
        self.assertTrue(all(h["topic"] == "iva" for h in hits))


class McpTest(unittest.TestCase):
    def test_stdio_handshake_and_search(self):
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize",
             "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
             "params": {"name": "search_tax_kb", "arguments": {"query": "criptomonedas ganancia de capital", "k": 2}}},
            {"jsonrpc": "2.0", "id": 4, "method": "resources/read", "params": {"uri": "crtax://doc/iva-exports"}},
            {"jsonrpc": "2.0", "id": 5, "method": "nope"},
        ]
        proc = subprocess.run(
            [sys.executable, str(ROOT / "src" / "cr_tax_kb" / "mcp_server.py")],
            input="\n".join(json.dumps(m) for m in msgs) + "\n",
            capture_output=True, text=True, timeout=30,
        )
        out = {r["id"]: r for r in map(json.loads, proc.stdout.splitlines())}
        self.assertEqual(sorted(out), [1, 2, 3, 4, 5])
        self.assertEqual(out[1]["result"]["serverInfo"]["name"], "cr-tax-kb")
        self.assertEqual(len(out[2]["result"]["tools"]), 7)
        self.assertIn("crypto-assets#", out[3]["result"]["content"][0]["text"])
        self.assertIn("art. 8", out[4]["result"]["contents"][0]["text"])
        self.assertEqual(out[5]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
