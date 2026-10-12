#!/usr/bin/env python3
"""Agent benchmark harness (calls claude CLI; not for CI)."""

from __future__ import annotations

import argparse
import json
import re
import shlex
import subprocess
import sys
import textwrap
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = REPO_ROOT / "benchmark" / "questions.json"
MCP_CONFIG = REPO_ROOT / ".mcp.json"
LAWS_ROOT = REPO_ROOT / "laws"
CONTEXT_TOKEN_LIMIT = 180000
CALL_TIMEOUT_S = 600

AREA_DEFAULT_NORM = {"laboral": "ley-2", "ccss": "ley-17", "tributario": "ley-7092"}

ALLOWED_TOOLS_ENGINE = (
    "mcp__cr-tax-kb__search_law,mcp__cr-tax-kb__get_article,mcp__cr-tax-kb__list_norms"
)


def _setup_path():
    src = str(REPO_ROOT / "src")
    if src not in sys.path:
        sys.path.insert(0, src)


def approx_tokens(text: str) -> float:
    return len(text) / 4.0


def git_commit() -> str:
    try:
        head = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if head.returncode != 0:
            return "unknown"
        commit = head.stdout.strip()
        dirty = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if dirty.stdout.strip():
            stat = subprocess.run(
                ["git", "diff", "--stat", "HEAD"],
                capture_output=True,
                text=True,
                cwd=REPO_ROOT,
                check=False,
            )
            lines = stat.stdout.strip().splitlines()
            tail = lines[-1] if lines else ""
            return f"uncommitted {tail}".strip()
        return commit
    except OSError:
        return "git unavailable"


def load_questions() -> dict:
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def norm_catalog_text() -> str:
    lines = []
    for norm_path in sorted(LAWS_ROOT.glob("*/norm.json")):
        meta = json.loads(norm_path.read_text(encoding="utf-8"))
        lines.append(f"- {meta['id']}: {meta.get('title', '')}")
    return "\n".join(lines)


def _json_footer_instruction() -> str:
    return textwrap.dedent(
        """
        Responde en español. Incluye citas textuales entre comillas cuando afirmes una regla.
        Termina la respuesta con un bloque markdown ```json ... ``` que contenga exactamente:
        {"cited": ["<norm-id>:art-<n>", ...], "quotes": ["texto exacto", ...], "covered": true|false}
        Usa ids como ley-2:art-29, ley-9635:trans-V-BIS, reglamento-renta:anexo-1 (minúsculas, guiones).
        """
    ).strip()


def _stored_norms_block() -> str:
    return "Normas almacenadas en el repositorio:\n" + norm_catalog_text()


SYS_A = (
    "Eres un asistente legal costarricense. Usa únicamente las herramientas MCP cr-tax-kb "
    "(search_law, get_article, list_norms) para fundamentar la respuesta en textos vigentes almacenados.\n"
    + _stored_norms_block()
    + "\n"
    + _json_footer_instruction()
)

SYS_B = (
    "Eres un asistente legal costarricense. Responde desde tu conocimiento de la legislación costarricense "
    "sin herramientas externas. Puedes citar normas almacenadas o otras leyes usando el mismo patrón de id.\n"
    + _stored_norms_block()
    + "\n"
    + _json_footer_instruction()
)

SYS_C = (
    "Eres un asistente legal costarricense. Responde únicamente con base en el texto legal pegado "
    "en el mensaje del usuario. Si el texto no contiene la respuesta, indica que no está cubierto.\n"
    + _stored_norms_block()
    + "\n"
    + _json_footer_instruction()
)

JUDGE_PROMPT = textwrap.dedent(
    """
    Eres un evaluador legal. Compara la respuesta del candidato con la referencia.
    Devuelve un único objeto JSON (sin markdown): {"verdict":"correct|partial|incorrect","reason":"..."}

    Pregunta:
    <<QUESTION>>

    Respuesta de referencia (paráfrasis esperada):
    <<REFERENCE>>

    Respuesta del candidato:
    <<CANDIDATE>>
    """
).strip()


def _fill_judge_prompt(question: str, reference: str, candidate: str) -> str:
    return (
        JUDGE_PROMPT.replace("<<QUESTION>>", question)
        .replace("<<REFERENCE>>", reference)
        .replace("<<CANDIDATE>>", candidate)
    )


def _norm_id(s: str) -> str:
    return re.sub(r"\s+", "", s.strip().lower())


def _page_norm_id(question: dict) -> str:
    if question.get("covered") and question.get("expected"):
        return question["expected"][0].split(":", 1)[0]
    return AREA_DEFAULT_NORM[question["area"]]


