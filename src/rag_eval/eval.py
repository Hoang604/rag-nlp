from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import cast

from rag_eval.retrieval.engine import RetrievalEngine

DEFAULT_EVAL_PATH = Path("data/eval/retrieval.jsonl")
SET1_PATH = Path("data/eval/set1_lexical_api.json")
SET2_PATH = Path("data/eval/set2_conceptual.json")


@dataclass
class ExpectedTarget:
    doc_slug: str
    path_suffix: str


@dataclass
class EvalHit:
    rank: int
    path: str
    doc_slug: str
    found_in: str
    start_line: int
    end_line: int
    snippet: str
    matched: bool


@dataclass
class EvalCase:
    id: str
    test_set: str
    domain: str
    question: str
    query: str
    pattern: str
    expected: list[ExpectedTarget]
    is_regex: bool = False
    case_sensitive: bool = False
    doc_slugs: list[str] = field(default_factory=list)
    path_prefix: str | None = None
    note: str = ""
    rank: int | None = None
    found_in: str | None = None
    matched_path: str | None = None
    elapsed_ms: float | None = None
    top_hits: list[EvalHit] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> EvalCase:
        raw_slugs = d.get("doc_slugs")
        slugs = (
            [str(s) for s in raw_slugs if str(s).strip()]
            if isinstance(raw_slugs, list)
            else []
        )
        raw_exp = d.get("expected")
        exp_list: list[ExpectedTarget] = []
        if isinstance(raw_exp, list):
            for item in raw_exp:
                if isinstance(item, dict):
                    exp_list.append(
                        ExpectedTarget(
                            doc_slug=str(item.get("doc_slug") or ""),
                            path_suffix=str(item.get("path_suffix") or ""),
                        )
                    )
                elif isinstance(item, str) and item.strip():
                    full_p = item.strip()
                    matched_slug = next(
                        (s for s in slugs if full_p == s or full_p.startswith(s + ".")),
                        "",
                    )
                    if not matched_slug:
                        parts = full_p.split(".")
                        matched_slug = (
                            ".".join(parts[:3])
                            if parts[0] == "nextjs" and len(parts) >= 3
                            else ".".join(parts[:2])
                            if len(parts) >= 2
                            else parts[0]
                        )
                    suffix = (
                        full_p[len(matched_slug) + 1 :]
                        if full_p.startswith(matched_slug + ".")
                        else full_p
                    )
                    exp_list.append(
                        ExpectedTarget(
                            doc_slug=matched_slug,
                            path_suffix=suffix,
                        )
                    )
        raw_hits = d.get("top_hits")
        hit_list: list[EvalHit] = []
        if isinstance(raw_hits, list):
            for item in raw_hits:
                if isinstance(item, dict):
                    hit_list.append(
                        EvalHit(
                            rank=int(cast(int, item.get("rank") or 1)),
                            path=str(item.get("path") or ""),
                            doc_slug=str(item.get("doc_slug") or ""),
                            found_in=str(item.get("found_in") or "both"),
                            start_line=int(cast(int, item.get("start_line") or 1)),
                            end_line=int(cast(int, item.get("end_line") or 1)),
                            snippet=str(item.get("snippet") or ""),
                            matched=bool(item.get("matched", False)),
                        )
                    )
        raw_rank = d.get("rank")
        rank_val = int(raw_rank) if isinstance(raw_rank, int) else None
        raw_elapsed = d.get("elapsed_ms")
        elapsed_val = (
            float(raw_elapsed)
            if isinstance(raw_elapsed, (int, float))
            else None
        )
        return cls(
            id=str(d["id"]),
            test_set=str(d.get("test_set") or "custom"),
            domain=str(d.get("domain") or "general"),
            question=str(d.get("question") or ""),
            query=str(d.get("query") or ""),
            pattern=str(d.get("pattern") or ""),
            expected=exp_list,
            is_regex=bool(d.get("is_regex", False)),
            case_sensitive=bool(d.get("case_sensitive", False)),
            doc_slugs=slugs,
            path_prefix=str(d["path_prefix"]) if d.get("path_prefix") else None,
            note=str(d.get("note") or ""),
            rank=rank_val,
            found_in=str(d["found_in"]) if d.get("found_in") else None,
            matched_path=str(d["matched_path"]) if d.get("matched_path") else None,
            elapsed_ms=elapsed_val,
            top_hits=hit_list,
        )


