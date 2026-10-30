"""Run retrieval evaluation and ablation study on data/eval/retrieval.jsonl."""

from __future__ import annotations

import asyncio
import json
import math
import statistics
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Final, Literal, cast

import asyncpg
from pydantic import BaseModel, ConfigDict, Field

from rag_eval.db.connection import close_db_pool, get_db_pool
from rag_eval.db.repositories import CorpusRepository
from rag_eval.retrieval.confidence import compute_search_confidence
from rag_eval.retrieval.embedder import SentenceTransformerQueryEmbedder
from rag_eval.retrieval.engine import RetrievalEngine
from rag_eval.retrieval.reranker import CrossEncoderReranker
from rag_eval.schemas import (
    HybridSearchQuery,
    SearchHitDTO,
    UnifiedSearchResult,
)

FOUND_IN_ORDER: Final[tuple[Literal["both", "semantic_only", "verbatim_only"], ...]] = (
    "both",
    "semantic_only",
    "verbatim_only",
)

EVAL_DIR: Final = Path("data/eval")
SET1_JSON: Final = EVAL_DIR / "set1_lexical_api.json"
SET2_JSON: Final = EVAL_DIR / "set2_conceptual.json"
RETRIEVAL_JSONL: Final = EVAL_DIR / "retrieval.jsonl"
RESULTS_JSON: Final = EVAL_DIR / "ablation_results.json"
LIMIT: Final = 10
RRF_K: Final = 60

TestSetName = Literal["TS1-Lexical-API", "TS2-Conceptual"]
DomainName = Literal["nextjs", "nodejs"]
FoundIn = Literal["both", "semantic_only", "verbatim_only", "missed"]


