"""Company knowledge base: Fact3's own processes, templates and client notes.

Separate from the tax corpus. The documents live where the team already writes
them, so nobody has to touch this repo:

- FACT3_DRIVE_FOLDER_ID: a Google Drive folder shared (Viewer) with the Cloud Run
  service account. Google Docs are exported as Markdown; .md and .txt files are
  read as is. Subfolders become the path, e.g. "Clientes/GrantFox/Plan".
- FACT3_KB_DIR: a local folder of .md files with the same layout (local use, tests).

Documents under a top-level "Clientes" (or "Clients") folder belong to the client
named by the next folder. The index is rebuilt in memory and refreshed at most
every FACT3_REFRESH_SECONDS (default 300) when a tool is called, so an edit in
Drive shows up within a few minutes without a redeploy.
"""

import json
import os
import re
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .search import fold, match_expression

CLIENT_FOLDERS = {"clientes", "clients"}
GOOGLE_DOC = "application/vnd.google-apps.document"
FOLDER = "application/vnd.google-apps.folder"
DRIVE = "https://www.googleapis.com/drive/v3/files"
METADATA_TOKEN = (
    "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
    "?scopes=https://www.googleapis.com/auth/drive.readonly"
)


@dataclass
class CompanyDoc:
    path: str  # "Procesos/Cierre mensual"
    text: str
    modified: str = ""
    url: str = ""

    @property
    def client(self):
        parts = self.path.split("/")
        return parts[1] if len(parts) > 2 and fold(parts[0]) in CLIENT_FOLDERS else None


def sections_of(text):
    """(heading, body) pairs split on #, ## and ### headings; text before the first heading is ''."""
    out, heading, lines = [], "", []
    for line in text.splitlines():
        m = re.match(r"^#{1,3}\s+(.*)", line)
        if m:
            if "".join(lines).strip():
                out.append((heading, "\n".join(lines).strip()))
            heading, lines = m.group(1).strip(), []
        else:
            lines.append(line)
    if "".join(lines).strip():
        out.append((heading, "\n".join(lines).strip()))
    return out


class LocalSource:
    def __init__(self, root):
        self.root = Path(root)

    def fetch(self, known):
        docs = {}
        for f in sorted(self.root.rglob("*")):
            if f.suffix.lower() not in (".md", ".txt") or not f.is_file():
                continue
            path = str(f.relative_to(self.root).with_suffix(""))
            modified = str(f.stat().st_mtime)
            old = known.get(path)
            docs[path] = old if old and old.modified == modified else CompanyDoc(path, f.read_text(encoding="utf-8"), modified)
        return docs


