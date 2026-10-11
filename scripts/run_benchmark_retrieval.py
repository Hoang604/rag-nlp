"""Run hybrid_search on all 70 benchmark test cases and freeze raw outputs."""

import asyncio
import json
from pathlib import Path
from typing import cast

from rag_eval.db.connection import close_db_pool
from rag_eval.mcp.server import CorpusMCPServer

AGENT_PAYLOADS_DIR: Path = Path("benchmark_data/agent_payloads")
OUTPUT_DIR: Path = Path("benchmark_result")
OUTPUT_FILE: Path = OUTPUT_DIR / "raw_retrieval_results.json"


async def execute_tool_call(
    server: CorpusMCPServer,
    tool_name: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    """Execute a single MCP tool call through CorpusMCPServer."""
    # Ensure limit is standardized to 5 for benchmark Top-5 evaluation unless specified
    run_args = dict(arguments)
    run_args["limit"] = 5
    req: dict[str, object] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name.strip(),
            "arguments": run_args,
        },
    }
    res = await server.handle_request_dict(req)
    if not res:
        return {}
    
    # Extract the tool result structure
    result_data = res.get("result", {})
    if isinstance(result_data, dict):
        return result_data
    return res


def extract_top_candidates(retrieval_data: dict[str, object]) -> list[dict[str, object]]:
    """Flatten and prioritize Top candidates from both_hits, semantic_only_hits, and verbatim_only_hits."""
    candidates: list[dict[str, object]] = []
    seen_paths: set[str] = set()

    for channel in ["both_hits", "semantic_only_hits", "verbatim_only_hits"]:
        hits = retrieval_data.get(channel)
        if isinstance(hits, list):
            for hit in hits:
                if isinstance(hit, dict):
                    path = str(hit.get("path", ""))
                    if path and path not in seen_paths:
                        seen_paths.add(path)
                        candidate_item = dict(hit)
                        candidate_item["channel"] = channel
                        candidates.append(candidate_item)
    return candidates[:5]


async def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load all 7 batch payload files
    all_test_cases: list[dict[str, object]] = []
    for batch_idx in range(1, 8):
        batch_file = AGENT_PAYLOADS_DIR / f"batch_{batch_idx:02d}.json"
        if not batch_file.exists():
            raise FileNotFoundError(f"Missing expected batch file: {batch_file}")
        batch_data = json.loads(batch_file.read_text(encoding="utf-8"))
        if not isinstance(batch_data, list):
            raise TypeError(f"Expected JSON list in {batch_file}")
        for item in batch_data:
            if isinstance(item, dict):
                item_dict = dict(item)
                item_dict["batch"] = f"batch_{batch_idx:02d}"
                all_test_cases.append(item_dict)

    print(f"Loaded {len(all_test_cases)} benchmark test cases across 7 batches.")
    
    server = CorpusMCPServer()
    results: list[dict[str, object]] = []
    
    try:
        for idx, tc in enumerate(all_test_cases, start=1):
            tc_id = str(tc.get("id", f"TC-{idx:03d}"))
            tool_name = str(tc.get("tool_name", "hybrid_search"))
            raw_args = tc.get("arguments", {})
            arguments = cast(dict[str, object], raw_args) if isinstance(raw_args, dict) else {}
            
            print(f"[{idx:02d}/{len(all_test_cases)}] Executing {tc_id} ({tool_name})...")
            
            raw_res = await execute_tool_call(server, tool_name, arguments)
            candidates = extract_top_candidates(raw_res)
            
            result_entry: dict[str, object] = {
                "id": tc_id,
                "batch": tc.get("batch"),
                "issue_file": tc.get("issue_file"),
                "issue_summary": tc.get("issue_summary"),
                "tool_name": tool_name,
                "arguments": arguments,
                "top_candidates": candidates,
                "raw_result": raw_res,
            }
            results.append(result_entry)
            print(f"    -> Found {len(candidates)} candidates.")
            
    finally:
        await close_db_pool()
        
    formatted_output = json.dumps(results, indent=2, ensure_ascii=False)
    OUTPUT_FILE.write_text(formatted_output, encoding="utf-8")
    print(f"\n✔ Done! Wrote {len(results)} frozen retrieval results to {OUTPUT_FILE}")


if __name__ == "__main__":
    asyncio.run(main())