class EvalCase(BaseModel):
    """One question, the first `hybrid_search` call an agent makes for it, and the chunks that answer it."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^e\d{3,}$")
    test_set: TestSetName
    domain: DomainName
    question: str = Field(min_length=1)
    query: str = Field(min_length=1)
    pattern: str = Field(min_length=1)
    is_regex: bool = False
    case_sensitive: bool = False
    doc_slugs: list[str] = Field(default_factory=list)
    path_prefix: str | None = None
    expected: list[str] = Field(min_length=1)
    note: str | None = None


@dataclass(frozen=True)
class CaseEvalOutcome:
    id: str
    test_set: TestSetName
    domain: DomainName
    found: bool
    found_in: FoundIn
    rank_10: int | None
    hit_1: bool
    hit_5: bool
    hit_10: bool
    recall_5: float
    recall_10: float
    mrr_10: float
    ndcg_10: float
    latency_ms: float
    confidence: str
    matched_path: str | None


def matches_target(path: str, target: str) -> bool:
    return path == target or path.startswith(target + ".")


def matched_expected_targets(paths: list[str], expected: list[str]) -> int:
    matched = 0
    for e in expected:
        if any(matches_target(p, e) for p in paths):
            matched += 1
    return matched


def compute_ndcg_at_k(ranked_paths: list[str], expected: list[str], k: int = 10) -> float:
    dcg = 0.0
    used_expected: set[str] = set()
    for idx, p in enumerate(ranked_paths[:k], start=1):
        hit_target = None
        for e in expected:
            if matches_target(p, e) and e not in used_expected:
                hit_target = e
                break
        if hit_target is not None:
            used_expected.add(hit_target)
            dcg += 1.0 / math.log2(idx + 1)

    ideal_hits = min(len(expected), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    return (dcg / idcg) if idcg > 0 else 0.0


def exact_mcnemar_p(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    total = sum(math.comb(n, i) for i in range(k + 1)) * (0.5**n)
    return min(1.0, 2.0 * total)


def score_ranked_list(
    case: EvalCase,
    ranked_paths: list[str],
    found_in_map: dict[str, FoundIn],
    latency_ms: float,
    confidence: str,
) -> CaseEvalOutcome:
    top_10 = ranked_paths[:LIMIT]
    top_5 = ranked_paths[:5]
    n_exp = len(case.expected)

    completion_rank: int | None = None
    matched_path: str | None = None
    matched_top10: set[str] = set()
    for idx, p in enumerate(top_10, start=1):
        for e in case.expected:
            if matches_target(p, e):
                matched_top10.add(e)
        if len(matched_top10) == n_exp:
            completion_rank = idx
            matched_path = p
            break

    all_found = False
    found_channel: FoundIn = "missed"
    matched_all: set[str] = set()
    for p in ranked_paths:
        for e in case.expected:
            if matches_target(p, e):
                matched_all.add(e)
        if len(matched_all) == n_exp:
            all_found = True
            found_channel = found_in_map.get(p, "semantic_only")
            if matched_path is None:
                matched_path = p
            break

    hit_1 = completion_rank == 1
    hit_5 = completion_rank is not None and completion_rank <= 5
    hit_10 = completion_rank is not None and completion_rank <= 10

    r5 = matched_expected_targets(top_5, case.expected) / n_exp
    r10 = matched_expected_targets(top_10, case.expected) / n_exp
    mrr10 = (1.0 / completion_rank) if completion_rank is not None else 0.0
    ndcg10 = compute_ndcg_at_k(top_10, case.expected, k=10)

    return CaseEvalOutcome(
        id=case.id,
        test_set=case.test_set,
        domain=case.domain,
        found=all_found,
        found_in=found_channel if all_found else "missed",
        rank_10=completion_rank,
        hit_1=hit_1,
        hit_5=hit_5,
        hit_10=hit_10,
        recall_5=r5,
        recall_10=r10,
        mrr_10=mrr10,
        ndcg_10=ndcg10,
        latency_ms=latency_ms,
        confidence=confidence,
        matched_path=matched_path,
    )


def flatten_venn_result(res: UnifiedSearchResult) -> tuple[list[str], dict[str, FoundIn]]:
    provisions = [p for g in res.groups for p in g.provisions]
    ordered: list[str] = []
    found_in_map: dict[str, FoundIn] = {}
    for ch in FOUND_IN_ORDER:
        bucket = sorted((p for p in provisions if p.found_in == ch), key=lambda x: x.rank)
        for p in bucket:
            if p.path not in found_in_map:
                ordered.append(p.path)
                found_in_map[p.path] = ch
    return ordered, found_in_map


def build_and_load_cases() -> list[EvalCase]:
    raw_1 = json.loads(SET1_JSON.read_text(encoding="utf-8"))
    raw_2 = json.loads(SET2_JSON.read_text(encoding="utf-8"))
    combined = [*raw_1, *raw_2]
    cases = [EvalCase.model_validate(item) for item in combined]
    cases.sort(key=lambda c: c.id)
    lines = [json.dumps(c.model_dump(mode="json"), ensure_ascii=False) + "\n" for c in cases]
    RETRIEVAL_JSONL.write_text("".join(lines), encoding="utf-8")
    return cases


async def search_dense_only(
    pool: asyncpg.Pool,
    q_vec: list[float],
    doc_slugs: list[str] | None,
    path_prefix: str | None,
    limit: int = LIMIT,
) -> list[SearchHitDTO]:
    rows = await pool.fetch(
        """
        SELECT
            c.id AS chunk_id,
            d.doc_slug,
            d.title AS doc_title,
            c.path::text AS path,
            c.start_line,
            c.end_line,
            c.verbatim_text,
            c.contextualized_text,
            c.metadata,
            (1.0 - (c.embedding <=> $1::vector))::DOUBLE PRECISION AS similarity,
            ROW_NUMBER() OVER (ORDER BY c.embedding <=> $1::vector ASC) AS rank_dense
        FROM chunks c
        JOIN documents d ON c.document_id = d.id
        WHERE c.embedding IS NOT NULL
          AND ($2::text[] IS NULL OR cardinality($2::text[]) = 0 OR d.doc_slug = ANY($2::text[]))
          AND ($3::ltree IS NULL OR c.path <@ $3::ltree)
        ORDER BY c.embedding <=> $1::vector ASC
        LIMIT $4
        """,
        q_vec,
        doc_slugs or None,
        path_prefix,
        limit,
    )
    hits: list[SearchHitDTO] = []
    for r in rows:
        meta = json.loads(r["metadata"]) if isinstance(r["metadata"], str) else dict(r["metadata"])
        hits.append(
            SearchHitDTO(
                chunk_id=r["chunk_id"],
                doc_slug=str(r["doc_slug"]),
                doc_title=str(r["doc_title"]),
                path=str(r["path"]),
                start_line=int(r["start_line"]),
                end_line=int(r["end_line"]),
                verbatim_text=str(r["verbatim_text"]),
                contextualized_text=str(r["contextualized_text"]),
                metadata=meta,
                score=float(r["similarity"]),
                dense_rank=int(r["rank_dense"]),
                sparse_rank=999,
                dense_similarity=float(r["similarity"]),
            )
        )
    return hits


def summarize_outcomes(outcomes: list[CaseEvalOutcome]) -> dict[str, object]:
    n = len(outcomes)
    if n == 0:
        return {}
    lats = [o.latency_ms for o in outcomes]
    lats_sorted = sorted(lats)
    p50 = statistics.median(lats_sorted)
    p95_idx = min(len(lats_sorted) - 1, math.ceil(0.95 * len(lats_sorted)) - 1)
    p95 = lats_sorted[p95_idx]

    conf_counts = {"none": 0, "low": 0, "medium": 0, "high": 0}
    venn_counts = {"both": 0, "semantic_only": 0, "verbatim_only": 0, "missed": 0}
    for o in outcomes:
        conf_counts[o.confidence] = conf_counts.get(o.confidence, 0) + 1
        venn_counts[o.found_in] = venn_counts.get(o.found_in, 0) + 1

    return {
        "n": n,
        "found_pct": sum(1 for o in outcomes if o.found) / n * 100.0,
        "hit_1_pct": sum(1 for o in outcomes if o.hit_1) / n * 100.0,
        "hit_5_pct": sum(1 for o in outcomes if o.hit_5) / n * 100.0,
        "hit_10_pct": sum(1 for o in outcomes if o.hit_10) / n * 100.0,
        "recall_5_pct": sum(o.recall_5 for o in outcomes) / n * 100.0,
        "recall_10_pct": sum(o.recall_10 for o in outcomes) / n * 100.0,
        "mrr_10_pct": sum(o.mrr_10 for o in outcomes) / n * 100.0,
        "ndcg_10_pct": sum(o.ndcg_10 for o in outcomes) / n * 100.0,
        "latency_mean_ms": sum(lats) / n,
        "latency_p50_ms": p50,
        "latency_p95_ms": p95,
        "venn_counts": venn_counts,
        "confidence_counts": conf_counts,
    }


async def main() -> None:
    cases = build_and_load_cases()
    print(f"Loaded and wrote {len(cases)} cases to {RETRIEVAL_JSONL}")

    pool = await get_db_pool()
    try:
        repo = CorpusRepository(pool)
        embedder = SentenceTransformerQueryEmbedder()
        reranker = CrossEncoderReranker(max_cache_size=0)  # Disable cache for honest latency measurement
        _ = await embedder.embed_query("warmup query")
        await reranker.warm()
        engine_no_rerank = RetrievalEngine(
            pool=pool, embedder=embedder, reranker=reranker, rerank_by_default=False
        )
        engine_rerank = RetrievalEngine(
            pool=pool, embedder=embedder, reranker=reranker, rerank_by_default=True
        )

        configs_outcomes: dict[str, list[CaseEvalOutcome]] = {
            "1_sparse_only": [],
            "2_dense_only": [],
            "4_hybrid_rrf_no_rerank": [],
            "5_hybrid_rrf_rerank": [],
            "6_full_dual_venn": [],
            "6b_dual_venn_no_rerank": [],
        }

        for idx, case in enumerate(cases, start=1):
            slugs = case.doc_slugs or None
            prefix = case.path_prefix

            # 1. Sparse FTS Only
            t0 = time.perf_counter()
            sparse_hits = await repo.chunks.hybrid_search(
                HybridSearchQuery(
                    query_text=case.query,
                    query_vector=None,
                    match_limit=LIMIT,
                    rrf_k=RRF_K,
                    target_documents=slugs,
                    path_prefix=prefix,
                    ts_config="simple",
                )
            )
            lat_1 = (time.perf_counter() - t0) * 1000.0
            paths_1 = [h.path for h in sparse_hits[:LIMIT]]
            fmap_1: dict[str, FoundIn] = {p: "semantic_only" for p in paths_1}
            configs_outcomes["1_sparse_only"].append(
                score_ranked_list(case, paths_1, fmap_1, lat_1, compute_search_confidence(sparse_hits[:LIMIT]))
            )

            # 2. Dense Vector Only
            t0 = time.perf_counter()
            q_vec = await embedder.embed_query(case.query)
            assert q_vec is not None
            dense_hits = await search_dense_only(pool, q_vec, slugs, prefix, limit=LIMIT)
            lat_2 = (time.perf_counter() - t0) * 1000.0
            paths_2 = [h.path for h in dense_hits]
            fmap_2: dict[str, FoundIn] = {p: "semantic_only" for p in paths_2}
            configs_outcomes["2_dense_only"].append(
                score_ranked_list(case, paths_2, fmap_2, lat_2, compute_search_confidence(dense_hits))
            )

            # 4. AST + Hybrid RRF w/o Rerank
            t0 = time.perf_counter()
            res_4 = await engine_no_rerank.search(
                query=case.query,
                limit=LIMIT,
                rerank=False,
                doc_slugs=slugs,
                path_prefix=prefix,
            )
            lat_4 = (time.perf_counter() - t0) * 1000.0
            paths_4 = [h.path for h in res_4.hits]
            fmap_4: dict[str, FoundIn] = {p: "semantic_only" for p in paths_4}
            configs_outcomes["4_hybrid_rrf_no_rerank"].append(
                score_ranked_list(case, paths_4, fmap_4, lat_4, res_4.confidence)
            )

            # 5. AST + Hybrid RRF + Cross-Encoder Rerank
            t0 = time.perf_counter()
            res_5 = await engine_rerank.search(
                query=case.query,
                limit=LIMIT,
                rerank=True,
                rerank_pool=10,
                doc_slugs=slugs,
                path_prefix=prefix,
            )
            lat_5 = (time.perf_counter() - t0) * 1000.0
            paths_5 = [h.path for h in res_5.hits]
            fmap_5: dict[str, FoundIn] = {p: "semantic_only" for p in paths_5}
            configs_outcomes["5_hybrid_rrf_rerank"].append(
                score_ranked_list(case, paths_5, fmap_5, lat_5, res_5.confidence)
            )

            # 6. Full Dual-Channel Venn (with Rerank)
            t0 = time.perf_counter()
            res_6 = await engine_rerank.search_venn(
                query=case.query,
                pattern=case.pattern,
                limit=LIMIT,
                rerank=True,
                rerank_pool=10,
                doc_slugs=slugs,
                path_prefix=prefix,
                is_regex=case.is_regex,
                case_sensitive=case.case_sensitive,
            )
            lat_6 = (time.perf_counter() - t0) * 1000.0
            paths_6, fmap_6 = flatten_venn_result(res_6)
            configs_outcomes["6_full_dual_venn"].append(
                score_ranked_list(case, paths_6, fmap_6, lat_6, res_6.confidence)
            )

            # 6b. Full Dual-Channel Venn (w/o Rerank)
            t0 = time.perf_counter()
            res_6b = await engine_no_rerank.search_venn(
                query=case.query,
                pattern=case.pattern,
                limit=LIMIT,
                rerank=False,
                doc_slugs=slugs,
                path_prefix=prefix,
                is_regex=case.is_regex,
                case_sensitive=case.case_sensitive,
            )
            lat_6b = (time.perf_counter() - t0) * 1000.0
            paths_6b, fmap_6b = flatten_venn_result(res_6b)
            configs_outcomes["6b_dual_venn_no_rerank"].append(
                score_ranked_list(case, paths_6b, fmap_6b, lat_6b, res_6b.confidence)
            )

            if idx % 20 == 0:
                print(f"Evaluated {idx}/{len(cases)} cases...")

        # Summarize all configurations
        summary_report: dict[str, object] = {"configs": {}, "mcnemar": {}, "per_testset_full": {}}
        configs_dict = cast(dict[str, object], summary_report["configs"])

        for cfg_name, out_list in configs_outcomes.items():
            ts1 = [o for o in out_list if o.test_set == "TS1-Lexical-API"]
            ts2 = [o for o in out_list if o.test_set == "TS2-Conceptual"]
            njs = [o for o in out_list if o.domain == "nextjs"]
            ndjs = [o for o in out_list if o.domain == "nodejs"]
            configs_dict[cfg_name] = {
                "overall": summarize_outcomes(out_list),
                "TS1-Lexical-API": summarize_outcomes(ts1),
                "TS2-Conceptual": summarize_outcomes(ts2),
                "nextjs": summarize_outcomes(njs),
                "nodejs": summarize_outcomes(ndjs),
                "TS1_nextjs": summarize_outcomes([o for o in ts1 if o.domain == "nextjs"]),
                "TS1_nodejs": summarize_outcomes([o for o in ts1 if o.domain == "nodejs"]),
                "TS2_nextjs": summarize_outcomes([o for o in ts2 if o.domain == "nextjs"]),
                "TS2_nodejs": summarize_outcomes([o for o in ts2 if o.domain == "nodejs"]),
                "outcomes": [asdict(o) for o in out_list],
            }

        # McNemar exact tests between pairs of configurations
        pairs = [
            ("1_sparse_only", "2_dense_only"),
            ("4_hybrid_rrf_no_rerank", "1_sparse_only"),
            ("4_hybrid_rrf_no_rerank", "2_dense_only"),
            ("5_hybrid_rrf_rerank", "4_hybrid_rrf_no_rerank"),
            ("6_full_dual_venn", "5_hybrid_rrf_rerank"),
            ("6_full_dual_venn", "4_hybrid_rrf_no_rerank"),
            ("6_full_dual_venn", "6b_dual_venn_no_rerank"),
        ]
        mcnemar_dict = cast(dict[str, object], summary_report["mcnemar"])
        for a_name, b_name in pairs:
            out_a = configs_outcomes[a_name]
            out_b = configs_outcomes[b_name]
            # Found (or Hit@10)
            f_better = sum(1 for a, b in zip(out_a, out_b, strict=True) if a.found and not b.found)
            f_worse = sum(1 for a, b in zip(out_a, out_b, strict=True) if not a.found and b.found)
            # Hit@1
            h1_better = sum(1 for a, b in zip(out_a, out_b, strict=True) if a.hit_1 and not b.hit_1)
            h1_worse = sum(1 for a, b in zip(out_a, out_b, strict=True) if not a.hit_1 and b.hit_1)
            # Hit@5
            h5_better = sum(1 for a, b in zip(out_a, out_b, strict=True) if a.hit_5 and not b.hit_5)
            h5_worse = sum(1 for a, b in zip(out_a, out_b, strict=True) if not a.hit_5 and b.hit_5)
            mcnemar_dict[f"{a_name}_vs_{b_name}"] = {
                "found": {"better": f_better, "worse": f_worse, "p": exact_mcnemar_p(f_better, f_worse)},
                "hit_1": {"better": h1_better, "worse": h1_worse, "p": exact_mcnemar_p(h1_better, h1_worse)},
                "hit_5": {"better": h5_better, "worse": h5_worse, "p": exact_mcnemar_p(h5_better, h5_worse)},
            }

        RESULTS_JSON.write_text(json.dumps(summary_report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote full ablation results to {RESULTS_JSON}")

        # Print concise table
        for cfg_name in configs_outcomes:
            ov = cast(dict[str, object], cast(dict[str, object], configs_dict[cfg_name])["overall"])
            ts1_s = cast(dict[str, object], cast(dict[str, object], configs_dict[cfg_name])["TS1-Lexical-API"])
            ts2_s = cast(dict[str, object], cast(dict[str, object], configs_dict[cfg_name])["TS2-Conceptual"])
            print(
                f"{cfg_name:24s} | Found={ov['found_pct']:5.1f}% | H@1={ov['hit_1_pct']:5.1f}% | "
                f"H@5={ov['hit_5_pct']:5.1f}% | R@5={ov['recall_5_pct']:5.1f}% | MRR@10={ov['mrr_10_pct']:5.1f}% | "
                f"NDCG@10={ov['ndcg_10_pct']:5.1f}% | TS1_MRR={ts1_s['mrr_10_pct']:5.1f}% | TS2_MRR={ts2_s['mrr_10_pct']:5.1f}% | "
                f"p50={ov['latency_p50_ms']:5.1f}ms p95={ov['latency_p95_ms']:5.1f}ms"
            )
    finally:
        await close_db_pool()


if __name__ == "__main__":
    asyncio.run(main())
