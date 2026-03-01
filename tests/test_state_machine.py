"""Tests for gcp/cloud_reconciler/state_machine.py
Covers verification matrix items: #5, #6, #30, #31, #38
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add reconciler to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gcp" / "cloud_reconciler"))

from state_machine import (
    TERMINAL_STATES,
    VALID_ACTORS,
    STATUS_COMPAT_MAP,
    can_transition,
    is_terminal,
    status_compat,
    transitions_hash,
    _load_transitions,
)


TRANSITIONS_FILE = ROOT / "gcp" / "state_transitions.json"
STATE_HELPERS_SH = ROOT / "gcp" / "state_helpers.sh"


# ── Terminal states ──


class TestTerminalStates:
    @pytest.mark.parametrize("state", ["COMPLETE", "FAILED", "PARTIAL", "STOPPED"])
    def test_terminal_states(self, state):
        assert is_terminal(state)

    @pytest.mark.parametrize("state", ["RUNNING", "PREEMPTED", "ORPHANED", "RESTARTING"])
    def test_non_terminal_states(self, state):
        assert not is_terminal(state)


# ── Status compatibility mapping ──


class TestStatusCompat:
    @pytest.mark.parametrize(
        "state,expected",
        [
            ("RUNNING", "RUNNING"),
            ("COMPLETE", "COMPLETE"),
            ("FAILED", "FAILED"),
            ("PARTIAL", "PARTIAL"),
            ("PREEMPTED", "PREEMPTED"),
            ("ORPHANED", "PREEMPTED"),
            ("RESTARTING", "RUNNING"),
            ("STOPPED", "STOPPED"),
        ],
    )
    def test_compat_mapping(self, state, expected):
        assert status_compat(state) == expected


# ── Transition validation ──


class TestCanTransition:
    def test_null_to_running(self):
        assert can_transition(None, "RUNNING", "vm")

    def test_null_to_orphaned_reconciler(self):
        assert can_transition(None, "ORPHANED", "reconciler")

    def test_running_to_complete(self):
        assert can_transition("RUNNING", "COMPLETE", "vm")

    def test_running_to_failed(self):
        assert can_transition("RUNNING", "FAILED", "vm")

    def test_running_to_partial(self):
        assert can_transition("RUNNING", "PARTIAL", "vm")

    def test_running_to_preempted(self):
        assert can_transition("RUNNING", "PREEMPTED", "vm")

    def test_running_to_orphaned(self):
        assert can_transition("RUNNING", "ORPHANED", "reconciler")

    def test_running_to_stopped(self):
        assert can_transition("RUNNING", "STOPPED", "operator")

    def test_preempted_to_restarting(self):
        assert can_transition("PREEMPTED", "RESTARTING", "local")

    def test_preempted_to_stopped(self):
        assert can_transition("PREEMPTED", "STOPPED", "operator")

    def test_orphaned_to_restarting(self):
        assert can_transition("ORPHANED", "RESTARTING", "reconciler")

    def test_orphaned_to_stopped(self):
        assert can_transition("ORPHANED", "STOPPED", "operator")

    def test_restarting_to_running(self):
        assert can_transition("RESTARTING", "RUNNING", "vm")

    def test_restarting_to_orphaned(self):
        assert can_transition("RESTARTING", "ORPHANED", "reconciler")

    def test_restarting_to_stopped(self):
        assert can_transition("RESTARTING", "STOPPED", "operator")


# ── Disallowed transitions ──


class TestDisallowedTransitions:
    @pytest.mark.parametrize("terminal", ["COMPLETE", "FAILED", "PARTIAL", "STOPPED"])
    def test_terminal_to_anything_rejected(self, terminal):
        """#5: Terminal precedence"""
        with pytest.raises(ValueError, match="not allowed"):
            can_transition(terminal, "RUNNING", "vm")

    def test_running_to_restarting_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            can_transition("RUNNING", "RESTARTING", "local")

    def test_preempted_to_running_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            can_transition("PREEMPTED", "RUNNING", "vm")

    def test_null_to_complete_rejected(self):
        with pytest.raises(ValueError, match="not allowed"):
            can_transition(None, "COMPLETE", "vm")