def _page_text(norm_id: str) -> str:
    path = LAWS_ROOT / norm_id / "text.md"
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def build_command(
    condition: str,
    question: dict,
    model: str,
    *,
    claude_bin: str = "claude",
) -> tuple[list[str], str | None]:
    """Return argv for claude and optional stdin (unused; prompt passed via -p)."""
    qtext = question["question"]
    base = [
        claude_bin,
        "--output-format",
        "stream-json",
        "--verbose",
        "--model",
        model,
        "--no-session-persistence",
        "--setting-sources",
        "project",
        "--strict-mcp-config",
        "--tools",
        "",
    ]
    if condition == "A":
        argv = base + [
            "--mcp-config",
            str(MCP_CONFIG),
            "--allowedTools",
            ALLOWED_TOOLS_ENGINE,
            "--append-system-prompt",
            SYS_A,
            "-p",
            qtext,
        ]
        return argv, None
    if condition == "B":
        argv = base + [
            "--append-system-prompt",
            SYS_B,
            "-p",
            qtext,
        ]
        return argv, None
    if condition == "C":
        norm_id = _page_norm_id(question)
        body = _page_text(norm_id)
        prompt = (
            f"Texto legal completo ({norm_id}):\n\n{body}\n\n---\n\nPregunta:\n{qtext}"
        )
        argv = base + [
            "--append-system-prompt",
            SYS_C,
            "-p",
            prompt,
        ]
        return argv, None
    raise ValueError(f"unknown condition {condition!r}")


def prompt_token_estimate(condition: str, question: dict) -> float:
    argv, _ = build_command(condition, question, "sonnet")
    # Last arg after -p is the user prompt; system prompts add separately.
    idx = argv.index("-p")
    user_prompt = argv[idx + 1]
    sys_map = {"A": SYS_A, "B": SYS_B, "C": SYS_C}
    return approx_tokens(user_prompt) + approx_tokens(sys_map[condition])


def _model_id_from_usage(mu: dict) -> str | None:
    if not isinstance(mu, dict) or not mu:
        return None
    ids = sorted(mu.keys())
    if len(ids) == 1:
        return ids[0]
    return ",".join(ids)


def parse_stream(lines: list[str]) -> dict:
    tool_calls = 0
    result_event = None
    message_model: str | None = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        ev_type = ev.get("type")
        if message_model is None and ev_type in ("system", "init"):
            m = ev.get("model")
            if isinstance(m, str) and m:
                message_model = m
        if ev_type == "assistant":
            msg = ev.get("message") or {}
            if message_model is None:
                m = msg.get("model") or ev.get("model")
                if isinstance(m, str) and m:
                    message_model = m
            for block in msg.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    tool_calls += 1
        if ev_type == "result":
            result_event = ev
    model_id: str | None = None
    if result_event:
        model_id = _model_id_from_usage(result_event.get("modelUsage") or {})
    if not model_id and message_model:
        model_id = message_model
    out = {"tool_calls": tool_calls, "model_id": model_id}
    if result_event:
        out.update(
            {
                "result_text": result_event.get("result") or "",
                "usage": result_event.get("usage") or {},
                "total_cost_usd": result_event.get("total_cost_usd"),
                "duration_ms": result_event.get("duration_ms"),
                "num_turns": result_event.get("num_turns"),
                "is_error": result_event.get("is_error"),
            }
        )
        if result_event.get("modelUsage"):
            out["model_usage"] = result_event["modelUsage"]
    else:
        out["result_text"] = ""
        out["usage"] = {}
    return out


_FENCE_JSON = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)


def parse_answer_footer(text: str) -> dict | None:
    if not text:
        return None
    m = _FENCE_JSON.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Trailing raw json object
    m2 = re.search(r"(\{[^{}]*\"cited\"[^{}]*\})\s*$", text, re.DOTALL)
    if m2:
        try:
            return json.loads(m2.group(1))
        except json.JSONDecodeError:
            pass
    return None


def _collapse_ws(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())


