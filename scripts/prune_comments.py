from __future__ import annotations

import argparse
import ast
import io
import pathlib
import re
import tokenize

TYPE_CONFIG_RE = re.compile(r"#\s*(type|pyright|mypy)\b", re.IGNORECASE)


def strip_comments_and_module_docstrings(source: str) -> str:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        tree = None

    mod_doc_lines: set[int] = set()
    if tree is not None and tree.body:
        first = tree.body[0]
        if (
            isinstance(first, ast.Expr)
            and isinstance(first.value, ast.Constant)
            and isinstance(first.value.value, str)
            and ast.get_docstring(tree, clean=False) == first.value.value
        ):
            mod_doc_lines = set(
                range(first.lineno, getattr(first, "end_lineno", first.lineno) + 1)
            )

    lines = source.splitlines(keepends=True)
    comment_tokens: dict[int, tokenize.TokenInfo] = {}
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                comment_tokens[tok.start[0]] = tok
    except tokenize.TokenError:
        pass

    new_lines: list[str] = []
    for i, line in enumerate(lines, 1):
        if i in mod_doc_lines:
            continue
        if i in comment_tokens:
            tok = comment_tokens[i]
            if TYPE_CONFIG_RE.search(tok.string):
                new_lines.append(line)
            else:
                col = tok.start[1]
                prefix = line[:col]
                if not prefix.strip():
                    continue
                ending = "\r\n" if line.endswith("\r\n") else "\n"
                new_lines.append(prefix.rstrip() + ending)
        else:
            new_lines.append(line)

    result: list[str] = []
    blank_count = 0
    for line in new_lines:
        if not line.strip():
            blank_count += 1
            if blank_count <= 2:
                result.append("\n")
        else:
            blank_count = 0
            result.append(line)

    final_text = "".join(result).lstrip("\r\n")
    if final_text and not final_text.endswith("\n"):
        final_text += "\n"
    return final_text


def process_path(
    path: pathlib.Path, dry_run: bool = False
) -> tuple[int, int, int]:
    files: list[pathlib.Path] = (
        sorted(path.rglob("*.py")) if path.is_dir() else [path]
    )
    processed_count = 0
    modified_count = 0
    total_lines_reduced = 0

    for file in files:
        processed_count += 1
        source = file.read_text(encoding="utf-8")
        transformed = strip_comments_and_module_docstrings(source)
        if transformed != source:
            modified_count += 1
            total_lines_reduced += len(source.splitlines()) - len(
                transformed.splitlines()
            )
            if not dry_run:
                file.write_text(transformed, encoding="utf-8")

    return processed_count, modified_count, total_lines_reduced


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Strip comments and module-level docstrings while preserving type configs and inner docstrings."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["src", "scripts"],
        help="Directories or files to process (default: src, scripts)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without modifying files on disk",
    )
    args = parser.parse_args()

    total_processed = 0
    total_modified = 0
    total_lines = 0

    for target in args.paths:
        p = pathlib.Path(target)
        if not p.exists():
            continue
        proc, mod, lines = process_path(p, dry_run=args.dry_run)
        total_processed += proc
        total_modified += mod
        total_lines += lines

    mode_str = "[DRY-RUN] " if args.dry_run else ""
    print(
        f"{mode_str}Processed {total_processed} files: {total_modified} modified, "
        f"{total_lines} lines reduced."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
