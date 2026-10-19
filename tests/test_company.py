import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cr_tax_kb.company import CompanyKB, DriveSource, LocalSource, sections_of  # noqa: E402
from cr_tax_kb.mcp_server import Server  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "fact3"


class FakeDrive(DriveSource):
    """Drive API answers from a dict, counting exports."""

    def __init__(self):
        super().__init__("root")
        self.exports = 0
        self.tree = {
            "root": [
                {"id": "f1", "name": "Procesos", "mimeType": "application/vnd.google-apps.folder"},
                {"id": "pdf", "name": "Contrato.pdf", "mimeType": "application/pdf", "modifiedTime": "1"},
            ],
            "f1": [
                {"id": "d1", "name": "Onboarding", "mimeType": "application/vnd.google-apps.document",
                 "modifiedTime": "1", "webViewLink": "https://docs.google.com/document/d/d1"},
            ],
        }

    def token(self):
        return "t"

    def get(self, url):
        if "/export" in url:
            self.exports += 1
            return "# Onboarding\n\n## Firma\n\nSign the engagement letter first.".encode()
        folder = url.split("%27")[1]
        return json.dumps({"files": self.tree[folder]}).encode()


class CompanyTest(unittest.TestCase):
    def setUp(self):
        self.co = CompanyKB(LocalSource(FIXTURES))

    def test_sections(self):
        self.assertEqual([h for h, _ in sections_of("intro\n# A\nx\n## B\ny")], ["", "A", "B"])

    def test_search_and_clients(self):
        hits = self.co.search("conciliación bancaria")
        self.assertEqual(hits[0]["path"], "Procesos/Cierre mensual")
        self.assertEqual(hits[0]["heading"], "Conciliación bancaria")
        self.assertEqual(self.co.clients(), ["Acme", "GrantFox"])

    def test_client_filter(self):
        hits = self.co.search("planilla", client="grantfox")
        self.assertEqual([h["path"] for h in hits], ["Clientes/GrantFox/Plan"])

    def test_get_by_short_path(self):
        self.assertEqual(self.co.get("Cierre mensual").path, "Procesos/Cierre mensual")
        self.assertIsNone(self.co.get("nope"))

    def test_drive_source_exports_docs_once(self):
        drive = FakeDrive()
        co = CompanyKB(drive, refresh_seconds=0.0001)
        self.assertEqual(co.search("firma")[0]["url"], "https://docs.google.com/document/d/d1")
        self.assertEqual(list(co.docs), ["Procesos/Onboarding"])
        co.refresh(force=True)  # unchanged modifiedTime: no new export
        self.assertEqual(drive.exports, 1)

    def test_failed_refresh_keeps_last_copy(self):
        self.co.refresh()
        self.co.source = None  # fetch now raises
        self.co.refresh(force=True)
        self.assertTrue(self.co.error)
        self.assertTrue(self.co.search("planilla"))

    def test_mcp_tools(self):
        server = Server(company=self.co)
        names = [t["name"] for t in server.dispatch("tools/list", {})["tools"]]
        self.assertIn("search_fact3", names)
        out = server.call_tool("search_fact3", {"query": "IVA", "client": None})
        self.assertIn("Procesos/Cierre mensual", out["content"][0]["text"])
        out = server.call_tool("list_fact3_docs", {"client": "Acme"})
        self.assertEqual([d["path"] for d in json.loads(out["content"][0]["text"])["documents"]], ["Clientes/Acme/Notas"])

    def test_tools_hidden_without_source(self):
        names = [t["name"] for t in Server(kb=Server().kb).dispatch("tools/list", {})["tools"]]
        self.assertNotIn("search_fact3", names)


if __name__ == "__main__":
    unittest.main()