class DriveSource:
    """Reads a Drive folder tree with the service account's token (Cloud Run metadata server)."""

    def __init__(self, folder_id):
        self.folder_id = folder_id
        self._token, self._expires = None, 0

    def token(self):
        if time.time() > self._expires - 60:
            req = urllib.request.Request(METADATA_TOKEN, headers={"Metadata-Flavor": "Google"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.load(r)
            self._token, self._expires = data["access_token"], time.time() + data["expires_in"]
        return self._token

    def get(self, url):
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token()}"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()

    def children(self, folder_id):
        params = {
            "q": f"'{folder_id}' in parents and trashed = false",
            "fields": "nextPageToken, files(id, name, mimeType, modifiedTime, webViewLink)",
            "pageSize": "1000",
            "supportsAllDrives": "true",
            "includeItemsFromAllDrives": "true",
        }
        while True:
            data = json.loads(self.get(f"{DRIVE}?{urllib.parse.urlencode(params)}"))
            yield from data.get("files", [])
            if not data.get("nextPageToken"):
                return
            params["pageToken"] = data["nextPageToken"]

    def fetch(self, known):
        docs, stack = {}, [(self.folder_id, "")]
        while stack:
            folder_id, prefix = stack.pop()
            for f in self.children(folder_id):
                name = f["name"]
                if f["mimeType"] == FOLDER:
                    stack.append((f["id"], f"{prefix}{name}/"))
                    continue
                if f["mimeType"] == GOOGLE_DOC:
                    url = f"{DRIVE}/{f['id']}/export?mimeType=text/markdown"
                elif name.lower().endswith((".md", ".txt")):
                    url, name = f"{DRIVE}/{f['id']}?alt=media&supportsAllDrives=true", name.rsplit(".", 1)[0]
                else:
                    continue  # PDFs, sheets, images: not indexed
                path = prefix + name
                old = known.get(path)
                if old and old.modified == f["modifiedTime"]:
                    docs[path] = old
                else:
                    text = self.get(url).decode("utf-8", errors="replace")
                    docs[path] = CompanyDoc(path, text, f["modifiedTime"], f.get("webViewLink", ""))
        return docs


def source_from_env():
    if os.environ.get("FACT3_DRIVE_FOLDER_ID"):
        return DriveSource(os.environ["FACT3_DRIVE_FOLDER_ID"])
    if os.environ.get("FACT3_KB_DIR"):
        return LocalSource(os.environ["FACT3_KB_DIR"])
    return None


class CompanyKB:
    def __init__(self, source, refresh_seconds=None):
        self.source = source
        self.refresh_seconds = float(refresh_seconds or os.environ.get("FACT3_REFRESH_SECONDS", 300))
        self.docs, self.loaded_at, self.error = {}, 0.0, None
        self.lock = threading.Lock()

    def refresh(self, force=False):
        with self.lock:
            if not force and self.docs and time.time() - self.loaded_at < self.refresh_seconds:
                return
            try:
                docs = self.source.fetch(self.docs)
            except Exception as e:  # keep serving the last good copy
                self.error = f"{type(e).__name__}: {e}"
                self.loaded_at = time.time()
                return
            self.error = None
            db = sqlite3.connect(":memory:", check_same_thread=False)
            db.execute(
                "CREATE VIRTUAL TABLE fts USING fts5(path UNINDEXED, client UNINDEXED, title, heading, text,"
                " tokenize='unicode61 remove_diacritics 2')"
            )
            for d in docs.values():
                for heading, body in sections_of(d.text) or [("", "")]:
                    db.execute("INSERT INTO fts VALUES (?,?,?,?,?)", (d.path, d.client and fold(d.client), d.path, heading, body))
            old, self.docs, self.db, self.loaded_at = getattr(self, "db", None), docs, db, time.time()
            if old:
                old.close()

    def clients(self):
        return sorted({d.client for d in self.docs.values() if d.client})

    def search(self, query, k=5, client=None):
        self.refresh()
        expr = match_expression(query)
        if not expr or not self.docs:
            return []
        sql = "SELECT path, heading, text, bm25(fts, 0, 0, 2.0, 3.0, 1.0) AS score FROM fts WHERE fts MATCH ?"
        args = [expr]
        if client:
            sql += " AND client = ?"
            args.append(fold(client))
        sql += " ORDER BY score LIMIT ?"
        args.append(int(k))
        return [
            {"path": p, "heading": h, "text": t, "score": round(-s, 3), "client": self.docs[p].client, "url": self.docs[p].url}
            for p, h, t, s in self.db.execute(sql, args)
        ]

    def get(self, path):
        self.refresh()
        d = self.docs.get(path.strip().strip("/"))
        if d:
            return d
        matches = [d for d in self.docs.values() if fold(d.path).endswith(fold(path.strip()))]
        return matches[0] if len(matches) == 1 else None


def format_company_hits(hits):
    if not hits:
        return "No results in the Fact3 knowledge base. Try other terms, or list_fact3_docs to browse."
    parts = []
    for h in hits:
        where = h["path"] + (f" > {h['heading']}" if h["heading"] else "")
        parts.append(f"### {where}\n[doc: {h['path']}" + (f" | {h['url']}" if h["url"] else "") + f"]\n\n{h['text']}")
    return "\n\n---\n\n".join(parts)
