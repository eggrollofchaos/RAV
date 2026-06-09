#!/usr/bin/env python3
"""Stateful /pm-audit runner with cross-run intelligence.

This is the canonical execution surface for `/pm-audit`. The skill at
``claude/skills/pm-audit/SKILL.md`` remains the operator entrypoint, but
finding production, stable signatures, report persistence, and cross-run
delta classification live here so they are deterministic and testable.

Design contract (see ``docs/plans/pm-audit-cross-run-intelligence.md`` and its
``_spec.md`` companion, plus the reference doc
``docs/knowledge-base/reference/2026-06-01_pm-audit.md``):

* Dependency-free. No PyYAML — a purpose-built parser handles the actual
  audit-config schema (nested maps, flow/block lists, list-of-maps
  ``suppressions:``), preserving the per-key absent-vs-empty semantics.
* Every check emits findings through the single :func:`emit_finding` helper so
  signatures are computed in exactly one place (Invariant A). CodeGraph results
  flow through :func:`normalize_codegraph_bundle` into that same helper.
* ``issue_signature`` is line-number-independent: ``check|area_key|kind``.
* Each run persists one UTC-stamped ``pm/reports/audit-*.md`` artifact whose
  trailing structured block the next run reloads. Baselines resolve per
  canonical check token, not against one global prior report, so mixed-mode
  cadence (core daily / extended weekly / full monthly) never fakes a
  ``resolved`` for a check that simply did not run this time.

Writing ``pm/reports/audit-*.md`` is an AUDIT OUTPUT artifact, not a PM
tracking-surface mutation. Finding production stays read-only with respect to
backlog/done/ideas/governance/registry/roadmap.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

# Unified ID grammar. The optional leading completion prefix is captured as part
# of the full token so an active ``WORK-AGT-164`` and a closed ``WORK-AGT-164``
# compare equal while ``ISSUE-AGT-010`` and ``FIXED-ISSUE-AGT-010`` do not.
COMPLETION_PREFIXES = ("FIXED", "LIVE", "NOPE", "OVER", "DUPE")
ACTIVE_PREFIXES = ("IDEA", "ISSUE", "WORK", "PLAN", "IMP", "EVO")
_TOKEN_BODY = (
    r"(?:FIXED-|LIVE-|NOPE-|OVER-|DUPE-)?"
    r"(?:IDEA|ISSUE|WORK|PLAN|IMP|EVO)-[A-Z][A-Z0-9]{1,15}-\d{1,5}"
)
TOKEN_RE = re.compile(rf"\b({_TOKEN_BODY})\b")
# A row's PRIMARY id is anchored at the start of a bullet row (after an optional
# backtick), so Check 1d compares row-class ids only, never IDs mentioned in
# description prose.
ROW_ID_RE = re.compile(rf"^-\s+`?({_TOKEN_BODY})\b")
# domain-number portion, ignoring the prefix, for cross-prefix grouping (1a).
DOMAIN_NUM_RE = re.compile(
    r"\b(?:FIXED-|LIVE-|NOPE-|OVER-|DUPE-)?"
    r"(IDEA|ISSUE|WORK|PLAN|IMP|EVO)-([A-Z][A-Z0-9]{1,15}-\d{1,5})\b"
)

STRUCT_START = "<!-- pm-audit-structured-report:v1 -->"
STRUCT_END = "<!-- /pm-audit-structured-report -->"

# Check 24 (refactor impact) is targeted-only: it requires explicit plan-claim
# context and never runs as part of routine ``full`` / ``codegraph``. Routine
# CodeGraph cadence (20-23) is taken from ``checks.codegraph`` config.
TARGETED_ONLY = ("24",)

# Default config (IXQT shape) with the cross-run-intelligence additions. Checks
# 25/26 are still operator-owned via the skill/dedicated scripts, so the runner
# surfaces them as skipped-with-note until they get deterministic adapters. The
# routine ``checks.codegraph`` default is 20-23; Check 24 stays targeted-only.
DEFAULTS: dict[str, Any] = {
    "paths": {
        "version_files": [
            'src/version.py:APP_VERSION = "v?(\\d+\\.\\d+\\.\\d+)',
            'pyproject.toml:^version = "(\\d+\\.\\d+\\.\\d+)"',
            "README.md:\\*\\*Version:\\*\\* .v?(\\d+\\.\\d+\\.\\d+)",
        ],
        "source_dirs": ["src/"],
        "source_extensions": [".py"],
        "followups": "pm/backlog.md",
        "changelog": "CHANGELOG.md",
        "index": "docs/INDEX.md",
        "registry": "pm/initiative-registry.md",
        "plans": "docs/plans/",
        "archive": "docs/archive/",
        "issues": "pm/issues/",
        "issue_tracker": "pm/issue-tracker.md",
        "ideas": "pm/ideas.md",
        "done": "pm/done.md",
        "governance": "pm/governance.md",
        "roadmap": "pm/roadmap.md",
        "reference": "docs/knowledge-base/reference/",
        "sessions": ".agent-sessions/sessions.md",
        "active_work": "pm/active-work.md",
        "tag_manifest": "pm/tag-manifest.md",
        "governance_dir": "docs/governance/",
        "governance_roadmaps": "docs/governance/*roadmap*.md",
        "current_sprint": "pm/current-sprint.md",
        "sprints": "pm/sprints/",
        "inbox_review_queue": "pm/inbox-review-queue.json",
        "reports": "pm/reports/",
    },
    "taxonomy": {
        "file": "docs/governance/project-taxonomy.yaml",
        "domain_codes": {
            "DAT": "data",
            "MLE": "ml",
            "STR": "strategy",
            "TRD": "trading",
            "UIX": "ui",
            "OPT": "options",
            "PFM": "portfolio",
            "TNM": "tournament",
            "BRK": "broker",
            "CLD": "cloud",
            "OBS": "observability",
            "FND": "foundation",
        },
    },
    "checks": {
        "core": [1, 2, 3, 4, 5, 6, 7, 8],
        "extended": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 25, 26],
        "codegraph": [20, 21, 22, 23],
        "skip": [],
        "severity_override": {},
    },
    "codegraph": {
        "enabled": True,
        "repo_path": ".",
        "complexity_threshold": 15,
        "dead_code_exclude_decorators": [
            "@app.route",
            "@cli.command",
            "@click.command",
            "@pytest.fixture",
            "@app.callback",
        ],
    },
    "suppressions": {},
    "repeat_escalation_days": 30,
}


class ConfigError(RuntimeError):
    """Raised when the merged audit config is structurally invalid."""


# --------------------------------------------------------------------------- #
# Dependency-free config parser (audit-config schema subset)
# --------------------------------------------------------------------------- #

_KEY_RE = re.compile(
    r"^(?P<key>[A-Za-z0-9_.\-]+|\"(?:[^\"\\]|\\.)*\"|'(?:[^']|'')*')"
    r":(?:[ \t]+(?P<val>.*))?$"
)


def _strip_comment(line: str) -> str:
    """Remove a trailing ``#`` comment that is outside quotes.

    A ``#`` only starts a comment when it is at the start of the (stripped)
    content or preceded by whitespace, matching YAML. ``#`` inside a quoted
    scalar is preserved.
    """
    out = []
    quote: Optional[str] = None
    prev_ws = True  # start-of-line counts as preceded-by-whitespace
    for ch in line:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            prev_ws = False
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            prev_ws = False
            continue
        if ch == "#" and prev_ws:
            break
        out.append(ch)
        prev_ws = ch in (" ", "\t")
    return "".join(out).rstrip()


def _logical_lines(text: str) -> list[tuple[int, str]]:
    if text.startswith("﻿"):
        text = text[1:]
    result: list[tuple[int, str]] = []
    for raw in text.splitlines():
        stripped = _strip_comment(raw)
        if not stripped.strip():
            continue
        indent = len(stripped) - len(stripped.lstrip(" "))
        result.append((indent, stripped.strip()))
    return result


def _parse_scalar(token: str) -> Any:
    token = token.strip()
    if not token:
        return None
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        return _unescape_double(token[1:-1])
    if len(token) >= 2 and token[0] == "'" and token[-1] == "'":
        return token[1:-1].replace("''", "'")
    low = token.lower()
    if low in ("null", "~", ""):
        return None
    if low == "true":
        return True
    if low == "false":
        return False
    if re.fullmatch(r"-?\d+", token):
        return int(token)
    return token


def _unescape_double(body: str) -> str:
    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            nxt = body[i + 1]
            mapping = {"n": "\n", "t": "\t", '"': '"', "\\": "\\", "/": "/"}
            out.append(mapping.get(nxt, nxt))
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _split_flow(body: str) -> list[str]:
    """Split a flow sequence/mapping body on top-level commas."""
    parts: list[str] = []
    depth = 0
    quote: Optional[str] = None
    current: list[str] = []
    for ch in body:
        if quote:
            current.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            current.append(ch)
            continue
        if ch in "[{":
            depth += 1
            current.append(ch)
            continue
        if ch in "]}":
            depth -= 1
            current.append(ch)
            continue
        if ch == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    tail = "".join(current).strip()
    if tail:
        parts.append(tail)
    return [p.strip() for p in parts if p.strip()]


def _parse_flow_value(token: str) -> Any:
    token = token.strip()
    if token.startswith("[") and token.endswith("]"):
        inner = token[1:-1].strip()
        if not inner:
            return []
        return [_parse_flow_value(item) for item in _split_flow(inner)]
    if token.startswith("{") and token.endswith("}"):
        inner = token[1:-1].strip()
        if not inner:
            return {}
        result: dict[str, Any] = {}
        for pair in _split_flow(inner):
            if ":" not in pair:
                raise ConfigError(f"invalid flow-map entry: {pair!r}")
            key, _, val = pair.partition(":")
            parsed_key = _parse_scalar(key.strip())
            result[str(parsed_key)] = _parse_flow_value(val.strip())
        return result
    return _parse_scalar(token)


class _BlockParser:
    def __init__(self, lines: list[tuple[int, str]]):
        self.lines = lines
        self.i = 0

    def _peek(self) -> Optional[tuple[int, str]]:
        return self.lines[self.i] if self.i < len(self.lines) else None

    def parse_block(self, indent: int) -> Any:
        node = self._peek()
        if node is None or node[0] < indent:
            return None
        if node[1] == "-" or node[1].startswith("- "):
            return self.parse_seq(indent)
        return self.parse_map(indent)

    def parse_map(self, indent: int) -> dict[str, Any]:
        result: dict[str, Any] = {}
        while True:
            node = self._peek()
            if node is None or node[0] != indent or node[1].startswith("-"):
                break
            match = _KEY_RE.match(node[1])
            if not match:
                raise ConfigError(f"unparsable config line: {node[1]!r}")
            key = str(_parse_scalar(match.group("key")))
            val = match.group("val")
            self.i += 1
            if val is None or val.strip() == "":
                child = self._peek()
                if child is not None and child[0] > indent:
                    result[key] = self.parse_block(child[0])
                else:
                    result[key] = None
            else:
                result[key] = _parse_flow_value(val.strip())
        return result

    def parse_seq(self, indent: int) -> list[Any]:
        result: list[Any] = []
        while True:
            node = self._peek()
            if node is None or node[0] != indent:
                break
            if not (node[1] == "-" or node[1].startswith("- ")):
                break
            content = node[1][1:].strip()
            self.i += 1
            if content == "":
                child = self._peek()
                if child is not None and child[0] > indent:
                    result.append(self.parse_block(child[0]))
                else:
                    result.append(None)
            elif _KEY_RE.match(content):
                sub = [(indent + 2, content)]
                while True:
                    child = self._peek()
                    if child is None or child[0] <= indent:
                        break
                    sub.append(child)
                    self.i += 1
                result.append(_BlockParser(sub).parse_map(indent + 2))
            else:
                result.append(_parse_flow_value(content))
        return result


def parse_config(text: str) -> dict[str, Any]:
    lines = _logical_lines(text)
    if not lines:
        return {}
    parsed = _BlockParser(lines).parse_block(lines[0][0])
    if parsed is None:
        return {}
    if not isinstance(parsed, dict):
        raise ConfigError("top-level audit config must be a mapping")
    return parsed


def _merge(default: Any, override: Any) -> Any:
    """Deep-merge, preserving per-key absent-vs-empty semantics.

    ``None`` (explicit null or empty value) means "use the default". An explicit
    ``[]`` / ``{}`` is a real disabling override and is kept as-is.
    """
    if override is None:
        return copy.deepcopy(default)
    if isinstance(default, dict) and isinstance(override, dict):
        merged = copy.deepcopy(default)
        for key, value in override.items():
            if value is None:
                continue
            base = merged.get(key)
            merged[key] = _merge(base, value) if isinstance(base, dict) else value
        return merged
    return override


def merge_config(loaded: dict[str, Any]) -> dict[str, Any]:
    merged = _merge(DEFAULTS, loaded or {})
    _validate_config(merged)
    return merged


def load_config(path: Optional[Path]) -> dict[str, Any]:
    if path is None or not Path(path).exists():
        return merge_config({})
    text = Path(path).read_text(encoding="utf-8")
    return merge_config(parse_config(text))


def _validate_config(cfg: dict[str, Any]) -> None:
    suppressions = cfg.get("suppressions") or {}
    if not isinstance(suppressions, dict):
        raise ConfigError("suppressions must be a mapping of check token -> entries")
    normalized: dict[str, list[dict[str, str]]] = {}
    for raw_key, entries in suppressions.items():
        token = canonical_token(raw_key)
        if entries is None:
            normalized[token] = []
            continue
        if not isinstance(entries, list):
            raise ConfigError(
                f"suppressions[{raw_key!r}] must be a list of "
                "{match, reason} entries"
            )
        out: list[dict[str, str]] = []
        for entry in entries:
            if not isinstance(entry, dict):
                raise ConfigError(
                    f"suppressions[{raw_key!r}] entries must be mappings with "
                    "'match' and 'reason'"
                )
            if "match" not in entry or not str(entry.get("match", "")).strip():
                raise ConfigError(
                    f"suppressions[{raw_key!r}] entry missing required 'match'"
                )
            if "reason" not in entry or not str(entry.get("reason", "")).strip():
                raise ConfigError(
                    f"suppressions[{raw_key!r}] entry for "
                    f"{entry.get('match')!r} missing required 'reason'"
                )
            out.append({"match": str(entry["match"]), "reason": str(entry["reason"])})
        normalized[token] = out
    cfg["suppressions"] = normalized

    days = cfg.get("repeat_escalation_days", 30)
    if days is None:
        days = 30
    if not isinstance(days, int) or days < 0:
        raise ConfigError("repeat_escalation_days must be a non-negative integer")
    cfg["repeat_escalation_days"] = days


# --------------------------------------------------------------------------- #
# Check-key normalization
# --------------------------------------------------------------------------- #


def canonical_token(raw: Any) -> str:
    """Normalize any check-key spelling to one bare lowercase token.

    ``Check-1a`` / ``check-1A`` / ``1A`` -> ``1a``; integer ``7`` -> ``"7"``.
    """
    text = str(raw).strip().lower()
    text = re.sub(r"^check[\s\-_]*", "", text)
    return text.strip().strip("-_ ")


def _whole_number(token: str) -> str:
    match = re.match(r"(\d+)", token)
    return match.group(1) if match else token


# --------------------------------------------------------------------------- #
# Findings + the single emission helper
# --------------------------------------------------------------------------- #


@dataclass
class Finding:
    check: str
    severity: str
    file: str
    line: Any
    issue: str
    suggested_fix: str
    area_key: str
    kind: str
    issue_signature: str = ""
    summary: str = ""
    first_seen: str = ""
    repeat_count: int = 1
    suppressed: bool = False
    escalated: bool = False
    delta_status: str = "new"
    severity_change: str = ""
    prior_signature: str = ""

    def to_payload(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "issue_signature": self.issue_signature,
            "summary": self.summary or self.issue,
            "area_key": self.area_key,
            "kind": self.kind,
            "first_seen": self.first_seen,
            "repeat_count": self.repeat_count,
            "suppressed": self.suppressed,
        }


def build_signature(check: str, area_key: str, kind: str) -> str:
    """Stable, line-number-independent finding identity."""
    return f"{check}|{area_key}|{kind}"


def normalize_snippet(text: str) -> str:
    """Fallback area-key normalization for findings with no stable token."""
    lowered = text.lower()
    lowered = re.sub(r"[`*_#>]", "", lowered)
    lowered = re.sub(r"\s+", " ", lowered).strip()
    return lowered


def snippet_area_key(text: str, *, length: int = 12) -> str:
    digest = hashlib.sha1(normalize_snippet(text).encode("utf-8")).hexdigest()
    return f"snip:{digest[:length]}"


def emit_finding(
    findings: list[Finding],
    *,
    check: str,
    severity: str,
    file: str,
    line: Any,
    issue: str,
    suggested_fix: str,
    area_key: str,
    kind: str,
    summary: str = "",
) -> Finding:
    """The ONE place findings are constructed (Invariant A).

    Every check and the CodeGraph adapter route through here so signatures are
    computed identically and tests can enumerate the emit path.
    """
    token = canonical_token(check)
    finding = Finding(
        check=token,
        severity=severity.lower(),
        file=file,
        line=line,
        issue=issue,
        suggested_fix=suggested_fix,
        area_key=area_key,
        kind=kind,
        summary=summary or issue,
        issue_signature=build_signature(token, area_key, kind),
    )
    findings.append(finding)
    return finding


# --------------------------------------------------------------------------- #
# PM row extraction helpers
# --------------------------------------------------------------------------- #


def _section(text: str, header: str) -> str:
    """Return the body of a ``## header`` section up to the next ``## ``."""
    pattern = re.compile(rf"(?m)^##\s+{re.escape(header)}\s*$")
    match = pattern.search(text)
    if not match:
        return ""
    rest = text[match.end() :]
    nxt = re.search(r"(?m)^##\s+", rest)
    return rest[: nxt.start()] if nxt else rest


