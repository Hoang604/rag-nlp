import re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
EXCLUDE_NAMES: set[str] = {
    ".venv",
    "__pycache__",
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".cache",
    ".holdout_vault",
    "data",
    "predictions",
    "reports",
    "experiments",
    "dist",
    "dist-ssr",
    "build",
    "node_modules",
    ".vite",
    ".vite-temp",
    "coverage",
    "htmlcov",
    "logs",
    "audits",
    ".idea",
    ".vscode",
    ".DS_Store",
    "Thumbs.db",
}

EXCLUDE_SUFFIXES: tuple[str, ...] = (
    ".pyc",
    ".pyo",
    ".patch",
    ".log",
    ".tsbuildinfo",
    ".egg-info",
)


def should_exclude(p: Path) -> bool:
    return p.name in EXCLUDE_NAMES or p.name.endswith(EXCLUDE_SUFFIXES)


def generate_tree(dir_path: Path, prefix: str = "") -> list[str]:
    lines: list[str] = []
    if dir_path == ROOT_DIR / ".agents":
        raw_entries = [p for p in dir_path.iterdir() if p.name == "skills"]
    else:
        raw_entries = [p for p in dir_path.iterdir() if not should_exclude(p)]

    entries = sorted(
        raw_entries,
        key=lambda p: (not p.is_dir(), p.name),
    )
    for idx, entry in enumerate(entries):
        is_last = idx == len(entries) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            sub_prefix = f"{prefix}    " if is_last else f"{prefix}│   "
            lines.extend(generate_tree(entry, sub_prefix))
    return lines


def main() -> None:
    tree_lines = [f"{ROOT_DIR.name}/", *generate_tree(ROOT_DIR)]
    tree_str = "\n".join(tree_lines)

    agents_file = ROOT_DIR / "AGENTS.md"
    if not agents_file.is_file():
        return
    content = agents_file.read_text(encoding="utf-8")
    pattern = r"<!-- DIR_TREE_START -->.*?<!-- DIR_TREE_END -->"
    replacement = f"<!-- DIR_TREE_START -->\n```text\n{tree_str}\n```\n<!-- DIR_TREE_END -->"
    new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
    with agents_file.open("w", encoding="utf-8", newline="\n") as f:
        f.write(new_content)


if __name__ == "__main__":
    main()
