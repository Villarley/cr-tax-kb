#!/usr/bin/env python3
"""Retrieval benchmark for the legal engine (stdlib only, no network)."""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUESTIONS_PATH = REPO_ROOT / "benchmark" / "questions.json"
LAWS_ROOT = REPO_ROOT / "laws"
CACHE_DIR = LAWS_ROOT / ".cache"


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


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    k = (len(ordered) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(ordered) - 1)
    if f == c:
        return float(ordered[f])
    return ordered[f] + (ordered[c] - ordered[f]) * (k - f)


def load_questions() -> dict:
    return json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))


def _recall_at_k(hit_ids: list[str], expected: list[str], k: int) -> bool:
    top = hit_ids[:k]
    return any(e in top for e in expected)


def _mrr_at_k(hit_ids: list[str], expected: list[str], k: int) -> float:
    top = hit_ids[:k]
    exp = set(expected)
    for i, uid in enumerate(top, start=1):
        if uid in exp:
            return 1.0 / i
    return 0.0


def _metric_bundle(covered: list[dict], kb, k_hits: int, area_filter: bool) -> dict:
    recalls = {1: [], 3: [], 5: []}
    mrrs = []
    by_area: dict[str, list[dict]] = {}
    by_style: dict[str, list[dict]] = {}
    for q in covered:
        area = q["area"]
        if area_filter:
            hits = kb.search_law(q["question"], k_hits, area=area)
        else:
            hits = kb.search_law(q["question"], k_hits)
        ids = [h["id"] for h in hits]
        exp = q["expected"]
        for kk in (1, 3, 5):
            recalls[kk].append(_recall_at_k(ids, exp, kk))
        mrrs.append(_mrr_at_k(ids, exp, k_hits))
        row = {"id": q["id"], "hit_ids": ids, "expected": exp}
        by_area.setdefault(area, []).append(row)
        by_style.setdefault(q["style"], []).append(row)

    def agg(rows: list[dict]) -> dict:
        if not rows:
            return {"n": 0, "recall@1": 0.0, "recall@3": 0.0, "recall@5": 0.0, f"mrr@{k_hits}": 0.0}
        ids_map = {r["id"]: r for r in rows}
        subset = [q for q in covered if q["id"] in ids_map]
        r1, r3, r5, mrr_list = [], [], [], []
        for q in subset:
            if area_filter:
                hits = kb.search_law(q["question"], k_hits, area=q["area"])
            else:
                hits = kb.search_law(q["question"], k_hits)
            ids = [h["id"] for h in hits]
            exp = q["expected"]
            r1.append(_recall_at_k(ids, exp, 1))
            r3.append(_recall_at_k(ids, exp, 3))
            r5.append(_recall_at_k(ids, exp, 5))
            mrr_list.append(_mrr_at_k(ids, exp, k_hits))
        n = len(subset)
        return {
            "n": n,
            "recall@1": sum(r1) / n if n else 0.0,
            "recall@3": sum(r3) / n if n else 0.0,
            "recall@5": sum(r5) / n if n else 0.0,
            f"mrr@{k_hits}": sum(mrr_list) / n if n else 0.0,
        }

    n = len(covered)
    return {
        "n": n,
        "recall@1": sum(recalls[1]) / n if n else 0.0,
        "recall@3": sum(recalls[3]) / n if n else 0.0,
        "recall@5": sum(recalls[5]) / n if n else 0.0,
        f"mrr@{k_hits}": sum(mrrs) / n if n else 0.0,
        "by_area": {a: agg(rows) for a, rows in sorted(by_area.items())},
        "by_style": {s: agg(rows) for s, rows in sorted(by_style.items())},
    }


def _token_stats(values: list[float]) -> dict:
    if not values:
        return {"mean": 0.0, "median": 0.0, "p95": 0.0, "max": 0.0}
    out = {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "max": max(values),
    }
    if len(values) >= 2:
        out["p95"] = percentile(values, 95)
    else:
        out["p95"] = values[0]
    return out


def _top1_scores(kb, questions: list[dict]) -> list[float]:
    scores = []
    for q in questions:
        hits = kb.search_law(q["question"], 1)
        scores.append(hits[0]["score"] if hits else 0.0)
    return scores


def _score_summary(scores: list[float]) -> dict:
    if not scores:
        return {"mean": 0.0, "min": 0.0, "max": 0.0}
    return {"mean": statistics.mean(scores), "min": min(scores), "max": max(scores)}


def _norm_id_from_unit(unit_id: str) -> str:
    return unit_id.split(":", 1)[0]