def _strip_strikethrough(line: str) -> str:
    return re.sub(r"~~.*?~~", "", line)


# Historical id tokens in rename notes — "renamed/renumbered ... from X" or
# "originally X" — name an id that has already been retired, not an active one.
# This pattern matches ONLY the historical (FROM / originally) side so the
# surviving id named by a "renamed to Y" / "superseded by Y" clause is never
# touched. The verb->``from`` window is bounded (so an unrelated later "from" on
# a long line cannot be roped in) and tolerates an intervening date or clause
# (e.g. "Renumbered 2026-06-01 from `IDEA-AGT-144`").
_RENAME_PROSE_RE = re.compile(
    r"(?P<lead>(?:renamed|renumbered)\b[^\n]{0,40}?\bfrom\s+|\boriginally\s+)"
    rf"`?(?:{_TOKEN_BODY})`?",
    re.IGNORECASE,
)


def _strip_rename_prose(line: str) -> str:
    """Blank out a historical id token that follows a rename-from phrase.

    Defense-in-depth behind the paired-strike rename convention
    (``pm/governance.md`` section Number Allocation): if an author writes
    ``renumbered from `IDEA-AGT-144` `` and forgets to paired-strike it, the
    token would otherwise be read as an active cross-prefix collision. Only the
    historical FROM/``originally`` side is removed -- the trigger words and the
    surviving id are preserved. This is safe against hiding a *real* collision:
    a genuinely active id always has a primary row occurrence elsewhere in the
    scanned surfaces, which still registers; only the rename-note mention on
    this line is dropped. Applied on top of, not instead of, strikethrough
    stripping.
    """
    return _RENAME_PROSE_RE.sub(lambda m: m.group("lead"), line)


def _row_primary_id(line: str) -> Optional[str]:
    """Return the bullet row's leading id token, or None for id-less rows."""
    match = ROW_ID_RE.match(line.lstrip())
    return match.group(1) if match else None


def _table_primary_id(line: str) -> Optional[str]:
    """Return the id in the FIRST column of a markdown table row, ignoring the
    description column so prose mentions are never treated as closed ids."""
    cells = line.split("|")
    if len(cells) < 2:
        return None
    match = TOKEN_RE.search(cells[1])
    return match.group(1) if match else None


def active_pending_tokens(backlog_text: str) -> list[tuple[str, int]]:
    """Primary ids of active rows in backlog ``## Pending``.

    Only paired ``~~...~~`` strikethrough closes a row; a single trailing ``~``
    category suffix (e.g. ``capability~``) stays active. Only the row's leading
    id is returned — ids mentioned in description prose are excluded.
    """
    section = _section(backlog_text, "Pending")
    if not section:
        return []
    base_line = backlog_text[: backlog_text.find(section)].count("\n") if section else 0
    out: list[tuple[str, int]] = []
    for offset, line in enumerate(section.splitlines()):
        if not line.lstrip().startswith("- "):
            continue
        visible = _strip_strikethrough(line)
        token = _row_primary_id(visible)
        if token:
            out.append((token, base_line + offset + 1))
    return out


def closed_surface_tokens(done_text: str, backlog_text: str) -> set[str]:
    """Primary ids of closed-row surfaces (done table + tombstone bullets).

    Description-column / prose ids are excluded so only the closed row's own
    id participates in the active-vs-closed comparison.
    """
    tokens: set[str] = set()
    for line in done_text.splitlines():
        if line.lstrip().startswith("|"):
            token = _table_primary_id(line)
            if token:
                tokens.add(token)
    tombstone = _section(backlog_text, "Recently Completed")
    for line in tombstone.splitlines():
        if line.lstrip().startswith("-"):
            token = _row_primary_id(line.lstrip())
            if token:
                tokens.add(token)
    return tokens


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _path(cfg: dict[str, Any], key: str, root: Path) -> Path:
    return root / cfg["paths"].get(key, "")


def _issues_dir(cfg: dict[str, Any], root: Path) -> Path:
    return _path(cfg, "issues", root)


def _issue_files(cfg: dict[str, Any], root: Path) -> list[Path]:
    issues_dir = _issues_dir(cfg, root)
    if not issues_dir.exists() or not issues_dir.is_dir():
        return []
    return sorted(p for p in issues_dir.glob("*.md") if p.is_file())


def _split_lines(text: str) -> list[str]:
    return text.splitlines()


def _heading_token(line: str, prefix: str) -> Optional[str]:
    match = re.match(
        rf"^###\s+((?:FIXED-|LIVE-|NOPE-|OVER-|DUPE-)?{re.escape(prefix)}-[A-Z][A-Z0-9]{{1,15}}-\d{{1,5}})\b",
        line.strip(),
    )
    return match.group(1) if match else None


@dataclass
class HeadingEntry:
    token: str
    line_no: int
    lines: list[str]
    path: str


def _iter_heading_entries(path: Path, prefix: str, root: Path) -> list[HeadingEntry]:
    text = _read_text(path)
    lines = _split_lines(text)
    entries: list[HeadingEntry] = []
    for idx, line in enumerate(lines):
        token = _heading_token(line, prefix)
        if not token or "~~" in line:
            continue
        entries.append(
            HeadingEntry(
                token=token,
                line_no=idx + 1,
                lines=lines[idx : idx + 11],
                path=str(path.relative_to(root)),
            )
        )
    return entries


def _window_has_field(lines: list[str], field: str) -> bool:
    pattern = f"**{field}:**"
    return any(pattern in line for line in lines[:10])


def _parse_markdown_tables(
    text: str,
) -> list[tuple[list[str], list[tuple[int, dict[str, str]]]]]:
    tables: list[tuple[list[str], list[tuple[int, dict[str, str]]]]] = []
    lines = text.splitlines()
    i = 0
    sep_re = re.compile(r"^\|\s*[-:]+(?:\s*\|\s*[-:]+)+\s*\|?\s*$")
    while i + 1 < len(lines):
        header = lines[i].strip()
        sep = lines[i + 1].strip()
        if not (header.startswith("|") and sep_re.match(sep)):
            i += 1
            continue
        headers = [cell.strip() for cell in header.strip("|").split("|")]
        i += 2
        rows: list[tuple[int, dict[str, str]]] = []
        while i < len(lines) and lines[i].strip().startswith("|"):
            row_line = lines[i].strip()
            cells = [cell.strip() for cell in row_line.strip("|").split("|")]
            if len(cells) == len(headers):
                rows.append((i + 1, dict(zip(headers, cells))))
            i += 1
        tables.append((headers, rows))
    return tables