def grade(record: dict, question: dict, units: dict) -> dict:
    """Deterministic grading from parsed footer and question metadata."""
    footer = record.get("parsed_footer") or {}
    cited_raw = footer.get("cited") or []
    cited = [_norm_id(c) for c in cited_raw if isinstance(c, str)]
    expected = [_norm_id(e) for e in question.get("expected") or []]
    right_unit = any(e in cited for e in expected) if expected else False

    quotes = [q for q in (footer.get("quotes") or []) if isinstance(q, str) and q.strip()]
    norm_keys = {_norm_id(k): k for k in units}
    stored_cited = [c for c in cited if c in norm_keys]
    quote_verbatim = False
    if quotes and stored_cited:
        quote_verbatim = True
        for q in quotes:
            qn = _collapse_ws(q)
            found = False
            for cid in stored_cited:
                u = units[norm_keys[cid]]
                text = _collapse_ws(u.text)
                notes = _collapse_ws(" ".join(u.notes))
                if qn in text or qn in notes:
                    found = True
                    break
            if not found:
                quote_verbatim = False
                break

    resp_covered = footer.get("covered")
    is_q_covered = bool(question.get("covered"))
    false_refusal = is_q_covered and resp_covered is False
    refusal_correct = (not is_q_covered) and (resp_covered is False)

    return {
        "right_unit": right_unit,
        "quote_verbatim": quote_verbatim,
        "false_refusal": false_refusal,
        "refusal_correct": refusal_correct,
        "parsed_cited": cited,
    }


