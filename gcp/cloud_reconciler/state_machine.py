"""Thin wrapper for shared reconciler state machine implementation.

Executes canonical source from:
  gcp-spot-runner/cloud_reconciler/state_machine.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _runner_candidates() -> list[Path]:
    explicit = os.environ.get("RUNNER_DIR") or os.environ.get("GCP_SPOT_RUNNER_DIR")
    if explicit:
        return [Path(explicit).expanduser()]
    here = Path(__file__).resolve()
    return [
        here.parents[3] / "gcp-spot-runner",
        here.parents[2] / "gcp-spot-runner",
    ]


def _resolve_shared_state_machine() -> Path:
    errors: list[str] = []
    for runner_dir in _runner_candidates():
        target = runner_dir / "cloud_reconciler" / "state_machine.py"
        if target.is_file():
            return target
        errors.append(f"missing {target}")

    msg = "\n".join(errors)
    raise RuntimeError(
        "Unable to locate shared state machine module. "
        "Set RUNNER_DIR or GCP_SPOT_RUNNER_DIR to your gcp-spot-runner checkout.\n"
        f"Details:\n{msg}"
    )


_SHARED_STATE = _resolve_shared_state_machine()
sys.path.insert(0, str(_SHARED_STATE.parent))

with open(_SHARED_STATE, "r", encoding="utf-8") as _f:
    _code = compile(_f.read(), str(_SHARED_STATE), "exec")
    exec(_code, globals(), globals())
