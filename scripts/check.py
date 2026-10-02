import re
import subprocess
import sys
from pathlib import Path

_FORBIDDEN_ANY_IMPORT = re.compile(
    r"^\s*(?:from\s+[\w.]+\s+import\s+(?:\([^)]*\bAny\b[^)]*\)|[^\n]*\bAny\b)|import\s+[^\n]*\bAny\b)",
    re.MULTILINE,
)


def run_step(title: str, cmd: list[str]) -> None:
    print(f"==> {title}...")
    result = subprocess.run(cmd, check=False)
    if result.returncode != 0:
        sys.exit(result.returncode)


def check_no_any_imports(target_dirs: tuple[str, ...] = ("src",)) -> None:
    print("==> Checking for forbidden Any imports...")
    violations: list[tuple[str, int, str]] = []

    for d_name in target_dirs:
        d = Path(d_name)
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.py")):
            text = p.read_text(encoding="utf-8")
            uncommented = "\n".join(line.split("#", 1)[0] for line in text.splitlines())
            for m in _FORBIDDEN_ANY_IMPORT.finditer(uncommented):
                line_no = uncommented[: m.start()].count("\n") + 1
                matched = m.group(0).strip().replace("\n", " ")
                violations.append((str(p), line_no, matched))

    if violations:
        print(f"\n[FAIL] Detected {len(violations)} forbidden 'Any' import declarations:", file=sys.stderr)
        for path_str, line_no, stmt in violations:
            print(f"  {path_str}:{line_no}: {stmt}", file=sys.stderr)
        sys.exit(1)
    print("✔ No forbidden 'Any' imports detected.")


def main() -> None:
    check_no_any_imports(("src",))
    run_step("Running Ruff linter & auto-fix", ["uv", "run", "ruff", "check", "--fix"])
    run_step("Running static type checking (ty)", ["uv", "run", "ty", "check"])


if __name__ == "__main__":
    main()
