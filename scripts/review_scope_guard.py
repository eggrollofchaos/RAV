from __future__ import annotations

GENERATED_ARTIFACT_PREFIXES = (
    "company-research-runs/",
    "employment-edge-runs/",
    "application-prep-runs/",
    "interview-prep-runs/",
    "personal-analysis-snapshots/",
    "repo-analysis-snapshots/",
    "deep-research-runs/",
    "review/local-reports/",
    "review/local-prompts/",
    "review/local-benchmarks/runs/",
)


def blocked_generated_artifact_paths(
    changed_paths: list[str],
    *,
    blocked_prefixes: tuple[str, ...] = GENERATED_ARTIFACT_PREFIXES,
    allowed_prefixes: list[str] | tuple[str, ...] = (),
) -> list[str]:
    allowed = tuple(prefix.rstrip("/") + "/" for prefix in allowed_prefixes)
    blocked: list[str] = []
    for path in changed_paths:
        if any(path.startswith(prefix) for prefix in blocked_prefixes):
            if any(path.startswith(prefix) for prefix in allowed):
                continue
            blocked.append(path)
    return blocked