def _scraping_baseline() -> dict:
    from cr_tax_kb import laws

    per_norm = []
    totals = {"text_md": 0.0, "html_raw": 0.0, "html_lines": 0.0}
    for norm_path in sorted(LAWS_ROOT.glob("*/norm.json")):
        meta = json.loads(norm_path.read_text(encoding="utf-8"))
        nid = meta["id"]
        row = {"norm_id": nid, "version_date": meta.get("version_date"), "units": meta.get("units")}
        text_path = LAWS_ROOT / nid / "text.md"
        if text_path.is_file():
            tok = approx_tokens(text_path.read_text(encoding="utf-8"))
            row["text_md_approx_tokens"] = tok
            totals["text_md"] += tok
        cache = CACHE_DIR / f"{nid}.html"
        if cache.is_file():
            raw = cache.read_text(encoding="utf-8", errors="replace")
            row["html_raw_approx_tokens"] = approx_tokens(raw)
            totals["html_raw"] += row["html_raw_approx_tokens"]
            lines = laws.html_to_lines(raw)
            joined = "\n".join(lines)
            row["html_lines_approx_tokens"] = approx_tokens(joined)
            totals["html_lines"] += row["html_lines_approx_tokens"]
        per_norm.append(row)
    return {"per_norm": per_norm, "total_approx_tokens": totals}


def run(k_latency_reps: int = 10) -> dict:
    _setup_path()
    from cr_tax_kb.search import KnowledgeBase, format_units

    t0 = time.perf_counter()
    kb = KnowledgeBase()
    index_build_ms = (time.perf_counter() - t0) * 1000.0

    payload = load_questions()
    questions = payload["questions"]
    covered = [q for q in questions if q.get("covered")]
    not_covered = [q for q in questions if not q.get("covered")]

    retrieval_no_area = _metric_bundle(covered, kb, 10, area_filter=False)
    retrieval_area = _metric_bundle(covered, kb, 10, area_filter=True)

    # Latency: one warm-up search per question, then k_latency_reps timed runs.
    search_ms: list[float] = []
    get_unit_ms: list[float] = []
    for q in questions:
        kb.search_law(q["question"], 5)
        for _ in range(k_latency_reps):
            t1 = time.perf_counter()
            kb.search_law(q["question"], 5)
            search_ms.append((time.perf_counter() - t1) * 1000.0)
        if q.get("covered") and q.get("expected"):
            uid = q["expected"][0]
            norm_id, _, art = uid.partition(":")
            kb.get_unit(norm_id, uid)
            for _ in range(k_latency_reps):
                t1 = time.perf_counter()
                kb.get_unit(norm_id, uid)
                get_unit_ms.append((time.perf_counter() - t1) * 1000.0)

    latency = {
        "search_law_k5": {
            "p50_ms": percentile(search_ms, 50),
            "p95_ms": percentile(search_ms, 95),
            "runs": len(search_ms),
        },
        "get_unit": {
            "p50_ms": percentile(get_unit_ms, 50),
            "p95_ms": percentile(get_unit_ms, 95),
            "runs": len(get_unit_ms),
        },
    }

    search_fmt_tokens = []
    for q in questions:
        hits = kb.search_law(q["question"], 5)
        search_fmt_tokens.append(approx_tokens(format_units(hits)))

    expected_fmt_tokens = []
    for q in covered:
        for uid in q["expected"]:
            u = kb.units.get(uid)
            if u:
                expected_fmt_tokens.append(approx_tokens(format_units([u.__dict__])))

    tokens = {
        "format_units_search_k5": _token_stats(search_fmt_tokens),
        "format_units_expected_units": {
            "mean": statistics.mean(expected_fmt_tokens) if expected_fmt_tokens else 0.0,
            "median": statistics.median(expected_fmt_tokens) if expected_fmt_tokens else 0.0,
            "max": max(expected_fmt_tokens) if expected_fmt_tokens else 0.0,
        },
    }

    covered_top1 = _top1_scores(kb, covered)
    not_covered_top1 = _top1_scores(kb, not_covered)
    refusal_study = {
        "covered_top1_score": _score_summary(covered_top1),
        "not_covered_top1_score": _score_summary(not_covered_top1),
    }

    scraping = _scraping_baseline()

    whole_norm_tokens = []
    engine_tokens = []
    for q in covered:
        if not q.get("expected"):
            continue
        nid = _norm_id_from_unit(q["expected"][0])
        text_path = LAWS_ROOT / nid / "text.md"
        if text_path.is_file():
            whole_norm_tokens.append(approx_tokens(text_path.read_text(encoding="utf-8")))
        hits = kb.search_law(q["question"], 5)
        eng = approx_tokens(format_units(hits))
        u = kb.units.get(q["expected"][0])
        if u:
            eng += approx_tokens(format_units([u.__dict__]))
        engine_tokens.append(eng)

    token_comparison = {
        "whole_relevant_norm_text_md_mean_approx_tokens": (
            statistics.mean(whole_norm_tokens) if whole_norm_tokens else 0.0
        ),
        "engine_search_k5_plus_one_unit_mean_approx_tokens": (
            statistics.mean(engine_tokens) if engine_tokens else 0.0
        ),
    }

    norms_meta = {}
    for norm_path in sorted(LAWS_ROOT.glob("*/norm.json")):
        meta = json.loads(norm_path.read_text(encoding="utf-8"))
        norms_meta[meta["id"]] = {
            "version_date": meta.get("version_date"),
            "units": meta.get("units"),
            "title": meta.get("title"),
        }

    return {
        "metadata": {
            "date_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "git_commit": git_commit(),
            "python_version": sys.version.split()[0],
            "platform": platform.platform(),
            "questions_version": payload.get("version"),
            "questions_status": payload.get("status"),
            "index_build_ms": round(index_build_ms, 2),
            "norms": norms_meta,
        },
        "counts": {
            "questions_total": len(questions),
            "questions_covered": len(covered),
            "questions_not_covered": len(not_covered),
        },
        "retrieval": {
            "hits_k": 10,
            "no_area_filter": retrieval_no_area,
            "with_area_filter": retrieval_area,
        },
        "latency": latency,
        "approx_tokens": tokens,
        "refusal_score_study": refusal_study,
        "scraping_baseline": scraping,
        "token_comparison": token_comparison,
    }


