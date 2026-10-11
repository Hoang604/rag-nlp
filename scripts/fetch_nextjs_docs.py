from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

REPO = "vercel/next.js"
BRANCH = "canary"
BASE_DIR = "docs/01-app/"
PREFIXES = [
    "docs/01-app/01-getting-started/",
    "docs/01-app/02-guides/",
]
TREES_API_URL = f"https://api.github.com/repos/{REPO}/git/trees/{BRANCH}?recursive=1"
RAW_BASE_URL = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"


def _download_file(remote_path: str, dest_file: Path) -> Path | None:
    raw_url = f"{RAW_BASE_URL}{remote_path}"
    dest_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        req = urllib.request.Request(raw_url, headers={"User-Agent": "rag-eval-crawler/1.0"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            content = resp.read()
            dest_file.write_bytes(content)
            return dest_file
    except (urllib.error.URLError, OSError, RuntimeError) as exc:
        logger.error("Failed downloading %s: %s", raw_url, exc)
        return None


def fetch_nextjs_docs(target_dir: Path = Path("data/nextjs"), force: bool = False) -> list[Path]:
    """Downloads official Next.js App Router MDX documentation safely avoiding GitHub rate limits.

    Uses a single Git Trees API request to get all file paths, then fetches contents
    via raw.githubusercontent.com concurrently using a thread pool.
    """
    target_dir = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    existing_files = list(target_dir.rglob("*.mdx"))
    if existing_files and not force:
        logger.info(
            "Found %d existing .mdx files in '%s'. Skipping fetch (use force=True to re-download).",
            len(existing_files),
            target_dir,
        )
        return existing_files

    logger.info("Requesting file tree from %s...", TREES_API_URL)
    req = urllib.request.Request(
        TREES_API_URL,
        headers={"User-Agent": "rag-eval-crawler/1.0", "Accept": "application/vnd.github.v3+json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 403:
            logger.warning("GitHub API rate limit on Git Trees API: %s.", exc)
            raise RuntimeError("GitHub API rate limit exceeded. Please wait or set GITHUB_TOKEN.") from exc
        raise

    tree = data.get("tree", [])
    mdx_entries = [
        item["path"]
        for item in tree
        if item.get("type") == "blob"
        and any(item.get("path", "").startswith(p) for p in PREFIXES)
        and item.get("path", "").endswith((".mdx", ".md"))
    ]

    logger.info("Discovered %d Next.js App Router documentation files.", len(mdx_entries))
    saved_files: list[Path] = []

    tasks = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for remote_path in mdx_entries:
            rel_subpath = remote_path.removeprefix(BASE_DIR)
            dest_file = target_dir / rel_subpath
            tasks.append(executor.submit(_download_file, remote_path, dest_file))

        for future in as_completed(tasks):
            res = future.result()
            if res is not None:
                saved_files.append(res)

    logger.info("Successfully fetched %d documentation files into '%s'.", len(saved_files), target_dir)
    return saved_files


if __name__ == "__main__":
    fetch_nextjs_docs(force=True)