def _parse_date(value: str) -> Optional[datetime]:
    if not value:
        return None
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            pass
    return _parse_ts(value)


def _days_old(date_value: str, today: Any) -> Optional[int]:
    parsed = _parse_date(date_value)
    if parsed is None:
        return None
    return (today - parsed.date()).days


def _active_ids_from_backlog(backlog_text: str) -> list[tuple[str, int]]:
    return active_pending_tokens(backlog_text)


def _all_backlog_ids(backlog_text: str) -> list[str]:
    ids = [token for token, _ in active_pending_tokens(backlog_text)]
    ids.extend(sorted(closed_surface_tokens("", backlog_text)))
    return ids


def _all_done_ids(done_text: str) -> list[str]:
    return sorted(closed_surface_tokens(done_text, ""))


def _iter_active_ids(cfg: dict[str, Any], root: Path) -> list[tuple[str, str, int]]:
    out: list[tuple[str, str, int]] = []
    backlog = _path(cfg, "followups", root)
    if backlog.exists():
        for token, line in active_pending_tokens(_read_text(backlog)):
            out.append((token, str(backlog.relative_to(root)), line))
    ideas = _path(cfg, "ideas", root)
    if ideas.exists():
        for entry in _iter_heading_entries(ideas, "IDEA", root):
            out.append((entry.token, entry.path, entry.line_no))
    for issue_file in _issue_files(cfg, root):
        for entry in _iter_heading_entries(issue_file, "ISSUE", root):
            out.append((entry.token, entry.path, entry.line_no))
    return out


def _iter_all_known_ids(cfg: dict[str, Any], root: Path) -> list[str]:
    ids = [token for token, _, _ in _iter_active_ids(cfg, root)]
    done = _path(cfg, "done", root)
    if done.exists():
        ids.extend(_all_done_ids(_read_text(done)))
    ideas = _path(cfg, "ideas", root)
    if ideas.exists():
        ids.extend(
            [entry.token for entry in _iter_heading_entries(ideas, "IDEA", root)]
        )
    for issue_file in _issue_files(cfg, root):
        ids.extend(
            [entry.token for entry in _iter_heading_entries(issue_file, "ISSUE", root)]
        )
    return sorted(set(ids))


def _strip_completion_prefix(token: str) -> str:
    for prefix in COMPLETION_PREFIXES:
        needle = f"{prefix}-"
        if token.startswith(needle):
            return token[len(needle) :]
    return token


def _parse_work_id(token: str) -> Optional[tuple[str, str, int]]:
    token = _strip_completion_prefix(token)
    match = re.match(
        r"^(IDEA|ISSUE|WORK|PLAN|IMP|EVO)-([A-Z][A-Z0-9]{1,15})-(\d{1,5})$", token
    )
    if not match:
        return None
    return match.group(1), match.group(2), int(match.group(3))


def _parse_governance_high_water(path: Path) -> dict[str, int]:
    text = _read_text(path)
    tables = _parse_markdown_tables(text)
    for headers, rows in tables:
        if {"Domain", "Code", "High-Water"}.issubset(set(headers)):
            result: dict[str, int] = {}
            for _, row in rows:
                code = row.get("Code", "").strip()
                value = row.get("High-Water", "").strip()
                if code and value.isdigit():
                    result[code] = int(value)
            return result
    return {}


_KNOWN_GAPS_START_RE = re.compile(r"^\s*<!--\s*known-gaps-start\s*-->\s*$")
_KNOWN_GAPS_END_RE = re.compile(r"^\s*<!--\s*known-gaps-end\s*-->\s*$")


def _parse_governance_known_gaps(path: Path) -> dict[str, set[int]]:
    """Read the known-gaps block from governance.md.

    Preferred format: an HTML-comment-delimited block bounded by
    ``<!-- known-gaps-start -->`` and ``<!-- known-gaps-end -->``. Every
    ``DOMAIN-NNN`` token between those markers is treated as an
    allocator-known gap that Check 1b should not flag. Explicit delimiters
    let the block carry per-gap classification on multiple lines without
    bleeding into surrounding narrative prose.

    Malformed-delimiter handling: if start or end is missing, or end appears
    before start, the parser FAILS CLOSED -- it returns no known gaps and
    emits a warning to stderr. A malformed block must not silently suppress
    real Check 1b findings.

    Legacy fallback: when neither marker is present anywhere in the file,
    fall back to the old one-line format -- the first line containing
    ``Known sequence gaps`` is scanned for ``DOMAIN-NNN`` tokens. This keeps
    downstream consumers that have not yet migrated to the delimited format
    on the prior behavior; consumers that DO use the delimiters get the
    stricter bounded-block guarantee. The legacy reader does not span
    multiple lines on purpose -- the failure mode that motivated the
    delimited format (narrative prose bleeding into the gap set) only
    affects multi-line parsing.
    """
    if not path.exists():
        return {}
    text = _read_text(path)
    lines = text.splitlines()
    start_idxs = [i for i, ln in enumerate(lines) if _KNOWN_GAPS_START_RE.match(ln)]
    end_idxs = [i for i, ln in enumerate(lines) if _KNOWN_GAPS_END_RE.match(ln)]

    if not start_idxs and not end_idxs:
        # Legacy single-line format. Scan only the first line that
        # contains the header text -- never bleed into adjacent lines.
        out_legacy: dict[str, set[int]] = {}
        for line in lines:
            if "Known sequence gaps" in line:
                for match in re.finditer(r"([A-Z][A-Z0-9]{1,15})-(\d{1,5})", line):
                    out_legacy.setdefault(match.group(1), set()).add(
                        int(match.group(2))
                    )
                return out_legacy
        return {}

    # Delimited format. Require a single, well-ordered start/end pair.
    if len(start_idxs) != 1 or len(end_idxs) != 1 or end_idxs[0] <= start_idxs[0]:
        sys.stderr.write(
            f"pm_audit: malformed known-gaps delimiters in {path}: "
            f"start_count={len(start_idxs)} end_count={len(end_idxs)} "
            f"start_idx={start_idxs} end_idx={end_idxs}. "
            "Failing closed (no known gaps recognized). "
            "Fix the block to have exactly one "
            "<!-- known-gaps-start --> and one <!-- known-gaps-end -->.\n"
        )
        return {}

    out: dict[str, set[int]] = {}
    for line in lines[start_idxs[0] + 1 : end_idxs[0]]:
        for match in re.finditer(r"([A-Z][A-Z0-9]{1,15})-(\d{1,5})", line):
            out.setdefault(match.group(1), set()).add(int(match.group(2)))
    return out


def _find_dates_descending_violations(
    items: list[tuple[str, int, str]],
) -> list[tuple[str, int, str, str]]:
    violations: list[tuple[str, int, str, str]] = []
    previous: Optional[datetime] = None
    previous_label = ""
    for label, line_no, raw in items:
        current = _parse_date(raw)
        if current is None:
            continue
        if previous is not None and current > previous:
            violations.append((label, line_no, raw, previous_label))
        previous = current
        previous_label = raw
    return violations


def _normalize_slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_taxonomy_initiatives(path: Path) -> tuple[set[str], set[str], list[str]]:
    text = _read_text(path)
    initiative_domains: set[str] = set()
    active_initiatives: set[str] = set()
    inconsistencies: list[str] = []

    in_map = False
    for line in text.splitlines():
        if re.match(r"^\s*initiative_domains:\s*$", line):
            in_map = True
            continue
        if in_map:
            if re.match(r"^\s{4}[A-Za-z0-9 _./-]+:\s*[A-Za-z0-9_-]+\s*$", line):
                name = line.strip().split(":", 1)[0]
                initiative_domains.add(name)
                continue
            if line.strip() and not line.startswith(" " * 4):
                in_map = False

    current_domain = None
    in_active = False
    for line in text.splitlines():
        domain_match = re.match(r"^\s*-\s+key:\s*([A-Za-z0-9_-]+)\s*$", line)
        if domain_match:
            current_domain = domain_match.group(1)
            in_active = False
            continue
        if re.match(r"^\s*active_initiatives:\s*$", line):
            in_active = True
            continue
        if in_active:
            item = re.match(r"^\s*-\s+(.+?)\s*$", line)
            if item:
                active_initiatives.add(item.group(1).strip())
                continue
            if line.strip() and not line.startswith(" " * 4):
                in_active = False

    if current_domain:
        pass

    return initiative_domains, active_initiatives, inconsistencies


# --------------------------------------------------------------------------- #
# Checks (each routes through emit_finding only)
# --------------------------------------------------------------------------- #


def check_1a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    """Cross-prefix collision: same DOMAIN-NNN under two active prefixes."""
    surfaces = ["followups", "ideas", "governance", "roadmap"]
    by_domain_num: dict[str, dict[str, str]] = {}
    for key in surfaces:
        path = root / cfg["paths"].get(key, "")
        if not path.exists() or path.is_dir():
            continue
        text = path.read_text(encoding="utf-8")
        for line in text.splitlines():
            visible = _strip_rename_prose(_strip_strikethrough(line))
            for prefix, domain_num in DOMAIN_NUM_RE.findall(visible):
                if prefix not in ACTIVE_PREFIXES:
                    continue
                by_domain_num.setdefault(domain_num, {})[prefix] = key
    for domain_num, prefixes in sorted(by_domain_num.items()):
        if len(prefixes) > 1:
            joined = ", ".join(f"{p}-{domain_num}" for p in sorted(prefixes))
            emit_finding(
                findings,
                check="1a",
                severity="critical",
                file=cfg["paths"]["followups"],
                line="N/A",
                issue=f"Cross-prefix ID collision: {joined} all active",
                suggested_fix="Renumber one of the colliding active items.",
                area_key=domain_num,
                kind="cross-prefix-collision",
            )