def load_cases(path: Path = DEFAULT_EVAL_PATH) -> list[EvalCase]:
    if path.exists():
        lines = path.read_text(encoding="utf-8").splitlines()
        return [EvalCase.from_dict(json.loads(line)) for line in lines if line.strip()]

    cases: list[EvalCase] = []
    for src_path in (SET1_PATH, SET2_PATH):
        if src_path.exists():
            raw = json.loads(src_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                for item in raw:
                    if isinstance(item, dict):
                        cases.append(EvalCase.from_dict(item))
    return cases


def save_cases(cases: list[EvalCase], path: Path = DEFAULT_EVAL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(json.dumps(c.to_dict(), ensure_ascii=False) for c in cases) + "\n"
    path.write_text(body, encoding="utf-8")

    if path == DEFAULT_EVAL_PATH:
        set1_cases = [c.to_dict() for c in cases if c.test_set == "TS1-Lexical-API"]
        set2_cases = [c.to_dict() for c in cases if c.test_set == "TS2-Conceptual"]
        if SET1_PATH.exists() and set1_cases:
            SET1_PATH.write_text(
                json.dumps(set1_cases, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if SET2_PATH.exists() and set2_cases:
            SET2_PATH.write_text(
                json.dumps(set2_cases, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )


def _matches_target(doc_slug: str, path: str, target: ExpectedTarget) -> bool:
    if target.doc_slug and doc_slug != target.doc_slug:
        return False
    sfx = target.path_suffix
    full = (
        f"{target.doc_slug}.{sfx}"
        if target.doc_slug and not sfx.startswith(target.doc_slug)
        else sfx
    )
    return (
        path in (full, sfx)
        or path.startswith((full + ".", sfx + "."))
        or path.endswith("." + sfx)
        or (f".{sfx}." in f".{path}.")
    )


async def run_case(
    engine: RetrievalEngine,
    case: EvalCase,
    *,
    limit: int = 10,
    rerank: bool = False,
) -> EvalCase:
    t0 = time.perf_counter()
    res = await engine.search_venn(
        query=case.query,
        pattern=case.pattern,
        limit=limit,
        rerank=rerank,
        doc_slugs=case.doc_slugs or None,
        path_prefix=case.path_prefix or None,
        is_regex=case.is_regex,
        case_sensitive=case.case_sensitive,
        order_by_reading_order=False,
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 1)

    flat: list[tuple[int, str, str, str, int, int, str]] = []
    for grp in res.groups:
        for prov in grp.provisions:
            flat.append(
                (
                    prov.rank,
                     grp.doc_slug,
                    prov.path,
                    prov.found_in,
                    prov.start_line,
                    prov.end_line,
                    prov.text,
                )
            )
    flat.sort(key=lambda item: item[0])

    matched_targets: set[int] = set()
    completion_rank: int | None = None
    completion_found_in: str | None = None
    completion_path: str | None = None
    top_hits: list[EvalHit] = []

    for r_idx, (_, doc_slug, path, found_in, start_line, end_line, text) in enumerate(
        flat[:limit], start=1
    ):
        hit_matched = False
        for t_idx, target in enumerate(case.expected):
            if _matches_target(doc_slug, path, target):
                hit_matched = True
                if t_idx not in matched_targets:
                    matched_targets.add(t_idx)
                    if (
                        completion_rank is None
                        and case.expected
                        and len(matched_targets) == len(case.expected)
                    ):
                        completion_rank = r_idx
                        completion_found_in = found_in
                        completion_path = path

        top_hits.append(
            EvalHit(
                rank=r_idx,
                path=path,
                doc_slug=doc_slug,
                found_in=found_in,
                start_line=start_line,
                end_line=end_line,
                snippet=text[:240],
                matched=hit_matched,
            )
        )

    case.rank = completion_rank
    case.found_in = completion_found_in
    case.matched_path = completion_path
    case.elapsed_ms = elapsed_ms
    case.top_hits = top_hits
    return case


async def run_all(
    engine: RetrievalEngine,
    path: Path = DEFAULT_EVAL_PATH,
    *,
    limit: int = 10,
    rerank: bool = False,
) -> list[EvalCase]:
    cases = load_cases(path)
    for case in cases:
        await run_case(engine, case, limit=limit, rerank=rerank)
    save_cases(cases, path)
    return cases
