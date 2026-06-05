#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from review_scope_guard import (
    GENERATED_ARTIFACT_PREFIXES,
    blocked_generated_artifact_paths,
)

MAX_OFFENDING_OUTPUT = 50


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fail closed when a PR diff contains generated artifact paths."
    )
    parser.add_argument("--repo", default=".", help="Git repo to inspect.")
    parser.add_argument(
        "--base",
        default="origin/main",
        help="Base ref for diff inspection (default: origin/main).",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Head ref for diff inspection (default: HEAD).",
    )
    parser.add_argument(
        "--allow-prefix",
        action="append",
        default=[],
        help="Blocked prefix to allow for this invocation. Can be repeated.",
    )
    parser.add_argument(
        "--allow-generated-artifacts",
        action="store_true",
        help="Bypass the generated-artifact scope failure for intentional artifact reviews.",
    )
    return parser.parse_args(argv)


def git_changed_paths(repo: Path, base: str, head: str) -> list[str]:
    cmd = [
        "git",
        "-C",
        str(repo),
        "diff",
        "--name-only",
        f"{base}...{head}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "git diff failed")
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    repo = Path(args.repo).expanduser().resolve()
    if args.allow_generated_artifacts:
        return 0
    changed = git_changed_paths(repo, args.base, args.head)
    offending = blocked_generated_artifact_paths(
        changed,
        blocked_prefixes=GENERATED_ARTIFACT_PREFIXES,
        allowed_prefixes=args.allow_prefix,
    )
    if not offending:
        return 0
    print(
        "PR scope check failed: generated artifact paths are present in the diff.\n",
        file=sys.stderr,
    )
    path_label = "path" if len(offending) == 1 else "paths"
    print(f"Found {len(offending)} generated artifact {path_label}:", file=sys.stderr)
    for path in offending[:MAX_OFFENDING_OUTPUT]:
        print(f"- {path}", file=sys.stderr)
    remaining = len(offending) - MAX_OFFENDING_OUTPUT
    if remaining > 0:
        print(f"- ... and {remaining} more", file=sys.stderr)
    print(
        "\nMove generated outputs onto a different branch/worktree, or rerun with "
        "--allow-prefix for the specific subtree when the artifacts are intentional.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