def _pct(x: float) -> str:
    return f"{100.0 * x:.1f}%"


def _print_summary(data: dict) -> None:
    meta = data["metadata"]
    print(f"# Retrieval benchmark")
    print(f"- Date (UTC): {meta['date_utc']}")
    print(f"- Git: {meta['git_commit']}")
    print(f"- Index build: {meta['index_build_ms']:.1f} ms")
    print(f"- Questions: {data['counts']['questions_covered']} covered / {data['counts']['questions_total']} total")
    print()

    def table_retrieval(label: str, block: dict) -> None:
        print(f"## {label}")
        print("| metric | value |")
        print("| --- | --- |")
        print(f"| recall@1 | {_pct(block['recall@1'])} |")
        print(f"| recall@3 | {_pct(block['recall@3'])} |")
        print(f"| recall@5 | {_pct(block['recall@5'])} |")
        print(f"| MRR@10 | {block['mrr@10']:.3f} |")
        print()

    r = data["retrieval"]
    table_retrieval("Retrieval (no area filter)", r["no_area_filter"])
    table_retrieval("Retrieval (area filter)", r["with_area_filter"])

    lat = data["latency"]
    print("## Latency (ms)")
    print("| op | p50 | p95 |")
    print("| --- | --- | --- |")
    s = lat["search_law_k5"]
    g = lat["get_unit"]
    print(f"| search_law k=5 | {s['p50_ms']:.3f} | {s['p95_ms']:.3f} |")
    print(f"| get_unit | {g['p50_ms']:.3f} | {g['p95_ms']:.3f} |")
    print()

    tok = data["approx_tokens"]
    print("## approx_tokens (format_units)")
    print("| source | mean | median | p95 | max |")
    print("| --- | --- | --- | --- | --- |")
    fs = tok["format_units_search_k5"]
    fe = tok["format_units_expected_units"]
    print(
        f"| search k=5 | {fs['mean']:.0f} | {fs['median']:.0f} | {fs.get('p95', 0):.0f} | {fs['max']:.0f} |"
    )
    print(f"| expected units | {fe['mean']:.0f} | {fe['median']:.0f} | | {fe['max']:.0f} |")
    print()

    rs = data["refusal_score_study"]
    print("## Top-1 score (refusal study, no threshold)")
    print("| group | mean | min | max |")
    print("| --- | --- | --- | --- |")
    c = rs["covered_top1_score"]
    n = rs["not_covered_top1_score"]
    print(f"| covered | {c['mean']:.3f} | {c['min']:.3f} | {c['max']:.3f} |")
    print(f"| not covered | {n['mean']:.3f} | {n['min']:.3f} | {n['max']:.3f} |")
    print()

    tc = data["token_comparison"]
    print("## Tokens: whole norm vs engine")
    print(f"- Mean whole norm text.md: {tc['whole_relevant_norm_text_md_mean_approx_tokens']:.0f}")
    print(f"- Mean engine (search k=5 + one unit): {tc['engine_search_k5_plus_one_unit_mean_approx_tokens']:.0f}")
    print()


def main() -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    default_out = REPO_ROOT / "benchmark" / "results" / f"retrieval-{today}.json"
    parser = argparse.ArgumentParser(description="Legal engine retrieval benchmark")
    parser.add_argument("--out", type=Path, default=default_out, help="Write JSON results here")
    args = parser.parse_args()

    data = run()
    _print_summary(data)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
