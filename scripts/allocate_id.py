#!/usr/bin/env python3
"""Atomically allocate governed WORK IDs across git worktrees."""

from __future__ import annotations

import argparse
import fcntl
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DOMAIN_RE = re.compile(r"^[A-Z][A-Z0-9]{1,15}$")
SIZE_VALUES = {"XS", "S", "M", "L", "XL"}
CATEGORY_RE = re.compile(r"^[a-z][a-z-]*~?$")


class AllocationError(RuntimeError):
    """Raised when an ID cannot be allocated safely."""


def git_output(args: list[str], cwd: Path) -> str:
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return proc.stdout.strip()


def normalize_domain(raw: str) -> str:
    domain = raw.strip().upper()
    if not DOMAIN_RE.fullmatch(domain):
        raise AllocationError(
            "domain must be an uppercase code like AGT, OBS, MLE, or TRD"
        )
    return domain


def governance_row_pattern(domain: str) -> re.Pattern[str]:
    return re.compile(
        rf"(?m)^(\|[ \t]*[^|\n]+[ \t]*\|[ \t]*{re.escape(domain)}"
        r"[ \t]*\|[ \t]*)(\d+)([ \t]*\|[^\n]*)$"
    )


def scan_governance_high_water(text: str, domain: str) -> int:
    match = governance_row_pattern(domain).search(text)
    if not match:
        raise AllocationError(
            f"unknown domain {domain}: no matching row in pm/governance.md"
        )
    return int(match.group(2))


def scan_pm_ids(path: Path, domain: str) -> int:
    if not path.exists():
        return 0
    text = path.read_text(encoding="utf-8")
    pattern = re.compile(rf"\b[A-Z]+-{re.escape(domain)}-(\d+)\b")
    values = [int(match.group(1)) for match in pattern.finditer(text)]
    return max(values, default=0)


def validate_pm_surface(root: Path, domain: str) -> None:
    governance_path = root / "pm" / "governance.md"
    backlog_path = root / "pm" / "backlog.md"
    if not governance_path.exists():
        raise AllocationError("pm/governance.md is required for governed allocation")
    if not backlog_path.exists():
        raise AllocationError("pm/backlog.md is required for governed allocation")

    governance_text = governance_path.read_text(encoding="utf-8")
    backlog_text = backlog_path.read_text(encoding="utf-8")
    scan_governance_high_water(governance_text, domain)
    if not re.search(r"(?m)^## Pending[ \t]*$", backlog_text):
        raise AllocationError("could not find ## Pending in pm/backlog.md")


def tracked_high_water(root: Path, domain: str) -> int:
    governance_text = (root / "pm" / "governance.md").read_text(encoding="utf-8")
    return max(
        scan_governance_high_water(governance_text, domain),
        scan_pm_ids(root / "pm" / "backlog.md", domain),
        scan_pm_ids(root / "pm" / "done.md", domain),
        scan_pm_ids(root / "pm" / "ideas.md", domain),
    )


def read_ledger(path: Path) -> int:
    if not path.exists():
        return 0
    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return 0
    try:
        return int(raw)
    except ValueError as exc:
        raise AllocationError(f"corrupt allocation ledger: {path}") from exc


def write_text_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    tmp.write_text(text, encoding="utf-8")
    os.replace(tmp, path)


def write_ledger(path: Path, value: int) -> None:
    write_text_atomic(path, f"{value}\n")


def update_governance(root: Path, domain: str, value: int) -> None:
    path = root / "pm" / "governance.md"
    text = path.read_text(encoding="utf-8")
    pattern = governance_row_pattern(domain)
    match = pattern.search(text)
    if not match:
        raise AllocationError(
            f"unknown domain {domain}: no matching row in pm/governance.md"
        )
    current = int(match.group(2))
    if current >= value:
        return
    raw_value = match.group(2)
    rendered_value = str(value).zfill(len(raw_value))
    updated = f"{text[:match.start(2)]}{rendered_value}{text[match.end(2):]}"
    write_text_atomic(path, updated)


def today_string() -> str:
    try:
        tz = ZoneInfo("America/New_York")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().strftime("%Y-%m-%d")
    return datetime.now(tz).strftime("%Y-%m-%d")


def render_backlog_entry(args: argparse.Namespace, work_id: str) -> str:
    today = today_string()
    title = args.title.strip() if args.title else ""
    description = args.description.strip() if args.description else ""
    if title and description and title.rstrip(".") != description.rstrip("."):
        body = f"{title}: {description}"
    elif title:
        body = title
    elif description:
        body = description
    else:
        body = (
            "Reserved ID: replace this placeholder with the work-item "
            "description before committing."
        )
    return (
        f"- {work_id} [{args.size}] {args.category} | {today} | "
        f"{args.source} | {body}"
    )


def insert_backlog_reservation(
    root: Path, work_id: str, args: argparse.Namespace
) -> None:
    path = root / "pm" / "backlog.md"
    text = path.read_text(encoding="utf-8")
    if re.search(rf"\b{re.escape(work_id)}\b", text):
        return
    entry = render_backlog_entry(args, work_id)
    match = re.search(r"(?m)^## Pending[ \t]*$", text)
    if not match:
        raise AllocationError("could not find ## Pending in pm/backlog.md")
    suffix = text[match.end() :].lstrip("\n")
    updated = f"{text[:match.end()]}\n\n{entry}\n"
    if suffix:
        updated += suffix
    write_text_atomic(path, updated)


def reserve_id(root: Path, domain: str, args: argparse.Namespace) -> str:
    validate_pm_surface(root, domain)
    common_git_dir = Path(
        git_output(["rev-parse", "--path-format=absolute", "--git-common-dir"], root)
    )
    lock_dir = common_git_dir / "pm-locks"
    lock_dir.mkdir(parents=True, exist_ok=True)
    lock_path = lock_dir / f"{domain}.lock"
    ledger_path = lock_dir / f"{domain}.highwater"

    with lock_path.open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        validate_pm_surface(root, domain)
        next_value = max(tracked_high_water(root, domain), read_ledger(ledger_path)) + 1
        write_ledger(ledger_path, next_value)
        work_id = f"WORK-{domain}-{next_value:03d}"
        update_governance(root, domain, next_value)
        insert_backlog_reservation(root, work_id, args)
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    return work_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Atomically reserve the next governed WORK ID for a domain."
    )
    parser.add_argument("domain", help="domain code, e.g. AGT, OBS, MLE, TRD")
    parser.add_argument("--title", default="", help="reserved backlog item title")
    parser.add_argument(
        "--description", default="", help="reserved backlog item description"
    )
    parser.add_argument("--size", default="M", help="backlog size: XS, S, M, L, XL")
    parser.add_argument(
        "--category",
        default="capability",
        help="backlog category, optionally suffixed with ~",
    )
    parser.add_argument("--source", default="Allocator", help="backlog source label")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        domain = normalize_domain(args.domain)
        args.size = args.size.strip().upper()
        if args.size not in SIZE_VALUES:
            raise AllocationError("size must be one of XS, S, M, L, XL")
        args.category = args.category.strip().lower()
        if not CATEGORY_RE.fullmatch(args.category):
            raise AllocationError("category must look like capability or cleanup~")
        args.source = args.source.strip() or "Allocator"

        root = Path(git_output(["rev-parse", "--show-toplevel"], Path.cwd()))
        work_id = reserve_id(root, domain, args)
    except (AllocationError, subprocess.CalledProcessError) as exc:
        print(f"allocate_id.py: error: {exc}", file=sys.stderr)
        return 1
    print(work_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