# ── Actor guards ──


class TestActorGuards:
    def test_null_to_orphaned_vm_rejected(self):
        """#31: VM attempts null→ORPHANED"""
        with pytest.raises(ValueError, match="guarded"):
            can_transition(None, "ORPHANED", "vm")

    def test_null_to_orphaned_local_rejected(self):
        with pytest.raises(ValueError, match="guarded"):
            can_transition(None, "ORPHANED", "local")

    def test_null_to_orphaned_operator_rejected(self):
        with pytest.raises(ValueError, match="guarded"):
            can_transition(None, "ORPHANED", "operator")

    def test_unknown_actor_rejected(self):
        with pytest.raises(ValueError, match="Unknown actor"):
            can_transition("RUNNING", "COMPLETE", "unknown")

    def test_empty_actor_rejected(self):
        with pytest.raises(ValueError, match="Unknown actor"):
            can_transition("RUNNING", "COMPLETE", "")


# ── Hash verification ──


class TestTransitionsHash:
    def test_hash_is_64_hex(self):
        """#38: Hash format"""
        h = transitions_hash()
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_matches_file(self):
        """#38: Hash matches file"""
        import hashlib

        expected = hashlib.sha256(TRANSITIONS_FILE.read_bytes()).hexdigest()
        assert transitions_hash() == expected


# ── Python ↔ Bash parity ──


class TestParity:
    """#30: can_transition parity — Python vs bash implementations agree on all (from, to, actor) triples"""

    ALL_STATES = [None, "RUNNING", "COMPLETE", "FAILED", "PARTIAL", "PREEMPTED", "ORPHANED", "RESTARTING", "STOPPED"]
    ALL_ACTORS = list(VALID_ACTORS)

    def _bash_can_transition(self, from_state, to_state, actor):
        """Call bash can_transition and return True/False."""
        from_arg = from_state if from_state else "null"
        cmd = f"""
            source "{STATE_HELPERS_SH}" 2>/dev/null
            can_transition "{from_arg}" "{to_state}" "{actor}" 2>/dev/null
        """
        result = subprocess.run(
            ["bash", "-c", cmd],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0

    def _python_can_transition(self, from_state, to_state, actor):
        """Call Python can_transition and return True/False."""
        try:
            return can_transition(from_state, to_state, actor)
        except ValueError:
            return False

    def test_all_transitions_agree(self):
        """Exhaustive parity check: every (from, to, actor) triple gives same result."""
        mismatches = []
        for from_state in self.ALL_STATES:
            for to_state in ["RUNNING", "COMPLETE", "FAILED", "PARTIAL", "PREEMPTED", "ORPHANED", "RESTARTING", "STOPPED"]:
                for actor in self.ALL_ACTORS:
                    py_result = self._python_can_transition(from_state, to_state, actor)
                    bash_result = self._bash_can_transition(from_state, to_state, actor)
                    if py_result != bash_result:
                        from_label = from_state or "null"
                        mismatches.append(
                            f"  {from_label} → {to_state} (actor={actor}): py={py_result}, bash={bash_result}"
                        )

        if mismatches:
            pytest.fail(f"Python/bash parity mismatches:\n" + "\n".join(mismatches))

    def test_actor_guarded_edges_agree(self):
        """#30: Actor-guarded edges (null→ORPHANED) agree specifically."""
        # reconciler: allowed
        assert self._python_can_transition(None, "ORPHANED", "reconciler") is True
        assert self._bash_can_transition(None, "ORPHANED", "reconciler") is True
        # vm: rejected
        assert self._python_can_transition(None, "ORPHANED", "vm") is False
        assert self._bash_can_transition(None, "ORPHANED", "vm") is False
        # local: rejected
        assert self._python_can_transition(None, "ORPHANED", "local") is False
        assert self._bash_can_transition(None, "ORPHANED", "local") is False