def check_1d(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    """Active-vs-closed same-prefix collision (WORK-AGT-235)."""
    backlog_path = root / cfg["paths"]["followups"]
    done_path = root / cfg["paths"]["done"]
    if not backlog_path.exists():
        return
    backlog_text = backlog_path.read_text(encoding="utf-8")
    done_text = done_path.read_text(encoding="utf-8") if done_path.exists() else ""
    closed = closed_surface_tokens(done_text, backlog_text)
    seen: set[str] = set()
    for token, line in active_pending_tokens(backlog_text):
        if token in closed and token not in seen:
            seen.add(token)
            emit_finding(
                findings,
                check="1d",
                severity="critical",
                file=cfg["paths"]["followups"],
                line=line,
                issue=(
                    f"{token} is active in {cfg['paths']['followups']} and also "
                    f"present in a closed-row surface ({cfg['paths']['done']} or "
                    "the Recently Completed tombstone)."
                ),
                suggested_fix=(
                    "Renumber the active item or remove the stale closed row; the "
                    "same exact ID must not be simultaneously active and closed."
                ),
                area_key=token,
                kind="active-vs-closed-same-prefix",
            )


def _plan_stem(stem: str) -> str:
    for suffix in ("_spec", "_plan"):
        if stem.endswith(suffix):
            return stem[: -len(suffix)]
    return stem


def check_1b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    by_domain: dict[str, set[int]] = {}
    known_gaps = _parse_governance_known_gaps(_path(cfg, "governance", root))
    for token in _iter_all_known_ids(cfg, root):
        parsed = _parse_work_id(token)
        if parsed is None:
            continue
        _, domain, number = parsed
        by_domain.setdefault(domain, set()).add(number)
    for domain, numbers in sorted(by_domain.items()):
        if not numbers:
            continue
        max_num = max(numbers)
        missing = [
            n
            for n in range(1, max_num + 1)
            if n not in numbers and n not in known_gaps.get(domain, set())
        ]
        for number in missing:
            emit_finding(
                findings,
                check="1b",
                severity="medium",
                file=cfg["paths"]["followups"],
                line="N/A",
                issue=f"Gap in active {domain} ID sequence at {domain}-{number:03d}.",
                suggested_fix=(
                    "Confirm whether the missing ID was legitimately closed, "
                    "never written, or accidentally dropped from PM tracking."
                ),
                area_key=f"{domain}-{number:03d}",
                kind="id-gap",
            )


def check_1c(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    governance = _path(cfg, "governance", root)
    if not governance.exists():
        return
    high_water = _parse_governance_high_water(governance)
    actual: dict[str, int] = {}
    for token in _iter_all_known_ids(cfg, root):
        parsed = _parse_work_id(token)
        if parsed is None:
            continue
        _, domain, number = parsed
        actual[domain] = max(number, actual.get(domain, 0))
    for domain, max_seen in sorted(actual.items()):
        recorded = high_water.get(domain)
        if recorded is None:
            continue
        if max_seen > recorded:
            emit_finding(
                findings,
                check="1c",
                severity="critical",
                file=cfg["paths"]["governance"],
                line="N/A",
                issue=(
                    f"Governance high-water for {domain} is {recorded}, but PM "
                    f"surfaces already reference {domain}-{max_seen:03d}."
                ),
                suggested_fix=(
                    "Bump the Number Allocation high-water to match the highest "
                    "tracked ID."
                ),
                area_key=f"{domain}:underflow",
                kind="high-water-underflow",
            )
        elif recorded > max_seen + 1:
            emit_finding(
                findings,
                check="1c",
                severity="medium",
                file=cfg["paths"]["governance"],
                line="N/A",
                issue=(
                    f"Governance high-water for {domain} is {recorded}, but the "
                    f"highest tracked PM ID is only {domain}-{max_seen:03d}."
                ),
                suggested_fix=(
                    "Confirm whether a reserved ID was intentionally abandoned or "
                    "whether a PM row disappeared."
                ),
                area_key=f"{domain}:overflow",
                kind="high-water-overflow",
            )


def check_2a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    required = ("Priority", "Size", "Status", "Created", "Updated")
    for issue_file in _issue_files(cfg, root):
        for entry in _iter_heading_entries(issue_file, "ISSUE", root):
            for field in required:
                if _window_has_field(entry.lines, field):
                    continue
                severity = "low" if field == "Updated" else "medium"
                emit_finding(
                    findings,
                    check="2a",
                    severity=severity,
                    file=entry.path,
                    line=entry.line_no,
                    issue=f"{entry.token} is missing required field `{field}`.",
                    suggested_fix=f"Add `**{field}:** ...` within 10 lines of the heading.",
                    area_key=f"{entry.token}:{field.lower()}",
                    kind="missing-issue-field",
                )


def check_2b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    domain_codes = cfg.get("taxonomy", {}).get("domain_codes") or {}
    if not domain_codes:
        return
    expected = {code: f"{slug}.md" for code, slug in domain_codes.items()}
    for issue_file in _issue_files(cfg, root):
        for entry in _iter_heading_entries(issue_file, "ISSUE", root):
            parsed = _parse_work_id(entry.token)
            if parsed is None:
                continue
            _, domain, _ = parsed
            wanted = expected.get(domain)
            if not wanted or issue_file.name == wanted:
                continue
            emit_finding(
                findings,
                check="2b",
                severity="high",
                file=entry.path,
                line=entry.line_no,
                issue=(
                    f"{entry.token} lives in {issue_file.name}, but domain {domain} "
                    f"maps to {wanted}."
                ),
                suggested_fix=f"Move the issue entry into `{wanted}`.",
                area_key=entry.token,
                kind="issue-domain-mismatch",
            )


def check_2c(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    done = _path(cfg, "done", root)
    if not done.exists():
        return
    allowed = tuple(f"{prefix}-" for prefix in COMPLETION_PREFIXES)
    for headers, rows in _parse_markdown_tables(_read_text(done)):
        if "ID" not in headers:
            continue
        for line_no, row in rows:
            token = row.get("ID", "").strip("` ")
            if not token:
                continue
            if token.startswith(allowed):
                continue
            emit_finding(
                findings,
                check="2c",
                severity="medium",
                file=cfg["paths"]["done"],
                line=line_no,
                issue=f"done.md row `{token}` is missing a valid resolution prefix.",
                suggested_fix="Use FIXED-/LIVE-/NOPE-/OVER-/DUPE- in the done ID column.",
                area_key=token,
                kind="done-prefix-missing",
            )


def check_2d(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    ideas = _path(cfg, "ideas", root)
    if not ideas.exists():
        return
    for entry in _iter_heading_entries(ideas, "IDEA", root):
        for field in ("Size", "Priority", "Status"):
            if _window_has_field(entry.lines, field):
                continue
            emit_finding(
                findings,
                check="2d",
                severity="medium",
                file=entry.path,
                line=entry.line_no,
                issue=f"{entry.token} is missing required field `{field}`.",
                suggested_fix=f"Add `**{field}:** ...` within 10 lines of the heading.",
                area_key=f"{entry.token}:{field.lower()}",
                kind="missing-idea-field",
            )


def check_3(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    path = _path(cfg, "followups", root)
    if not path.exists():
        return
    today = _today(cfg)
    date_re = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
    # Honor the `pm/governance.md` row convention: a trailing `~` on the
    # category column ("capability~", "cleanup~", etc.) marks a row as
    # lower-priority / nice-to-have. Such rows are skipped by Check 3 so the
    # backlog can carry intentionally-deprioritized work without emitting a
    # recurring stale-followup finding.
    lowpri_category_re = re.compile(r"\]\s+\S+~\s*\|")
    section = ""
    for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip().lower()
            continue
        if not stripped.startswith("- ") or "~~" in stripped:
            continue
        if lowpri_category_re.search(stripped):
            continue
        match = date_re.search(stripped)
        if not match:
            continue
        age = _days_old(match.group(1), today)
        if age is None:
            continue
        # Default thresholds. Time-Sensitive section uses a tight 7-day window;
        # everywhere else, accept ordinary backlog churn up to 30 days before
        # flagging. (Raised from 14 to 30 to reduce recurring noise on real
        # future work that has been deprioritized but not abandoned.)
        severity = None
        if "time-sensitive" in section and age > 7:
            severity = "high"
        elif age > 30:
            severity = "medium"
        if severity is None:
            continue
        area = _row_primary_id(stripped) or snippet_area_key(stripped)
        emit_finding(
            findings,
            check="3",
            severity=severity,
            file=cfg["paths"]["followups"],
            line=line_no,
            issue=f"{area} is {age} days old.",
            suggested_fix="Action, reprioritize, or close the stale item.",
            area_key=area,
            kind="stale-followup",
        )


def check_4(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    path = _path(cfg, "followups", root)
    if not path.exists():
        return
    today = _today(cfg)
    patterns = [
        re.compile(r"due (\d{4}-\d{2}-\d{2})", re.I),
        re.compile(r"by (\d{4}-\d{2}-\d{2})", re.I),
        re.compile(r"action by (\d{4}-\d{2}-\d{2})", re.I),
        re.compile(r"deadline[: ]+(\d{4}-\d{2}-\d{2})", re.I),
    ]
    for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
        stripped = line.strip()
        if not stripped.startswith("- ") or "~~" in stripped:
            continue
        dates = [m.group(1) for pat in patterns for m in pat.finditer(stripped)]
        if not dates:
            continue
        parsed = [_parse_date(value) for value in dates]
        parsed = [dt for dt in parsed if dt is not None]
        if not parsed:
            continue
        deadline = min(parsed).date()
        days = (deadline - today).days
        if days < 0:
            severity = "critical"
        elif days <= 7:
            severity = "high"
        elif days <= 14:
            severity = "medium"
        else:
            continue
        area = _row_primary_id(stripped) or snippet_area_key(stripped)
        emit_finding(
            findings,
            check="4",
            severity=severity,
            file=cfg["paths"]["followups"],
            line=line_no,
            issue=f"{area} has a deadline on {deadline.isoformat()} ({days} days).",
            suggested_fix="Reprioritize the item or update the deadline/progress notes.",
            area_key=area,
            kind="deadline-risk",
        )


def _likely_inflight_sessions(path: Path, stem: str) -> list[str]:
    if not path.exists():
        return []
    slug = _normalize_slug(stem)
    names: list[str] = []
    for headers, rows in _parse_markdown_tables(_read_text(path)):
        header_map = {h.lower(): h for h in headers}
        if "status" not in header_map:
            continue
        for _, row in rows:
            status = row.get(header_map["status"], "").lower()
            if "active" not in status and "running" not in status:
                continue
            haystacks = " ".join(
                row.get(col, "")
                for col in headers
                if col.lower() in {"name", "responsibility", "branch", "task"}
            )
            if slug and slug in _normalize_slug(haystacks):
                names.append(
                    row.get(header_map.get("name", ""), "").strip() or "session"
                )
    return names


def check_5(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    plans_dir = _path(cfg, "plans", root)
    archive_dir = _path(cfg, "archive", root)
    sessions = _path(cfg, "sessions", root)
    if not plans_dir.exists():
        return
    archive_stems = set()
    if archive_dir.exists():
        for plan in archive_dir.glob("*.md"):
            archive_stems.add(_plan_stem(plan.stem))
    markers = (
        "status: implemented",
        "status: done",
        "status: complete",
        "status: shipped",
    )
    for plan in sorted(plans_dir.glob("*.md")):
        stem = _plan_stem(plan.stem)
        head = "\n".join(_read_text(plan).splitlines()[:20]).lower()
        duplicate_path = archive_dir / plan.name
        marker_hit = any(marker in head for marker in markers)
        archive_hit = stem in archive_stems
        duplicate_hit = duplicate_path.exists()
        if not (duplicate_hit or marker_hit or archive_hit):
            continue
        inflight = _likely_inflight_sessions(sessions, stem)
        severity = "low" if inflight else ("critical" if duplicate_hit else "high")
        note = f" likely in-flight by {', '.join(inflight)}." if inflight else ""
        emit_finding(
            findings,
            check="5",
            severity=severity,
            file=str(plan.relative_to(root)),
            line="N/A",
            issue=(
                f"{plan.name} looks completed but is still in {cfg['paths']['plans']}."
                f"{note}"
            ),
            suggested_fix=f"Archive the plan/spec pair to {cfg['paths']['archive']}.",
            area_key=stem,
            kind="unarchived-plan",
        )


def check_6(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    entries = cfg["paths"].get("version_files") or []
    if not entries:
        return
    versions: dict[str, str] = {}
    for entry in entries:
        path_part, _, regex = str(entry).partition(":")
        path = root / path_part
        if not path.exists():
            emit_finding(
                findings,
                check="6",
                severity="medium",
                file=path_part,
                line="N/A",
                issue=f"Configured version file {path_part} does not exist.",
                suggested_fix="Fix the version_files config or restore the file.",
                area_key=f"{path_part}:missing",
                kind="version-file-missing",
            )
            continue
        match = re.search(regex, _read_text(path), re.M)
        if match:
            versions[path_part] = match.group(1)
    distinct = set(versions.values())
    if len(distinct) > 1:
        emit_finding(
            findings,
            check="6",
            severity="critical",
            file=cfg["paths"].get("changelog", "version_files"),
            line="N/A",
            issue=f"Version mismatch across files: {versions}.",
            suggested_fix="Reconcile all version files to one value.",
            area_key="version-parity",
            kind="version-mismatch",
        )


def check_7(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    changelog = _path(cfg, "changelog", root)
    if not changelog.exists():
        return
    text = _read_text(changelog)
    unrel = re.search(r"(?ms)^## \[Unreleased\]\s*$([\s\S]*?)(?=^## |\Z)", text)
    version = re.search(r"(?m)^## \[v\d+\.\d+\.\d+\] .+?(\d{4}-\d{2}-\d{2})\s*$", text)
    if not unrel or not version:
        return
    body = [
        line
        for line in unrel.group(1).splitlines()
        if line.strip() and not line.strip().startswith("###")
    ]
    if not body:
        return
    today = _today(cfg)
    days = _days_old(version.group(1), today)
    if days is None or days <= 7:
        return
    severity = "high" if days > 14 else "medium"
    emit_finding(
        findings,
        check="7",
        severity=severity,
        file=cfg["paths"]["changelog"],
        line="N/A",
        issue=f"CHANGELOG has unreleased content {days} days after the last release.",
        suggested_fix="Cut a release bucket or trim stale unreleased entries.",
        area_key="changelog-unreleased-aging",
        kind="changelog-aging",
    )


def check_8(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    index = _path(cfg, "index", root)
    if not index.exists():
        return
    text = _read_text(index)
    for target in re.findall(r"]\(([^)]+)\)", text):
        if target.startswith("#") or target.startswith("http"):
            continue
        clean = target.split("#", 1)[0]
        resolved = (index.parent / clean).resolve()
        if resolved.exists():
            continue
        emit_finding(
            findings,
            check="8",
            severity="high",
            file=cfg["paths"]["index"],
            line="N/A",
            issue=f"INDEX links to non-existent target: {target}",
            suggested_fix="Fix or remove the broken link target.",
            area_key=clean,
            kind="broken-doc-link",
        )


def check_9(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    sessions = _path(cfg, "sessions", root)
    if not sessions.exists():
        return
    now = _now_utc()
    for headers, rows in _parse_markdown_tables(_read_text(sessions)):
        lower = {h.lower(): h for h in headers}
        if not {"last active", "status"}.issubset(lower):
            continue
        for line_no, row in rows:
            last_active = row.get(lower["last active"], "").strip()
            status = row.get(lower["status"], "").lower()
            name = row.get(lower.get("name", ""), "").strip()
            worktree = row.get(lower.get("worktree", ""), "").strip()
            if last_active in {"-", "—", ""}:
                continue
            parsed = _parse_date(last_active)
            if parsed is None:
                continue
            age_hours = (now - parsed).total_seconds() / 3600
            # A row with a populated `Worktree` column is a real agent session
            # that the daemon discovered via session-log inference but that
            # never wrote a `state-<uuid>.md` file (so the `Name` column stays
            # blank). That is structural Codex/agent-sync behavior, not a
            # hygiene problem -- skip the unnamed-row rule in that case. The
            # running/active age rules still apply.
            #
            # `agent-sync` writes the literal string `[missing]` into the
            # Worktree column when the underlying worktree directory has been
            # deleted from disk (e.g., `.codex/worktrees/foo [missing]`). A
            # row carrying `[missing]` is no longer a real anchor and must be
            # treated as unanchored so the ghost-session cleanup signal still
            # surfaces.
            unnamed = name in {"-", "—", ""}
            has_worktree = (
                worktree not in {"-", "—", ""} and "[missing]" not in worktree
            )
            severity = None
            if "running" in status and age_hours > 24:
                severity = "medium"
            elif "active" in status and age_hours > 24 * 7:
                severity = "low"
            elif unnamed and not has_worktree:
                severity = "low"
            if severity is None:
                continue
            issue = (
                f"Session `{name or 'unnamed'}` has status `{status}` and last active "
                f"{last_active}."
            )
            emit_finding(
                findings,
                check="9",
                severity=severity,
                file=cfg["paths"]["sessions"],
                line=line_no,
                issue=issue,
                suggested_fix="Close, refresh, or rename the stale session row.",
                area_key=name or f"row-{line_no}",
                kind="stale-session",
            )


def _find_session_status_by_id(sessions_text: str, session_id: str) -> Optional[str]:
    for headers, rows in _parse_markdown_tables(sessions_text):
        lower = {h.lower(): h for h in headers}
        if "session id" not in lower and "id" not in lower:
            continue
        id_col = lower.get("session id") or lower.get("id")
        status_col = lower.get("status")
        for _, row in rows:
            if row.get(id_col, "").strip() == session_id:
                return row.get(status_col, "").strip() if status_col else ""
    return None


def check_10a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    active_work = _path(cfg, "active_work", root)
    if not active_work.exists():
        return
    today = _today(cfg)
    for headers, rows in _parse_markdown_tables(_read_text(active_work)):
        lower = {h.lower(): h for h in headers}
        if not {"status", "updated"}.issubset(lower):
            continue
        id_col = lower.get("work item") or lower.get("id") or headers[0]
        for line_no, row in rows:
            status = row.get(lower["status"], "").lower()
            updated = row.get(lower["updated"], "")
            days = _days_old(updated, today)
            if days is None:
                continue
            severity = None
            if "active" in status and days > 7:
                severity = "medium"
            elif "blocked" in status and days > 3:
                severity = "high"
            if severity is None:
                continue
            area = row.get(id_col, "").strip() or f"row-{line_no}"
            emit_finding(
                findings,
                check="10a",
                severity=severity,
                file=cfg["paths"]["active_work"],
                line=line_no,
                issue=f"{area} is `{status}` with Updated={updated}.",
                suggested_fix="Refresh the row or resolve the stale active/block state.",
                area_key=area,
                kind="active-work-stale",
            )


def check_10b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    active_work = _path(cfg, "active_work", root)
    sessions = _path(cfg, "sessions", root)
    if not active_work.exists():
        return
    sessions_text = _read_text(sessions) if sessions.exists() else ""
    for headers, rows in _parse_markdown_tables(_read_text(active_work)):
        lower = {h.lower(): h for h in headers}
        if "status" not in lower:
            continue
        session_col = lower.get("session id") or lower.get("session")
        id_col = lower.get("work item") or lower.get("id") or headers[0]
        if not session_col:
            continue
        for line_no, row in rows:
            session_id = row.get(session_col, "").strip()
            if not session_id:
                continue
            status = _find_session_status_by_id(sessions_text, session_id)
            if status and any(flag in status.lower() for flag in ("running", "active")):
                continue
            area = row.get(id_col, "").strip() or f"row-{line_no}"
            emit_finding(
                findings,
                check="10b",
                severity="high",
                file=cfg["paths"]["active_work"],
                line=line_no,
                issue=f"{area} references orphaned or inactive session `{session_id}`.",
                suggested_fix="Remove the orphaned row or reactivate the owning session.",
                area_key=area,
                kind="active-work-orphaned",
            )


def _count_issue_statuses(cfg: dict[str, Any], root: Path) -> dict[str, int]:
    counts = {"open": 0, "resolved": 0, "graduated": 0, "deferred": 0}
    for issue_file in _issue_files(cfg, root):
        for entry in _iter_heading_entries(issue_file, "ISSUE", root):
            status_line = next(
                (
                    line
                    for line in entry.lines[:10]
                    if line.strip().startswith("**Status:**")
                ),
                "",
            )
            status = (
                status_line.split("**Status:**", 1)[-1].strip().lower().split() or [""]
            )[0]
            if status in counts:
                counts[status] += 1
    return counts


def check_11a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    tracker = _path(cfg, "issue_tracker", root)
    if not tracker.exists():
        return
    text = _read_text(tracker)
    match = re.search(r"(?im)^last updated:\s*(\d{4}-\d{2}-\d{2})\s*$", text)
    if not match:
        return
    days = _days_old(match.group(1), _today(cfg))
    if days is None or days <= 7:
        return
    emit_finding(
        findings,
        check="11a",
        severity="low",
        file=cfg["paths"]["issue_tracker"],
        line="N/A",
        issue=f"Issue tracker last updated {days} days ago.",
        suggested_fix="Refresh the issue tracker counts/statuses.",
        area_key="issue-tracker-last-updated",
        kind="issue-tracker-stale",
    )


def check_11b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    tracker = _path(cfg, "issue_tracker", root)
    if not tracker.exists():
        return
    text = _read_text(tracker).lower()
    source = _count_issue_statuses(cfg, root)
    tracker_open = None
    tracker_resolved = None
    open_match = re.search(r"open[^0-9]{0,20}(\d+)", text)
    resolved_match = re.search(r"resolved[^0-9]{0,20}(\d+)", text)
    if open_match:
        tracker_open = int(open_match.group(1))
    if resolved_match:
        tracker_resolved = int(resolved_match.group(1))
    if tracker_open is not None and tracker_open != source["open"] + source["deferred"]:
        emit_finding(
            findings,
            check="11b",
            severity="medium",
            file=cfg["paths"]["issue_tracker"],
            line="N/A",
            issue=(
                f"Issue tracker open count is {tracker_open}, but source issue files "
                f"show {source['open'] + source['deferred']} open/deferred items."
            ),
            suggested_fix="Refresh the tracker counts from the issue source files.",
            area_key="issue-tracker-open-count",
            kind="issue-tracker-count-mismatch",
        )
    if tracker_resolved is not None and tracker_resolved != source["resolved"]:
        emit_finding(
            findings,
            check="11b",
            severity="medium",
            file=cfg["paths"]["issue_tracker"],
            line="N/A",
            issue=(
                f"Issue tracker resolved count is {tracker_resolved}, but source issue "
                f"files show {source['resolved']} resolved items."
            ),
            suggested_fix="Refresh the tracker counts from the issue source files.",
            area_key="issue-tracker-resolved-count",
            kind="issue-tracker-count-mismatch",
        )


def _changelog_versions(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return set(re.findall(r"(?m)^## \[(v\d+\.\d+\.\d+)\]", _read_text(path)))


def check_12a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    registry = _path(cfg, "registry", root)
    changelog = _path(cfg, "changelog", root)
    if not registry.exists() or not changelog.exists():
        return
    versions = _changelog_versions(changelog)
    for line_no, line in enumerate(_read_text(registry).splitlines(), start=1):
        for version in re.findall(r"\bv\d+\.\d+\.\d+\b", line):
            if version in versions:
                continue
            emit_finding(
                findings,
                check="12a",
                severity="high",
                file=cfg["paths"]["registry"],
                line=line_no,
                issue=f"Registry references {version}, but CHANGELOG has no matching header.",
                suggested_fix="Add the versioned CHANGELOG entry or fix the registry version.",
                area_key=version,
                kind="registry-version-missing",
            )


def check_12b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    registry = _path(cfg, "registry", root)
    taxonomy = root / cfg.get("taxonomy", {}).get("file", "")
    if not registry.exists() or not taxonomy.exists():
        return
    initiative_domains, active_initiatives, _ = _parse_taxonomy_initiatives(taxonomy)
    registry_text = _read_text(registry)
    registry_names = set()
    for headers, rows in _parse_markdown_tables(registry_text):
        if "Items" not in headers:
            continue
        name_col = headers[0]
        for _, row in rows:
            name = row.get(name_col, "").strip().strip("*")
            if name:
                registry_names.add(name)
    for name in sorted(initiative_domains - registry_names):
        emit_finding(
            findings,
            check="12b",
            severity="medium",
            file=cfg["paths"]["registry"],
            line="N/A",
            issue=f"Taxonomy initiative `{name}` is missing from the registry.",
            suggested_fix="Add the initiative to the active registry table or drop it from taxonomy.",
            area_key=name,
            kind="taxonomy-registry-missing",
        )
    for name in sorted(registry_names - initiative_domains - active_initiatives):
        emit_finding(
            findings,
            check="12b",
            severity="medium",
            file=cfg["paths"]["registry"],
            line="N/A",
            issue=f"Registry initiative `{name}` is missing from taxonomy.",
            suggested_fix="Add the initiative to taxonomy or remove the stale registry row.",
            area_key=name,
            kind="registry-taxonomy-missing",
        )


def check_13(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    pattern = cfg["paths"].get("governance_roadmaps") or "docs/governance/*roadmap*.md"
    files = sorted(root.glob(pattern))
    changelog_versions = _changelog_versions(_path(cfg, "changelog", root))
    if not files:
        return
    for path in files:
        for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
            versions = re.findall(r"\bv\d+\.\d+\.\d+\b", line)
            if not versions or ("done" not in line.lower() and "~~" not in line):
                continue
            for version in versions:
                if version in changelog_versions:
                    continue
                emit_finding(
                    findings,
                    check="13",
                    severity="medium",
                    file=str(path.relative_to(root)),
                    line=line_no,
                    issue=f"Roadmap marks work done with {version}, but CHANGELOG is missing it.",
                    suggested_fix="Add the release to CHANGELOG or correct the roadmap version.",
                    area_key=f"{path.name}:{version}",
                    kind="roadmap-version-missing",
                )


def check_14a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    source_dirs = cfg["paths"].get("source_dirs") or []
    exts = set(cfg["paths"].get("source_extensions") or [])
    reference_dir = _path(cfg, "reference", root)
    if not source_dirs or not exts or not reference_dir.exists():
        return
    reference_text = "\n".join(
        _read_text(path)
        for path in sorted(reference_dir.rglob("*.md"))
        if path.is_file()
    ).lower()
    backlog_text = (
        _read_text(_path(cfg, "followups", root))
        if _path(cfg, "followups", root).exists()
        else ""
    )
    excluded = {
        "__init__",
        "version",
        "conftest",
        "index",
        "mod",
    }
    for rel_dir in source_dirs:
        base = root / rel_dir
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix not in exts:
                continue
            if any(part in {"tests", "test", "pages"} for part in path.parts):
                continue
            stem = path.stem
            if stem in excluded:
                continue
            if stem.lower() in reference_text or stem in backlog_text:
                continue
            emit_finding(
                findings,
                check="14a",
                severity="low",
                file=str(path.relative_to(root)),
                line="N/A",
                issue=f"Source module `{path.name}` has no obvious reference-doc mention.",
                suggested_fix="Add or link a reference doc, or pin the gap in backlog/registry.",
                area_key=str(path.relative_to(root)),
                kind="missing-reference-doc",
            )


def check_14b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    taxonomy = root / cfg.get("taxonomy", {}).get("file", "")
    if not taxonomy.exists():
        return
    text = _read_text(taxonomy)
    domains = re.findall(r"(?m)^\s*-\s+key:\s*([A-Za-z0-9_-]+)\s*$", text)
    for domain in domains:
        if re.search(
            rf"(?ms)-\s+key:\s*{re.escape(domain)}.*?reference_docs:\s*\[\s*\]", text
        ):
            emit_finding(
                findings,
                check="14b",
                severity="low",
                file=cfg.get("taxonomy", {}).get("file", ""),
                line="N/A",
                issue=f"Taxonomy domain `{domain}` has an empty reference_docs list.",
                suggested_fix="Add reference docs or confirm the domain intentionally has none.",
                area_key=domain,
                kind="taxonomy-reference-gap",
            )


def check_15a(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    done = _path(cfg, "done", root)
    if not done.exists():
        return
    for headers, rows in _parse_markdown_tables(_read_text(done)):
        if "Closed" not in headers:
            continue
        items = [
            (row.get("ID", "").strip(), line_no, row.get("Closed", "").strip())
            for line_no, row in rows
            if row.get("Closed", "").strip()
        ]
        for label, line_no, raw, prev in _find_dates_descending_violations(items):
            emit_finding(
                findings,
                check="15a",
                severity="low",
                file=cfg["paths"]["done"],
                line=line_no,
                issue=f"done.md is out of descending order at `{label}` ({raw} after {prev}).",
                suggested_fix="Keep the newest completion rows at the top of the table.",
                area_key=label or f"row-{line_no}",
                kind="insertion-order",
            )
        return


def check_15b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    backlog = _path(cfg, "followups", root)
    if not backlog.exists():
        return
    date_re = re.compile(r"\|\s*(\d{4}-\d{2}-\d{2})\s*\|")
    groups: dict[str, list[tuple[str, int, str]]] = {}
    section = ""
    for line_no, line in enumerate(_read_text(backlog).splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:].strip()
            continue
        if not stripped.startswith("- ") or "~~" in stripped:
            continue
        match = date_re.search(stripped)
        if not match:
            continue
        groups.setdefault(section or "Pending", []).append(
            (_row_primary_id(stripped) or stripped[:40], line_no, match.group(1))
        )
    for section, items in groups.items():
        for label, line_no, raw, prev in _find_dates_descending_violations(items):
            emit_finding(
                findings,
                check="15b",
                severity="low",
                file=cfg["paths"]["followups"],
                line=line_no,
                issue=f"Backlog section `{section}` is out of newest-first order at `{label}`.",
                suggested_fix="Reorder active backlog rows newest-first within the section.",
                area_key=f"{section}:{label}",
                kind="insertion-order",
            )


def check_15c(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    for issue_file in _issue_files(cfg, root):
        items: list[tuple[str, int, str]] = []
        for entry in _iter_heading_entries(issue_file, "ISSUE", root):
            created = next(
                (
                    line.split("**Created:**", 1)[-1].strip()
                    for line in entry.lines[:10]
                    if line.strip().startswith("**Created:**")
                ),
                "",
            )
            if created:
                items.append((entry.token, entry.line_no, created))
        for label, line_no, raw, prev in _find_dates_descending_violations(items):
            emit_finding(
                findings,
                check="15c",
                severity="low",
                file=str(issue_file.relative_to(root)),
                line=line_no,
                issue=f"{issue_file.name} is out of newest-first Created order at `{label}`.",
                suggested_fix="Keep newer issue headings above older ones in the same file.",
                area_key=label,
                kind="insertion-order",
            )


def check_15d(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    ideas = _path(cfg, "ideas", root)
    if not ideas.exists():
        return
    items: list[tuple[str, int, str]] = []
    for entry in _iter_heading_entries(ideas, "IDEA", root):
        date = next(
            (
                line.split("**Date:**", 1)[-1].strip()
                for line in entry.lines[:10]
                if line.strip().startswith("**Date:**")
            ),
            "",
        )
        if date:
            items.append((entry.token, entry.line_no, date))
    for label, line_no, raw, prev in _find_dates_descending_violations(items):
        emit_finding(
            findings,
            check="15d",
            severity="low",
            file=cfg["paths"]["ideas"],
            line=line_no,
            issue=f"Ideas are out of newest-first order at `{label}`.",
            suggested_fix="Reorder idea entries newest-first within their domain section.",
            area_key=label,
            kind="insertion-order",
        )


def check_16b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    manifest = _path(cfg, "tag_manifest", root)
    if not manifest.exists():
        return
    manifest_text = _read_text(manifest)
    match = re.search(r"(?im)^last updated:\s*(\d{4}-\d{2}-\d{2})\s*$", manifest_text)
    since = match.group(1) if match else ""
    since_dt = _parse_date(since)
    if since_dt is None:
        since_dt = datetime.combine(
            _today(cfg), datetime.min.time(), tzinfo=timezone.utc
        ) - timedelta(days=14)
    candidates: list[Path] = []
    for key in ("reference", "governance_dir", "plans"):
        base = _path(cfg, key, root)
        if base.is_file():
            candidates.append(base)
        elif base.exists():
            candidates.extend(p for p in base.rglob("*.md") if p.is_file())
    for path in sorted(set(candidates)):
        if datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc) <= since_dt:
            continue
        section = ""
        for line_no, line in enumerate(_read_text(path).splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                section = stripped.lower()
                continue
            if not stripped.startswith("- "):
                continue
            if "<!--" in stripped or re.search(r"\[[A-Z]+-[A-Z0-9-]+\]", stripped):
                continue
            if not any(
                key in section
                for key in (
                    "future work",
                    "known limitations",
                    "planned",
                    "todo",
                    "roadmap",
                )
            ):
                continue
            emit_finding(
                findings,
                check="16b",
                severity="low",
                file=str(path.relative_to(root)),
                line=line_no,
                issue="Recently modified doc contains an untagged trackable bullet.",
                suggested_fix="Add an inline WORK/IDEA/PLAN tag or promote the item into PM tracking.",
                area_key=f"{path.name}:{line_no}",
                kind="untagged-trackable-item",
            )


def check_16c(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    manifest = _path(cfg, "tag_manifest", root)
    if not manifest.exists():
        return
    text = _read_text(manifest)
    match = re.search(r"(?im)^last updated:\s*(\d{4}-\d{2}-\d{2})\s*$", text)
    if not match:
        return
    days = _days_old(match.group(1), _today(cfg))
    if days is None or days <= 7:
        return
    emit_finding(
        findings,
        check="16c",
        severity="low",
        file=cfg["paths"]["tag_manifest"],
        line="N/A",
        issue=f"Tag manifest last updated {days} days ago.",
        suggested_fix="Run tag maintenance and refresh the manifest date/counts.",
        area_key="tag-manifest-stale",
        kind="tag-manifest-stale",
    )


def _parse_registry_children(
    text: str,
) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    active: dict[str, set[str]] = {}
    backlog: dict[str, set[str]] = {}
    for headers, rows in _parse_markdown_tables(text):
        if "Items" in headers:
            name_col = headers[0]
            for _, row in rows:
                name = row.get(name_col, "").strip().strip("*")
                items = row.get("Items", "").strip()
                if not name or items in {"", "—", "-"}:
                    continue
                ids = set()
                for token in re.findall(r"WORK-[A-Z][A-Z0-9]{1,15}-\d{1,5}", items):
                    ids.add(token)
                active[name] = ids
        for _, line in enumerate(text.splitlines(), start=1):
            pass
    current_initiative = ""
    for line in text.splitlines():
        if line.strip().startswith("### "):
            current_initiative = line.strip()[4:].strip()
        for token in re.findall(
            r"<!--\s*(WORK-[A-Z][A-Z0-9]{1,15}-\d{1,5})\s*-->", line
        ):
            backlog.setdefault(current_initiative or "Backlog", set()).add(token)
    return active, backlog


def check_17(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    registry = _path(cfg, "registry", root)
    if not registry.exists():
        return
    active, backlog = _parse_registry_children(_read_text(registry))
    for initiative, child_ids in active.items():
        tagged = backlog.get(initiative, set())
        for token in sorted(tagged - child_ids):
            emit_finding(
                findings,
                check="17",
                severity="medium",
                file=cfg["paths"]["registry"],
                line="N/A",
                issue=f"{initiative} backlog row tags `{token}` but Active Items omits it.",
                suggested_fix="Update the initiative's Items column to include the tagged child.",
                area_key=f"{initiative}:{token}",
                kind="initiative-child-drift",
            )
        for token in sorted(child_ids - tagged):
            emit_finding(
                findings,
                check="17",
                severity="medium",
                file=cfg["paths"]["registry"],
                line="N/A",
                issue=f"{initiative} Items lists `{token}` but no backlog row carries that tag.",
                suggested_fix="Retag the backlog row or trim the stale Items entry.",
                area_key=f"{initiative}:{token}",
                kind="initiative-child-drift",
            )


def _completed_scope_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    section = _section(_read_text(path), "Completed Scope")
    return {token for token in re.findall(r"WORK-[A-Z][A-Z0-9]{1,15}-\d{1,5}", section)}


def check_18b(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    current = _path(cfg, "current_sprint", root)
    ids = _completed_scope_ids(current)
    if not ids:
        return
    backlog_text = _read_text(_path(cfg, "followups", root))
    active = {token for token, _ in active_pending_tokens(backlog_text)}
    for token in sorted(ids & active):
        emit_finding(
            findings,
            check="18b",
            severity="high",
            file=cfg["paths"]["followups"],
            line="N/A",
            issue=f"Sprint-completed item `{token}` still appears active in backlog.",
            suggested_fix="Strike through the backlog row or move the work into done.md.",
            area_key=token,
            kind="sprint-item-still-active",
        )


def check_18c(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    current = _path(cfg, "current_sprint", root)
    ids = _completed_scope_ids(current)
    if not ids:
        return
    done_ids = set(_all_done_ids(_read_text(_path(cfg, "done", root))))
    for token in sorted(ids):
        if token in done_ids or any(
            f"{prefix}-{token}" in done_ids for prefix in COMPLETION_PREFIXES
        ):
            continue
        emit_finding(
            findings,
            check="18c",
            severity="high",
            file=cfg["paths"]["done"],
            line="N/A",
            issue=f"Sprint-completed item `{token}` has no done.md closure row.",
            suggested_fix="Add a done.md row for the completed sprint item.",
            area_key=token,
            kind="sprint-item-missing-done",
        )


def check_18d(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    backlog = _path(cfg, "followups", root)
    if not backlog.exists():
        return
    seen: dict[str, int] = {}
    for token, line_no in active_pending_tokens(_read_text(backlog)):
        if token in seen:
            emit_finding(
                findings,
                check="18d",
                severity="medium",
                file=cfg["paths"]["followups"],
                line=line_no,
                issue=f"Duplicate active backlog row for `{token}`.",
                suggested_fix="Strike through or merge the later duplicate filing.",
                area_key=token,
                kind="duplicate-active-backlog-id",
            )
        else:
            seen[token] = line_no


def check_19(root: Path, cfg: dict[str, Any], findings: list[Finding]) -> None:
    done = _path(cfg, "done", root)
    if not done.exists():
        return
    text = _read_text(done)
    tables = _parse_markdown_tables(text)
    if not tables:
        return
    today = _today(cfg)
    notes = set(re.findall(r"(?m)^###\s+(IMP-[A-Z][A-Z0-9]{1,15}-\d{1,5})\b", text))
    for headers, rows in tables:
        if not {"ID", "Closed", "Description"}.issubset(set(headers)):
            continue
        for line_no, row in rows:
            token = row.get("ID", "").strip("` ")
            closed = row.get("Closed", "")
            description = row.get("Description", "")
            days = _days_old(closed, today)
            if days is None or days > 14:
                continue
            if token.startswith(("OVER-", "DUPE-", "NOPE-")):
                continue
            if len(description) < 40 and "config" in description.lower():
                continue
            parsed = _parse_work_id(token)
            if parsed is None:
                continue
            _, domain, number = parsed
            imp = f"IMP-{domain}-{number:03d}"
            if imp in notes:
                continue
            emit_finding(
                findings,
                check="19",
                severity="medium",
                file=cfg["paths"]["done"],
                line=line_no,
                issue=f"Recently closed item `{token}` is missing Implementation Notes `{imp}`.",
                suggested_fix="Ask the implementing agent to add an IMP notes block or document the omission.",
                area_key=token,
                kind="missing-implementation-notes",
            )
        return


# Lowest-level tokens the runner mechanizes, mapped to their implementation.
CHECK_REGISTRY: dict[str, Callable[[Path, dict[str, Any], list[Finding]], None]] = {
    "1a": check_1a,
    "1b": check_1b,
    "1c": check_1c,
    "1d": check_1d,
    "2a": check_2a,
    "2b": check_2b,
    "2c": check_2c,
    "2d": check_2d,
    "3": check_3,
    "4": check_4,
    "5": check_5,
    "6": check_6,
    "7": check_7,
    "8": check_8,
    "9": check_9,
    "10a": check_10a,
    "10b": check_10b,
    "11a": check_11a,
    "11b": check_11b,
    "12a": check_12a,
    "12b": check_12b,
    "13": check_13,
    "14a": check_14a,
    "14b": check_14b,
    "15a": check_15a,
    "15b": check_15b,
    "15c": check_15c,
    "15d": check_15d,
    "16b": check_16b,
    "16c": check_16c,
    "17": check_17,
    "18b": check_18b,
    "18c": check_18c,
    "18d": check_18d,
    "19": check_19,
}

SUBCHECK_MAP: dict[str, list[str]] = {
    "1": ["1a", "1b", "1c", "1d"],
    "2": ["2a", "2b", "2c", "2d"],
    "3": ["3"],
    "4": ["4"],
    "5": ["5"],
    "6": ["6"],
    "7": ["7"],
    "8": ["8"],
    "9": ["9"],
    "10": ["10a", "10b"],
    "11": ["11a", "11b"],
    "12": ["12a", "12b"],
    "13": ["13"],
    "14": ["14a", "14b"],
    "15": ["15a", "15b", "15c", "15d"],
    "16": ["16b", "16c"],
    "17": ["17"],
    "18": ["18b", "18c", "18d"],
    "19": ["19"],
    "20": ["20"],
    "21": ["21"],
    "22": ["22"],
    "23": ["23"],
    "24": ["24"],
}

CODEGRAPH_KINDS = {
    "20": "dead-code",
    "21": "complexity",
    "22": "orphan-module",
    "23": "cycle",
    "24": "refactor-impact",
}

CODEGRAPH_SEVERITY = {
    "20": "low",
    "21": "low",
    "22": "low",
    "23": "medium",
    "24": "high",
}


# --------------------------------------------------------------------------- #
# CodeGraph bundle adapter
# --------------------------------------------------------------------------- #


def normalize_codegraph_bundle(
    bundle: dict[str, Any],
    findings: list[Finding],
    requested: set[str],
    cfg: dict[str, Any],
) -> set[str]:
    """Normalize a CodeGraph handoff bundle into the shared finding schema.

    Returns the set of canonical CodeGraph tokens the bundle actually provided
    data for so the caller can mark requested-but-absent tokens skipped.
    """
    provided: set[str] = set()
    for item in bundle.get("findings", []):
        token = canonical_token(item.get("check", ""))
        if token not in requested:
            continue
        provided.add(token)
        kind = item.get("kind") or CODEGRAPH_KINDS.get(token, "codegraph")
        path = item.get("path", "")
        symbol = item.get("symbol")
        metadata = item.get("metadata") or {}
        if token == "23":
            members = metadata.get("members_sorted")
            if not members:
                members = sorted(item.get("members", []) or [path])
            area_key = "+".join(sorted(str(m) for m in members))
        elif token == "24":
            anchor = metadata.get("anchor_symbol") or symbol or path
            plan_ref = metadata.get("plan_ref", "")
            area_key = f"{anchor}@{plan_ref}" if plan_ref else str(anchor)
        elif token in ("20", "21"):
            area_key = symbol or path
        else:  # 22 orphan module — path-based
            area_key = path
        emit_finding(
            findings,
            check=token,
            severity=str(
                item.get("severity") or CODEGRAPH_SEVERITY.get(token, "low")
            ).lower(),
            file=path,
            line=symbol or "N/A",
            issue=item.get("summary", f"CodeGraph {kind} finding"),
            suggested_fix="Review the CodeGraph signal; confirm before acting.",
            area_key=str(area_key),
            kind=kind,
            summary=item.get("summary", ""),
        )
    return provided


# --------------------------------------------------------------------------- #
# Report persistence + structured-block reload
# --------------------------------------------------------------------------- #


def extract_structured(text: str) -> Optional[dict[str, Any]]:
    start = text.find(STRUCT_START)
    end = text.find(STRUCT_END)
    if start < 0 or end < 0 or end < start:
        return None
    block = text[start + len(STRUCT_START) : end]
    match = re.search(r"```json\s*(.*?)```", block, re.S)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    if "metadata" not in payload or "findings" not in payload:
        return None
    return payload


@dataclass
class PriorReport:
    path: Path
    run_timestamp: str
    executed_checks: set[str]
    findings: list[dict[str, Any]]


def load_prior_reports(
    reports_dir: Path, exclude: Optional[Path] = None
) -> tuple[list[PriorReport], list[str]]:
    """Load valid ``audit-*.md`` baselines newest-first; collect warnings.

    Only ``audit-*.md`` artifacts are scanned. ``pm_report_*.md`` and
    ``pm_context_latest.md`` (the project-manager agent's files) are ignored.
    """
    warnings: list[str] = []
    reports: list[PriorReport] = []
    if not reports_dir.exists():
        return reports, warnings
    for path in sorted(reports_dir.glob("audit-*.md")):
        if exclude and path.resolve() == Path(exclude).resolve():
            continue
        payload = extract_structured(path.read_text(encoding="utf-8"))
        if payload is None:
            warnings.append(
                f"baseline skipped (malformed structured block): {path.name}"
            )
            continue
        meta = payload.get("metadata", {})
        reports.append(
            PriorReport(
                path=path,
                run_timestamp=str(meta.get("run_timestamp", "")),
                executed_checks={
                    canonical_token(c) for c in meta.get("executed_checks", [])
                },
                findings=payload.get("findings", []),
            )
        )
    reports.sort(key=lambda r: r.run_timestamp, reverse=True)
    return reports, warnings


# --------------------------------------------------------------------------- #
# Delta classification
# --------------------------------------------------------------------------- #


def classify_deltas(
    findings: list[Finding],
    prior_reports: list[PriorReport],
    executed: set[str],
    run_timestamp: str,
) -> dict[str, list[dict[str, Any]]]:
    """Classify current findings + surface resolved/not-re-evaluated buckets.

    Baselines resolve per canonical check token: for each token that ran now we
    use the newest prior report that also executed that token.
    """
    baseline_for_token: dict[str, PriorReport] = {}
    for token in executed:
        for report in prior_reports:  # already newest-first
            if token in report.executed_checks:
                baseline_for_token[token] = report
                break

    # Index baseline findings by token.
    def baseline_findings(token: str) -> list[dict[str, Any]]:
        report = baseline_for_token.get(token)
        if not report:
            return []
        return [f for f in report.findings if canonical_token(f.get("check")) == token]

    matched_signatures: dict[str, set[str]] = {}
    for finding in findings:
        token = finding.check
        base = baseline_findings(token)
        if not base and token not in baseline_for_token:
            finding.delta_status = "new"
            finding.first_seen = run_timestamp
            finding.repeat_count = 1
            continue
        by_sig = {b["issue_signature"]: b for b in base}
        by_area = {}
        for b in base:
            by_area.setdefault(b.get("area_key"), b)
        if finding.issue_signature in by_sig:
            prior = by_sig[finding.issue_signature]
            finding.delta_status = "repeat"
            finding.first_seen = prior.get("first_seen", run_timestamp)
            finding.repeat_count = int(prior.get("repeat_count", 1)) + 1
            if prior.get("severity") and prior["severity"] != finding.severity:
                finding.severity_change = f"{prior['severity']}->{finding.severity}"
            matched_signatures.setdefault(token, set()).add(finding.issue_signature)
        elif finding.area_key in by_area:
            prior = by_area[finding.area_key]
            finding.delta_status = "post-fix-drift"
            finding.first_seen = prior.get("first_seen", run_timestamp)
            finding.repeat_count = int(prior.get("repeat_count", 1)) + 1
            finding.prior_signature = prior.get("issue_signature", "")
            matched_signatures.setdefault(token, set()).add(prior["issue_signature"])
        else:
            finding.delta_status = "new"
            finding.first_seen = run_timestamp
            finding.repeat_count = 1

    # Resolved: prior signatures (for tokens that ran now) absent from current.
    resolved: list[dict[str, Any]] = []
    for token, report in baseline_for_token.items():
        matched = matched_signatures.get(token, set())
        current_sigs = {f.issue_signature for f in findings if f.check == token}
        for prior in baseline_findings(token):
            sig = prior["issue_signature"]
            if sig in matched or sig in current_sigs:
                continue
            resolved.append(prior)

    # Not re-evaluated: newest prior findings for checks that did not run this
    # time. Resolve per token so consecutive skip cycles do not lose the last
    # report that actually evaluated the check.
    not_reevaluated: list[dict[str, Any]] = []
    skipped_tokens = {
        canonical_token(prior.get("check"))
        for report in prior_reports
        for prior in report.findings
        if canonical_token(prior.get("check")) not in executed
    }
    for token in sorted(skipped_tokens):
        for report in prior_reports:  # already newest-first
            if token in report.executed_checks:
                not_reevaluated.extend(
                    prior
                    for prior in report.findings
                    if canonical_token(prior.get("check")) == token
                )
                break

    return {"resolved": resolved, "not_reevaluated": not_reevaluated}


def apply_suppressions_and_escalation(
    findings: list[Finding], cfg: dict[str, Any], run_timestamp: str
) -> None:
    suppressions: dict[str, list[dict[str, str]]] = cfg.get("suppressions", {})
    threshold = int(cfg.get("repeat_escalation_days", 30))
    run_date = _parse_ts(run_timestamp)
    for finding in findings:
        entries = suppressions.get(finding.check, [])
        for entry in entries:
            if entry["match"] in finding.issue_signature:
                finding.suppressed = True
                break
        finding.escalated = False
        if finding.delta_status in ("repeat", "post-fix-drift"):
            first = _parse_ts(finding.first_seen)
            if first and run_date:
                age = (run_date.date() - first.date()).days
                if age >= threshold:
                    finding.escalated = True


# --------------------------------------------------------------------------- #
# Timestamps
# --------------------------------------------------------------------------- #


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _today(cfg: dict[str, Any]) -> Any:
    override = cfg.get("_today")
    if override:
        return datetime.strptime(override, "%Y-%m-%d").date()
    return _now_utc().date()


def _parse_ts(value: str) -> Optional[datetime]:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        try:
            return datetime.strptime(value[:10], "%Y-%m-%d")
        except ValueError:
            return None


def _format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


def _compact_ts(value: str) -> str:
    dt = _parse_ts(value)
    if dt is None:
        return re.sub(r"[^0-9A-Za-z]", "", value)
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%S%f") + "Z"


# --------------------------------------------------------------------------- #
# Mode expansion + run
# --------------------------------------------------------------------------- #


def expand_mode(
    mode: str, explicit_checks: list[str], cfg: dict[str, Any]
) -> tuple[list[str], bool]:
    """Return requested whole-check ids and whether Check 24 is allowed."""
    checks_cfg = cfg["checks"]
    core = [str(c) for c in (checks_cfg.get("core") or [])]
    extended = [str(c) for c in (checks_cfg.get("extended") or [])]
    # CodeGraph group is taken as configured. Any TARGETED_ONLY token (Check 24)
    # left in the routine set is surfaced as skipped-with-note by run_audit
    # rather than silently dropped, so the exclusion is visible to the operator.
    codegraph = [str(c) for c in (checks_cfg.get("codegraph") or [])]
    if mode == "core":
        return core, False
    if mode == "extended":
        return core + extended, False
    if mode == "full":
        return core + extended + codegraph, False
    if mode == "codegraph":
        return codegraph, False
    if mode == "check":
        # Targeted invocation: Check 24 reachable only here.
        return [canonical_token(c) for c in explicit_checks], True
    if mode == "status":
        return [], False
    raise ValueError(f"unknown mode: {mode}")


@dataclass
class AuditResult:
    mode: str
    run_timestamp: str
    executed_checks: list[str]
    skipped_checks: list[str]
    skip_notes: dict[str, str]
    findings: list[Finding]
    resolved: list[dict[str, Any]]
    not_reevaluated: list[dict[str, Any]]
    baseline_warnings: list[str]
    report_path: Optional[Path]


def run_audit(
    root: Path,
    cfg: dict[str, Any],
    mode: str,
    explicit_checks: Optional[list[str]] = None,
    *,
    reports_dir: Optional[Path] = None,
    run_timestamp: Optional[str] = None,
    codegraph_bundle: Optional[dict[str, Any]] = None,
    allow_targeted: Optional[bool] = None,
    write: bool = True,
) -> AuditResult:
    explicit_checks = explicit_checks or []
    run_timestamp = run_timestamp or _format_ts(_now_utc())
    reports_dir = reports_dir or (root / cfg["paths"].get("reports", "pm/reports/"))

    requested_whole, targeted = expand_mode(mode, explicit_checks, cfg)
    if allow_targeted is not None:
        targeted = allow_targeted

    skip_set = {canonical_token(c) for c in (cfg["checks"].get("skip") or [])}
    findings: list[Finding] = []
    executed: list[str] = []
    skipped: list[str] = []
    skip_notes: dict[str, str] = {}

    # Resolve which CodeGraph tokens were requested (routine vs targeted).
    requested_codegraph: set[str] = set()
    provided_codegraph: set[str] = set()
    bundle_obj = codegraph_bundle or {}

    for whole in requested_whole:
        whole_token = canonical_token(whole)
        if whole_token in TARGETED_ONLY and not targeted:
            skipped.append(whole_token)
            skip_notes[whole_token] = (
                "targeted-only (requires explicit plan-claim context)"
            )
            continue
        sub_tokens = SUBCHECK_MAP.get(whole_token, [whole_token])
        for token in sub_tokens:
            if token in skip_set or _whole_number(token) in skip_set:
                skipped.append(token)
                skip_notes[token] = "config skip"
                continue
            if token in CODEGRAPH_KINDS:
                requested_codegraph.add(token)
                continue
            impl = CHECK_REGISTRY.get(token)
            if impl is None:
                skipped.append(token)
                skip_notes[token] = (
                    "not mechanized in runner (operator-owned via skill)"
                )
                continue
            impl(root, cfg, findings)
            executed.append(token)

    # CodeGraph: normalize the bundle, mark requested-but-missing tokens skipped.
    if requested_codegraph:
        provided_codegraph = normalize_codegraph_bundle(
            bundle_obj, findings, requested_codegraph, cfg
        )
        for token in sorted(requested_codegraph):
            if token in provided_codegraph:
                executed.append(token)
            else:
                skipped.append(token)
                skip_notes[token] = "CodeGraph bundle missing for requested check"

    # Apply severity overrides.
    overrides = cfg["checks"].get("severity_override") or {}
    norm_overrides = {canonical_token(k): str(v).lower() for k, v in overrides.items()}
    for finding in findings:
        override = norm_overrides.get(finding.check) or norm_overrides.get(
            _whole_number(finding.check)
        )
        if override:
            finding.severity = override

    executed_set = set(executed)

    # Cross-run delta. status mode neither classifies nor writes.
    report_path: Optional[Path] = None
    resolved: list[dict[str, Any]] = []
    not_reevaluated: list[dict[str, Any]] = []
    warnings: list[str] = []
    if mode != "status":
        target_path = _report_path(reports_dir, run_timestamp)
        prior_reports, warnings = load_prior_reports(reports_dir, exclude=target_path)
        deltas = classify_deltas(findings, prior_reports, executed_set, run_timestamp)
        resolved = deltas["resolved"]
        not_reevaluated = deltas["not_reevaluated"]
        apply_suppressions_and_escalation(findings, cfg, run_timestamp)
        if write:
            report_path = _write_report(
                target_path,
                AuditResult(
                    mode=mode,
                    run_timestamp=run_timestamp,
                    executed_checks=sorted(executed_set),
                    skipped_checks=sorted(set(skipped)),
                    skip_notes=skip_notes,
                    findings=findings,
                    resolved=resolved,
                    not_reevaluated=not_reevaluated,
                    baseline_warnings=warnings,
                    report_path=None,
                ),
            )

    return AuditResult(
        mode=mode,
        run_timestamp=run_timestamp,
        executed_checks=sorted(executed_set),
        skipped_checks=sorted(set(skipped)),
        skip_notes=skip_notes,
        findings=findings,
        resolved=resolved,
        not_reevaluated=not_reevaluated,
        baseline_warnings=warnings,
        report_path=report_path,
    )


def _report_path(reports_dir: Path, run_timestamp: str) -> Path:
    base = f"audit-{_compact_ts(run_timestamp)}"
    candidate = reports_dir / f"{base}.md"
    counter = 1
    while candidate.exists():
        candidate = reports_dir / f"{base}-{counter}.md"
        counter += 1
    return candidate


def _bucket(findings: list[Finding]) -> dict[str, list[Finding]]:
    buckets: dict[str, list[Finding]] = {
        "new": [],
        "repeat": [],
        "escalated": [],
        "drift": [],
        "suppressed": [],
    }
    for finding in findings:
        if finding.escalated:
            buckets["escalated"].append(finding)
        elif finding.suppressed:
            buckets["suppressed"].append(finding)
        elif finding.delta_status == "new":
            buckets["new"].append(finding)
        elif finding.delta_status == "post-fix-drift":
            buckets["drift"].append(finding)
        else:
            buckets["repeat"].append(finding)
    return buckets


def format_report_markdown(result: AuditResult) -> str:
    buckets = _bucket(result.findings)
    lines: list[str] = []
    lines.append(f"# PM Audit Report — {result.run_timestamp}")
    lines.append("")
    lines.append(f"Mode: `{result.mode}`")
    lines.append(f"Executed checks: {', '.join(result.executed_checks) or 'none'}")
    lines.append(f"Skipped checks: {', '.join(result.skipped_checks) or 'none'}")
    lines.append("")
    if result.baseline_warnings:
        lines.append("## Baseline warnings")
        for warning in result.baseline_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    def render(title: str, items: list[Finding]) -> None:
        lines.append(f"## {title}")
        if not items:
            lines.append("None.")
        for finding in items:
            note = ""
            if finding.severity_change:
                note = f" (severity {finding.severity_change})"
            lines.append(
                f"- **{finding.severity.upper()}** — Check {finding.check} — "
                f"`{finding.file}:{finding.line}` — {finding.summary or finding.issue}"
                f"{note}  \n  signature `{finding.issue_signature}`, "
                f"first_seen {finding.first_seen}, repeat_count {finding.repeat_count}"
            )
        lines.append("")

    render("New since last audit", buckets["new"])
    render("Repeats unactioned", buckets["repeat"])
    render("Escalated repeats", buckets["escalated"])
    render("Post-fix drift", buckets["drift"])

    lines.append("## Suppressed (hidden, still tracked)")
    if not buckets["suppressed"]:
        lines.append("None.")
    for finding in buckets["suppressed"]:
        lines.append(f"- Check {finding.check} — `{finding.issue_signature}`")
    lines.append("")

    lines.append("## Newly resolved")
    if not result.resolved:
        lines.append("None.")
    for prior in result.resolved:
        lines.append(f"- Check {prior.get('check')} — `{prior.get('issue_signature')}`")
    lines.append("")

    lines.append("## Not re-evaluated this run")
    if not result.not_reevaluated:
        lines.append("None.")
    for prior in result.not_reevaluated:
        lines.append(f"- Check {prior.get('check')} — `{prior.get('issue_signature')}`")
    lines.append("")

    if result.skip_notes:
        lines.append("## Skip notes")
        for token in sorted(result.skip_notes):
            lines.append(f"- {token}: {result.skip_notes[token]}")
        lines.append("")

    payload = {
        "metadata": {
            "run_timestamp": result.run_timestamp,
            "mode": result.mode,
            "executed_checks": result.executed_checks,
            "skipped_checks": result.skipped_checks,
        },
        "findings": [f.to_payload() for f in result.findings],
    }
    lines.append(STRUCT_START)
    lines.append("```json")
    lines.append(json.dumps(payload, indent=2, sort_keys=True))
    lines.append("```")
    lines.append(STRUCT_END)
    lines.append("")
    return "\n".join(lines)


def _write_report(path: Path, result: AuditResult) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    result.report_path = path
    path.write_text(format_report_markdown(result), encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

_MODE_WORDS = {"core", "status", "extended", "full", "codegraph"}


def _parse_mode_tokens(tokens: list[str]) -> tuple[str, list[str]]:
    """Parse natural-language mode tokens (no dashes), e.g. ``check 1 check 6``."""
    if not tokens:
        return "core", []
    lowered = [t.lower() for t in tokens]
    if "check" in lowered:
        checks: list[str] = []
        for token in tokens:
            if token.lower() == "check":
                continue
            checks.append(canonical_token(token))
        return "check", checks
    for word in lowered:
        if word in _MODE_WORDS:
            return word, []
    raise SystemExit(f"pm_audit.py: unrecognized mode tokens: {tokens}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Stateful /pm-audit runner.")
    parser.add_argument(
        "mode", nargs="*", help="core|status|extended|full|codegraph|check N"
    )
    parser.add_argument("--root", default=None, help="project root (default: cwd)")
    parser.add_argument("--config", default=None, help="audit-config.yaml path")
    parser.add_argument("--reports-dir", default=None, help="override reports dir")
    parser.add_argument(
        "--codegraph-bundle", default=None, help="CodeGraph JSON bundle"
    )
    parser.add_argument("--now", default=None, help="inject run timestamp (ISO 8601)")
    parser.add_argument(
        "--today", default=None, help="inject today's date (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--no-write", action="store_true", help="do not persist a report"
    )
    parser.add_argument(
        "--json", action="store_true", help="emit JSON instead of markdown"
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path.cwd()
    config_path = (
        Path(args.config) if args.config else (root / "pm" / "audit-config.yaml")
    )
    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        print(f"pm_audit.py: config error: {exc}", file=sys.stderr)
        return 2
    if args.today:
        cfg["_today"] = args.today
    mode, explicit = _parse_mode_tokens(args.mode)

    bundle = None
    if args.codegraph_bundle:
        bundle = json.loads(Path(args.codegraph_bundle).read_text(encoding="utf-8"))

    reports_dir = Path(args.reports_dir) if args.reports_dir else None
    result = run_audit(
        root,
        cfg,
        mode,
        explicit,
        reports_dir=reports_dir,
        run_timestamp=args.now,
        codegraph_bundle=bundle,
        write=not args.no_write,
    )

    if args.json:
        payload = {
            "metadata": {
                "run_timestamp": result.run_timestamp,
                "mode": result.mode,
                "executed_checks": result.executed_checks,
                "skipped_checks": result.skipped_checks,
                "report_path": str(result.report_path) if result.report_path else None,
                "baseline_warnings": result.baseline_warnings,
            },
            "findings": [f.to_payload() for f in result.findings],
            "resolved": result.resolved,
            "not_reevaluated": result.not_reevaluated,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(format_report_markdown(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
