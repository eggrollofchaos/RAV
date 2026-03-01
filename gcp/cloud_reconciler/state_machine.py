"""State machine transition validation.

Loads state_transitions.json and provides can_transition() for Python callers.
Both this module and gcp/state_helpers.sh load the same canonical file.
"""

import hashlib
import json
from pathlib import Path

_TRANSITIONS_PATH = Path(__file__).resolve().parent.parent / "state_transitions.json"

VALID_ACTORS = frozenset({"vm", "reconciler", "local", "operator"})

TERMINAL_STATES = frozenset({"COMPLETE", "FAILED", "PARTIAL", "STOPPED"})

# Status.txt compatibility mapping
STATUS_COMPAT_MAP = {
    "RUNNING": "RUNNING",
    "COMPLETE": "COMPLETE",
    "FAILED": "FAILED",
    "PARTIAL": "PARTIAL",
    "PREEMPTED": "PREEMPTED",
    "ORPHANED": "PREEMPTED",      # Intentional: same semantics from poll loop's perspective
    "RESTARTING": "RUNNING",       # Poll loop treats as active run
    "STOPPED": "STOPPED",
}


def _load_transitions(path: Path | None = None) -> dict:
    """Load and return the transitions definition."""
    p = path or _TRANSITIONS_PATH
    with open(p) as f:
        return json.load(f)


def transitions_hash(path: Path | None = None) -> str:
    """SHA-256 hash of the transitions file for version logging."""
    p = path or _TRANSITIONS_PATH
    return hashlib.sha256(p.read_bytes()).hexdigest()


def can_transition(
    from_state: str | None,
    to_state: str,
    actor: str,
    transitions: dict | None = None,
) -> bool:
    """Validate a state transition.

    Args:
        from_state: Current state (None for initial).
        to_state: Target state.
        actor: Must be one of VALID_ACTORS.
        transitions: Pre-loaded transitions dict (optional, loads from file if None).

    Returns:
        True if transition is allowed.

    Raises:
        ValueError: If actor is unknown or transition is not allowed.
    """
    if actor not in VALID_ACTORS:
        raise ValueError(f"Unknown actor '{actor}' (valid: {VALID_ACTORS})")

    if transitions is None:
        transitions = _load_transitions()

    from_key = "null" if from_state is None else from_state
    edges = transitions.get("edges", {})
    allowed_targets = edges.get(from_key, [])

    if to_state not in allowed_targets:
        raise ValueError(f"Transition {from_key} → {to_state} not allowed")

    # Check actor guards
    guard_key = f"{from_key}:{to_state}"
    actor_guards = transitions.get("actor_guards", {})
    if guard_key in actor_guards:
        allowed_actors = actor_guards[guard_key]
        if actor not in allowed_actors:
            raise ValueError(
                f"Transition {from_key} → {to_state} guarded — "
                f"actor '{actor}' not in allowed list {allowed_actors}"
            )

    return True


def status_compat(state: str) -> str:
    """Map state.json state to status.txt value."""
    return STATUS_COMPAT_MAP.get(state, state)


def is_terminal(state: str) -> bool:
    """Check if a state is terminal (cannot be overwritten)."""
    return state in TERMINAL_STATES
