# Hosting the MCP server

The stdio server (`mcp_server.py`) only works for MCP clients on the same machine. To use the knowledge base from Claude on the web or phone (custom connectors), run the HTTP server (`http_server.py`) at a public HTTPS URL. It serves the same tools, has no dependencies, and needs no database: the search index is built in memory at start (well under a second).

## How access works

The server reads a secret from the `CR_TAX_KB_TOKEN` environment variable. The endpoint is `https://<host>/mcp/<token>`; any other path answers 404. Anyone with the full URL can query the knowledge base, so share it only with the people who should use it, and rotate the token if it leaks (change the secret, redeploy, send the new URL). OAuth login is a later step.

Generate a token:

```
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run it locally

```
CR_TAX_KB_TOKEN=dev PORT=8080 PYTHONPATH=src python3 -m cr_tax_kb.http_server
curl -s -X POST localhost:8080/mcp/dev -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}'
```

Or with Docker: `docker build -t cr-tax-kb . && docker run -p 8080:8080 -e CR_TAX_KB_TOKEN=dev cr-tax-kb`.

## Deploy on Google Cloud Run

One time, in the Google Cloud console:

1. Create a project (for example `fact3`) and link a billing account. With a few users the service should stay inside the free tier; set a budget alert anyway (Billing > Budgets & alerts).
2. Secret Manager: create a secret `cr-tax-kb-token` with the generated token.
3. Cloud Run > Deploy container > **Continuously deploy from a repository**. Connect GitHub, pick `Villarley/cr-tax-kb`, branch `^main$`, build type **Dockerfile** (path `/Dockerfile`). Every merge to `main` then rebuilds and redeploys.
4. Service settings:
   - Region: `us-central1` (or the closest one with free tier)
   - Authentication: **Allow unauthenticated invocations** (the token in the path is the access control)
   - Container port 8080, memory 512 MiB, CPU 1, minimum instances 0, maximum instances 2
   - Variables & secrets: expose secret `cr-tax-kb-token` as env var `CR_TAX_KB_TOKEN` (required: without it the container exits at start and the deploy fails with "failed to start and listen on the port")
5. Deploy. The service URL looks like `https://cr-tax-kb-xxxxx-uc.a.run.app`. Check `https://<service-url>/health` answers `ok` (not `/healthz`: Cloud Run reserves URL paths ending in `z` and answers them with its own 404).

The connector URL is `https://<service-url>/mcp/<token>`.

With minimum instances 0 the first request after a quiet period waits a few seconds while the container starts. Set minimum instances to 1 to avoid that, at a monthly cost.

## Add it to Claude

Each person: Claude > Settings > Connectors > **Add custom connector**, name `CR Tax KB`, paste the connector URL, leave OAuth fields empty. Then enable it in a chat from the tools menu. Custom connectors may require a paid Claude plan.

Claude Code: `claude mcp add --transport http cr-tax-kb https://<service-url>/mcp/<token>`.

## Protocol notes

Streamable HTTP transport, JSON responses only: `POST` carries one JSON-RPC message or a batch; notifications get `202`. There is no server-initiated stream, so `GET` and `DELETE` on the endpoint answer `405`. No session ids: every request is independent, which lets Cloud Run route requests to any instance.

## Fact3 knowledge base (processes and clients)

The same service can also serve Fact3's own documents (processes, templates, per-client notes) through three more tools: `search_fact3`, `get_fact3_doc` and `list_fact3_docs`. They appear only when a source is configured. The documents stay in Google Drive, where the team edits them as normal Google Docs; the service reads them and picks up edits within 5 minutes, with no redeploy.

Folder layout (any names work; documents under `Clientes/<client>/` are tagged with that client, so a search can be limited to one client):

```
Fact3 KB/
  Procesos/        Cierre mensual, Onboarding de cliente, ...
  Plantillas/
  Clientes/
    GrantFox/      Plan, Acuerdos, ...
```

Google Docs, `.md` and `.txt` files are indexed; PDFs, sheets and images are skipped. Headings (Título 1 to 3) split a document into sections, so use them.

One time:

1. Enable the Drive API: `gcloud services enable drive.googleapis.com`.
2. Share the `Fact3 KB` folder as **Viewer** with the service's account. Find it with `gcloud run services describe cr-tax-kb-git --region europe-west1 --format='value(spec.template.spec.serviceAccountName)'`; if empty, it is the default `<project-number>-compute@developer.gserviceaccount.com`.
3. Set the folder id (the last part of the folder's URL): `gcloud run services update cr-tax-kb-git --region europe-west1 --update-env-vars FACT3_DRIVE_FOLDER_ID=<id>`.

Editing goes through each person's own Google Drive connector in Claude (share the folder with them as Editor), so changes carry their name; the service account cannot create files in a personal Drive (no storage quota), only in a Shared Drive.

Everyone with the connector URL can read every document in the folder, all clients included. Keep anything that must stay with fewer people outside it. Per-person access is a later step.

Local use: `FACT3_KB_DIR=/path/to/folder/of/md` instead of the Drive id. `FACT3_REFRESH_SECONDS` changes the refresh interval (default 300).