def _run_claude(argv: list[str], cwd: Path, timeout: int) -> tuple[list[str], float, int]:
    t0 = time.perf_counter()
    proc = subprocess.run(
        argv,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    wall = time.perf_counter() - t0
    lines = (proc.stdout or "").splitlines()
    if proc.stderr:
        lines.extend(proc.stderr.splitlines())
    return lines, wall, proc.returncode


def _judge(
    claude_bin: str,
    judge_model: str,
    question: str,
    reference: str,
    candidate: str,
) -> dict:
    prompt = _fill_judge_prompt(question, reference, candidate)
    argv = [
        claude_bin,
        "-p",
        prompt,
        "--model",
        judge_model,
        "--tools",
        "",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--output-format",
        "json",
    ]
    lines, wall, rc = _run_claude(argv, REPO_ROOT, CALL_TIMEOUT_S)
    raw = "\n".join(lines)
    verdict = None
    reason = None
    usage = {}
    cost = None
    model_id = None
    try:
        outer = json.loads(raw)
        if isinstance(outer, dict):
            usage = outer.get("usage") or {}
            cost = outer.get("total_cost_usd")
            model_id = _model_id_from_usage(outer.get("modelUsage") or {})
            if not model_id:
                m = outer.get("model")
                if isinstance(m, str) and m:
                    model_id = m
            inner = outer.get("result") or outer.get("response") or ""
            if isinstance(inner, str):
                parsed = json.loads(inner)
            else:
                parsed = inner
            if isinstance(parsed, dict):
                verdict = parsed.get("verdict")
                reason = parsed.get("reason")
    except json.JSONDecodeError:
        pass
    return {
        "verdict": verdict,
        "reason": reason,
        "usage": usage,
        "total_cost_usd": cost,
        "model_id": model_id,
        "wall_seconds": wall,
        "returncode": rc,
        "raw": raw[:2000],
    }


def _summarize(records: list[dict], condition: str) -> dict:
    subset = [r for r in records if r.get("condition") == condition and r.get("status") == "ok"]
    skipped = sum(1 for r in records if r.get("condition") == condition and r.get("status") == "skipped_context")
    errors = sum(1 for r in records if r.get("condition") == condition and r.get("status") == "error")
    if not subset:
        return {"n": 0, "skipped_context": skipped, "errors": errors}

    covered_subset = [r for r in subset if r.get("question", {}).get("covered")]
    not_covered_subset = [r for r in subset if not r.get("question", {}).get("covered")]
    n_covered = len(covered_subset)
    n_not_covered = len(not_covered_subset)

    def rate_on(recs: list[dict], key: str) -> float:
        vals = [r.get("grades", {}).get(key) for r in recs]
        vals = [v for v in vals if v is not None]
        return sum(1 for v in vals if v) / len(vals) if vals else 0.0

    judge_counts = {"correct": 0, "partial": 0, "incorrect": 0, "missing": 0}
    for r in subset:
        if not r.get("question", {}).get("covered"):
            continue
        v = (r.get("judge") or {}).get("verdict")
        if v in judge_counts:
            judge_counts[v] += 1
        else:
            judge_counts["missing"] += 1

    jc_total = sum(judge_counts[k] for k in ("correct", "partial", "incorrect"))
    inputs, outputs, costs, walls, tools, judge_costs = [], [], [], [], [], []
    total_cost_usd = 0.0
    for r in subset:
        u = r.get("usage") or {}
        inp = (u.get("input_tokens") or 0) + (u.get("cache_creation_input_tokens") or 0) + (
            u.get("cache_read_input_tokens") or 0
        )
        inputs.append(inp)
        outputs.append(u.get("output_tokens") or 0)
        if r.get("total_cost_usd") is not None:
            ac = float(r["total_cost_usd"])
            costs.append(ac)
            total_cost_usd += ac
        walls.append(r.get("wall_seconds") or 0.0)
        tools.append(r.get("tool_calls") or 0)
        j = r.get("judge") or {}
        if j.get("total_cost_usd") is not None:
            jc = float(j["total_cost_usd"])
            judge_costs.append(jc)
            total_cost_usd += jc

    def mean(xs):
        return sum(xs) / len(xs) if xs else 0.0

    def median(xs):
        if not xs:
            return 0.0
        s = sorted(xs)
        m = len(s) // 2
        return s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2

    return {
        "n": len(subset),
        "n_covered": n_covered,
        "n_not_covered": n_not_covered,
        "skipped_context": skipped,
        "errors": errors,
        "right_unit_rate": rate_on(covered_subset, "right_unit"),
        "quote_verbatim_rate": rate_on(covered_subset, "quote_verbatim"),
        "false_refusal_rate": rate_on(covered_subset, "false_refusal"),
        "refusal_correct_rate": rate_on(not_covered_subset, "refusal_correct"),
        "judge_correct_rate": judge_counts["correct"] / jc_total if jc_total else 0.0,
        "judge_partial_rate": judge_counts["partial"] / jc_total if jc_total else 0.0,
        "judge_incorrect_rate": judge_counts["incorrect"] / jc_total if jc_total else 0.0,
        "mean_input_tokens": mean(inputs),
        "median_input_tokens": median(inputs),
        "mean_output_tokens": mean(outputs),
        "mean_cost_usd": mean(costs),
        "mean_judge_cost": mean(judge_costs),
        "total_cost_usd": total_cost_usd,
        "mean_wall_seconds": mean(walls),
        "mean_tool_calls": mean(tools),
    }


def _print_summary(summaries: dict[str, dict]) -> None:
    print("# Agent benchmark summary")
    print(
        "| condition | n | cov/not | right_unit | quote_ok | judge OK | judge partial | "
        "judge bad | refusal OK | false refusal | total cost | mean in tok | mean tools | mean wall s |"
    )
    print("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for cond in sorted(summaries):
        s = summaries[cond]
        if s.get("n", 0) == 0:
            print(f"| {cond} | 0 | | | | | | | | | | | | skipped={s.get('skipped_context', 0)} |")
            continue
        cov = f"{s.get('n_covered', 0)}/{s.get('n_not_covered', 0)}"
        print(
            f"| {cond} | {s['n']} | {cov} | {100*s['right_unit_rate']:.0f}% | {100*s['quote_verbatim_rate']:.0f}% | "
            f"{100*s['judge_correct_rate']:.0f}% | {100*s['judge_partial_rate']:.0f}% | "
            f"{100*s['judge_incorrect_rate']:.0f}% | {100*s['refusal_correct_rate']:.0f}% | "
            f"{100*s['false_refusal_rate']:.0f}% | ${s['total_cost_usd']:.4f} | "
            f"{s['mean_input_tokens']:.0f} | {s['mean_tool_calls']:.1f} | {s['mean_wall_seconds']:.1f} |"
        )


def _truncate(s: str, n: int = 200) -> str:
    s = s.replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


def dry_run(
    conditions: list[str],
    questions: list[dict],
    claude_bin: str,
    model: str,
) -> int:
    ver = "not found"
    try:
        r = subprocess.run(
            [claude_bin, "--version"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            check=False,
        )
        if r.returncode == 0:
            ver = (r.stdout or r.stderr or "").strip()
    except OSError:
        pass
    print(f"claude --version: {ver}")
    print()
    for cond in conditions:
        print(f"## Condition {cond}")
        for q in questions:
            est = prompt_token_estimate(cond, q)
            skip = cond == "C" and est > CONTEXT_TOKEN_LIMIT
            flag = " SKIP" if skip else ""
            print(f"- {q['id']}: approx prompt tokens {est:.0f}{flag}")
        if questions:
            q0 = questions[0]
            argv, _ = build_command(cond, q0, model, claude_bin=claude_bin)
            shown = []
            for part in argv:
                if part == "-p":
                    shown.append("-p")
                    continue
                if len(part) > 240:
                    shown.append(_truncate(part, 240))
                else:
                    shown.append(part)
            print(f"\nExample command ({q0['id']}):")
            print(" ".join(shlex.quote(p) for p in shown))
        print()
    return 0


def run_one(
    condition: str,
    question: dict,
    model: str,
    judge_model: str,
    claude_bin: str,
    units: dict,
) -> dict:
    rec = {
        "condition": condition,
        "question": question,
        "model": model,
    }
    try:
        if condition == "C":
            est = prompt_token_estimate("C", question)
            if est > CONTEXT_TOKEN_LIMIT:
                rec["status"] = "skipped_context"
                rec["approx_prompt_tokens"] = est
                return rec

        argv, _ = build_command(condition, question, model, claude_bin=claude_bin)
        try:
            lines, wall, rc = _run_claude(argv, REPO_ROOT, CALL_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            rec["status"] = "timeout"
            return rec

        parsed = parse_stream(lines)
        rec.update(
            {
                "status": "ok" if rc == 0 and not parsed.get("is_error") else "error",
                "returncode": rc,
                "wall_seconds": wall,
                "tool_calls": parsed.get("tool_calls", 0),
                "usage": parsed.get("usage") or {},
                "total_cost_usd": parsed.get("total_cost_usd"),
                "model_id": parsed.get("model_id"),
                "duration_ms": parsed.get("duration_ms"),
                "num_turns": parsed.get("num_turns"),
                "answer": parsed.get("result_text") or "",
            }
        )
        footer = parse_answer_footer(rec["answer"])
        rec["parsed_footer"] = footer
        grades = grade({"parsed_footer": footer}, question, units)
        rec["grades"] = grades

        if question.get("covered"):
            rec["judge"] = _judge(
                claude_bin,
                judge_model,
                question["question"],
                question.get("answer") or "",
                rec["answer"],
            )
        return rec
    except Exception as e:
        rec["status"] = "error"
        rec["error"] = f"{type(e).__name__}: {e}"
        return rec


def main() -> int:
    parser = argparse.ArgumentParser(description="Legal engine agent benchmark")
    parser.add_argument("--conditions", default="A,B,C", help="Comma-separated A,B,C")
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--judge-model", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="Comma-separated question ids")
    parser.add_argument("--jobs", type=int, default=2)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--claude", default="claude", dest="claude_bin")
    args = parser.parse_args()

    conditions = [c.strip().upper() for c in args.conditions.split(",") if c.strip()]
    judge_model = args.judge_model or args.model
    payload = load_questions()
    questions = payload["questions"]
    if args.ids:
        wanted = {x.strip() for x in args.ids.split(",")}
        questions = [q for q in questions if q["id"] in wanted]
    if args.limit is not None:
        questions = questions[: args.limit]

    if args.dry_run:
        return dry_run(conditions, questions, args.claude_bin, args.model)

    _setup_path()
    from cr_tax_kb.search import KnowledgeBase

    kb = KnowledgeBase()
    units = kb.units

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_path = args.out or (REPO_ROOT / "benchmark" / "results" / f"agent-{today}.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    claude_ver = ""
    try:
        r = subprocess.run(
            [args.claude_bin, "--version"],
            capture_output=True,
            text=True,
            check=False,
        )
        claude_ver = (r.stdout or r.stderr or "").strip()
    except OSError:
        claude_ver = "unavailable"

    records: list[dict] = []

    def _models_reported(recs: list[dict]) -> tuple[list[str], list[str]]:
        answer: set[str] = set()
        judge: set[str] = set()
        for r in recs:
            mid = r.get("model_id")
            if isinstance(mid, str) and mid:
                for part in mid.split(","):
                    p = part.strip()
                    if p:
                        answer.add(p)
            jmid = (r.get("judge") or {}).get("model_id")
            if isinstance(jmid, str) and jmid:
                for part in jmid.split(","):
                    p = part.strip()
                    if p:
                        judge.add(p)
        return sorted(answer), sorted(judge)

    def write_results() -> None:
        summaries = {c: _summarize(records, c) for c in conditions}
        models_reported, judge_models_reported = _models_reported(records)
        out_doc = {
            "metadata": {
                "date_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "git_commit": git_commit(),
                "claude_version": claude_ver,
                "model": args.model,
                "judge_model": judge_model,
                "models_reported": models_reported,
                "judge_models_reported": judge_models_reported,
                "conditions": conditions,
                "prompts": {
                    "SYS_A": SYS_A,
                    "SYS_B": SYS_B,
                    "SYS_C": SYS_C,
                    "JUDGE_PROMPT": JUDGE_PROMPT,
                },
            },
            "records": records,
            "summary": summaries,
        }
        out_path.write_text(
            json.dumps(out_doc, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    tasks = [(c, q) for c in conditions for q in questions]
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        futs = {
            pool.submit(run_one, c, q, args.model, judge_model, args.claude_bin, units): (c, q)
            for c, q in tasks
        }
        for fut in as_completed(futs):
            records.append(fut.result())
            write_results()

    summaries = {c: _summarize(records, c) for c in conditions}
    _print_summary(summaries)
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
