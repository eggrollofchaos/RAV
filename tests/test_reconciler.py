"""Tests for gcp/cloud_reconciler/main.py
Covers verification matrix items: #7-12, #17, #20, #26, #32-33
Uses unittest.mock to avoid requiring real GCP services.
"""

import datetime
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "gcp" / "cloud_reconciler"))


# ── Fixtures ──


def _make_state(state, updated_at=None, attempt=0, instance_name="test-vm", zone="us-east1-c"):
    updated_at = updated_at or datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "state": state,
        "prev_state": None,
        "state_version": 1,
        "owner_id": instance_name,
        "instance_name": instance_name,
        "zone": zone,
        "attempt": attempt,
        "updated_at": updated_at,
        "updated_by": "vm",
        "reason": "test",
        "history": [],
    }


def _make_heartbeat(stale_sec=0):
    """Create heartbeat data. stale_sec=0 means fresh."""
    ts = datetime.datetime.utcnow() - datetime.timedelta(seconds=stale_sec)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "phase": "running",
        "uptime_sec": 3600,
        "exit_code": 0,
    }


def _make_stale_marker(age_sec=180, hb_ts=None):
    """Create .reconciler_stale_seen marker data."""
    ts = datetime.datetime.utcnow() - datetime.timedelta(seconds=age_sec)
    return {
        "timestamp": ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "heartbeat_epoch_at_observation": hb_ts or "2026-02-28T10:00:00Z",
    }


class MockBlob:
    """Mock GCS blob with generation tracking."""

    def __init__(self, data=None, generation=1):
        self._data = data
        self.generation = generation
        self._exists = data is not None
        self._uploaded = []
        self._deleted = False

    def download_as_text(self):
        if self._data is None:
            raise Exception("Not found")
        return self._data if isinstance(self._data, str) else json.dumps(self._data)

    def upload_from_string(self, data, content_type=None, if_generation_match=None):
        if if_generation_match == 0 and self._exists:
            raise _PreconditionFailed("exists")
        if if_generation_match is not None and if_generation_match != 0 and if_generation_match != self.generation:
            raise _PreconditionFailed("generation mismatch")
        self._data = data
        self._exists = True
        self.generation += 1
        self._uploaded.append(data)

    def exists(self):
        return self._exists

    def delete(self, if_generation_match=None):
        if if_generation_match is not None and if_generation_match != self.generation:
            raise _PreconditionFailed("generation mismatch")
        self._data = None
        self._exists = False
        self._deleted = True


class MockBucket:
    """Mock GCS bucket with blob routing."""

    def __init__(self, blobs=None):
        self._blobs = blobs or {}

    def blob(self, path):
        if path not in self._blobs:
            self._blobs[path] = MockBlob()
        return self._blobs[path]

    def list_blobs(self, prefix="", delimiter=""):
        return MagicMock(pages=[MagicMock(prefixes=[])])


# ── Import reconciler after path setup ──

# Create real exception classes for mocking
_PreconditionFailed = type("PreconditionFailed", (Exception,), {})
_NotFound = type("NotFound", (Exception,), {})

# Create a mock module for google.api_core.exceptions
_mock_gae = MagicMock()
_mock_gae.PreconditionFailed = _PreconditionFailed
_mock_gae.NotFound = _NotFound

# Mock all GCP dependencies before importing main
sys.modules["functions_framework"] = MagicMock()
sys.modules["requests"] = MagicMock()
sys.modules["google"] = MagicMock()
sys.modules["google.cloud"] = MagicMock()
sys.modules["google.cloud.storage"] = MagicMock()
sys.modules["google.cloud.compute_v1"] = MagicMock()
sys.modules["google.api_core"] = MagicMock()
sys.modules["google.api_core.exceptions"] = _mock_gae

import main as reconciler

# Ensure reconciler uses our exception types
reconciler.PreconditionFailed = _PreconditionFailed
reconciler.NotFound = _NotFound

# Override the global DRY_RUN for tests
reconciler.DRY_RUN = False
reconciler.HEARTBEAT_STALE_SEC = 600
reconciler.RESTARTING_STUCK_SEC = 600
reconciler.STALE_MARKER_MIN_AGE_SEC = 120


# ── Tests ──


class TestReconcileRun:
    """Tests for _reconcile_run()."""

    def test_skip_terminal_complete(self):
        """Skip COMPLETE runs."""
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("COMPLETE")),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None

    def test_skip_terminal_failed(self):
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("FAILED")),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None

    def test_skip_terminal_stopped(self):
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("STOPPED")),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None


class TestTwoStageStalDetection:
    """#8, #9: Two-stage stale detection."""

    def test_first_stale_observation_writes_marker(self):
        """#8 (stage 1): First stale observation creates marker."""
        hb = _make_heartbeat(stale_sec=700)
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("RUNNING")),
            "runs/test-run/heartbeat.json": MockBlob(hb),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result == "stale_first_observation"
        # Marker should be written
        marker_blob = bucket.blob("runs/test-run/.reconciler_stale_seen")
        assert marker_blob._exists

    def test_second_observation_requires_min_age(self):
        """Marker too recent — skip."""
        hb = _make_heartbeat(stale_sec=700)
        marker = _make_stale_marker(age_sec=60, hb_ts=hb["timestamp"])  # Only 60s old
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("RUNNING")),
            "runs/test-run/heartbeat.json": MockBlob(hb),
            "runs/test-run/.reconciler_stale_seen": MockBlob(marker),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None

    def test_heartbeat_recovery_clears_marker(self):
        """#9: Fresh heartbeat clears stale marker."""
        hb = _make_heartbeat(stale_sec=0)  # Fresh
        marker = _make_stale_marker(age_sec=300)
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("RUNNING")),
            "runs/test-run/heartbeat.json": MockBlob(hb),
            "runs/test-run/.reconciler_stale_seen": MockBlob(marker),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None
        # Marker should be deleted
        assert bucket.blob("runs/test-run/.reconciler_stale_seen")._deleted

    def test_stale_vm_alive_warning_only(self):
        """#10: Stale heartbeat but VM still exists → warning only."""
        hb_ts = (datetime.datetime.utcnow() - datetime.timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hb = {"timestamp": hb_ts, "phase": "running", "uptime_sec": 3600, "exit_code": 0}
        marker = _make_stale_marker(age_sec=180, hb_ts=hb_ts)
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(_make_state("RUNNING")),
            "runs/test-run/heartbeat.json": MockBlob(hb),
            "runs/test-run/.reconciler_stale_seen": MockBlob(marker),
        })

        with patch.object(reconciler, "_vm_exists", return_value=True):
            result = reconciler._reconcile_run(bucket, "test-run")

        assert result == "stale_vm_alive"


class TestStatusDriftRepair:
    """#17: Status drift detection and repair."""

    def test_no_drift_no_action(self):
        """No drift when status matches."""
        state = _make_state("COMPLETE")
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
            "runs/test-run/status.txt": MockBlob("COMPLETE"),
        })
        reconciler._repair_status_drift(bucket, "test-run", state)
        # status.txt should not have been re-uploaded
        blob = bucket.blob("runs/test-run/status.txt")
        assert len(blob._uploaded) == 0

    def test_drift_repaired(self):
        """Drift: state=COMPLETE, status=RUNNING → repair to COMPLETE."""
        state = _make_state("COMPLETE")
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
            "runs/test-run/status.txt": MockBlob("RUNNING"),
        })
        reconciler._repair_status_drift(bucket, "test-run", state)
        blob = bucket.blob("runs/test-run/status.txt")
        assert blob._uploaded[-1] == "COMPLETE"

    def test_no_repair_during_restarting(self):
        """Don't repair during RESTARTING."""
        state = _make_state("RESTARTING")
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
            "runs/test-run/status.txt": MockBlob("RUNNING"),
        })
        reconciler._repair_status_drift(bucket, "test-run", state)
        blob = bucket.blob("runs/test-run/status.txt")
        assert len(blob._uploaded) == 0

    def test_repair_disabled_marker(self):
        """Skip repair when .drift_repair_disabled exists."""
        state = _make_state("COMPLETE")
        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
            "runs/test-run/status.txt": MockBlob("RUNNING"),
            "runs/test-run/.drift_repair_disabled": MockBlob("true"),
        })
        reconciler._repair_status_drift(bucket, "test-run", state)
        blob = bucket.blob("runs/test-run/status.txt")
        assert len(blob._uploaded) == 0


class TestRestartingStuckRecovery:
    """#26: RESTARTING stuck recovery."""

    def test_stuck_restarting_transitions_to_orphaned(self):
        """RESTARTING for >10 min + no VM + no heartbeat → ORPHANED."""
        old_ts = (datetime.datetime.utcnow() - datetime.timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = _make_state("RESTARTING", updated_at=old_ts)

        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
        })

        with patch.object(reconciler, "_vm_exists", return_value=False), \
             patch.object(reconciler, "_write_state_cas", return_value=True) as mock_write:
            result = reconciler._reconcile_run(bucket, "test-run")

        assert result == "restarting_stuck_recovered"
        mock_write.assert_called_once_with(bucket, "test-run", "ORPHANED", "restarting_stuck_recovery")

    def test_restarting_vm_alive_no_recovery(self):
        """RESTARTING but VM exists → no recovery."""
        old_ts = (datetime.datetime.utcnow() - datetime.timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = _make_state("RESTARTING", updated_at=old_ts)

        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
        })

        with patch.object(reconciler, "_vm_exists", return_value=True):
            result = reconciler._reconcile_run(bucket, "test-run")

        # Should not recover since VM is alive
        assert result is None

    def test_restarting_recent_no_recovery(self):
        """RESTARTING for <10 min → no recovery."""
        recent_ts = (datetime.datetime.utcnow() - datetime.timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%SZ")
        state = _make_state("RESTARTING", updated_at=recent_ts)

        bucket = MockBucket({
            "runs/test-run/state.json": MockBlob(state),
        })
        result = reconciler._reconcile_run(bucket, "test-run")
        assert result is None


class TestDryRun:
    """#7: Dry-run mode."""

    def test_dry_run_no_state_writes(self):
        """#7: DRY_RUN prevents state writes."""
        old_dry_run = reconciler.DRY_RUN
        reconciler.DRY_RUN = True
        try:
            result = reconciler._write_state_cas(MagicMock(), "test-run", "ORPHANED", "test")
            assert result is True  # Returns True in dry-run (logged action)
        finally:
            reconciler.DRY_RUN = old_dry_run


class TestRestartEnabled:
    """#32: Reconciler without restart flag."""

    def test_restart_not_enabled(self):
        """#32: No .reconciler_restart_enabled → no restart."""
        bucket = MockBucket()  # No restart flag
        assert reconciler._is_restart_enabled(bucket) is False

    def test_restart_enabled(self):
        """#33: With restart flag."""
        flag = {"enabled_at": "2026-02-28T12:00:00Z", "enabled_by": "operator"}
        bucket = MockBucket({
            ".reconciler_restart_enabled": MockBlob(flag),
        })
        assert reconciler._is_restart_enabled(bucket) is True


class TestRestartLockCAS:
    """#12, #13: Restart lock acquisition and reclaim."""

    def test_lock_acquire_fresh(self):
        """Acquire lock when no lock exists."""
        bucket = MockBucket()  # No restart.lock
        result = reconciler._acquire_restart_lock_cas(bucket, "test-run", 1)
        assert result is not None
        blob, gen = result
        assert blob._exists

    def test_lock_acquire_conflict(self):
        """Cannot acquire lock when it exists (not stale)."""
        fresh_lock = {
            "actor": "local",
            "hostname": "other-host",
            "acquired_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "attempt": 1,
            "ttl_sec": 300,
        }
        bucket = MockBucket({
            "runs/test-run/restart.lock": MockBlob(fresh_lock),
        })
        result = reconciler._acquire_restart_lock_cas(bucket, "test-run", 1)
        assert result is None


class TestOwnerLockClearance:
    """#14: Owner lock preconditioned delete."""

    def test_clear_owner_lock_vm_gone(self):
        """Clear owner lock when VM is gone."""
        lock_data = {
            "instance": "old-vm",
            "zone": "us-east1-c",
        }
        bucket = MockBucket({
            "runs/test-run/.owner.lock": MockBlob(lock_data),
        })

        with patch.object(reconciler, "_vm_exists", return_value=False):
            result = reconciler._clear_owner_lock_preconditioned(bucket, "test-run")

        assert result is True
        assert bucket.blob("runs/test-run/.owner.lock")._deleted

    def test_clear_owner_lock_vm_alive_aborts(self):
        """Abort when owner VM still exists."""
        lock_data = {
            "instance": "alive-vm",
            "zone": "us-east1-c",
        }
        bucket = MockBucket({
            "runs/test-run/.owner.lock": MockBlob(lock_data),
        })

        with patch.object(reconciler, "_vm_exists", return_value=True):
            result = reconciler._clear_owner_lock_preconditioned(bucket, "test-run")

        assert result is False


class TestLegacyRun:
    """#20: Legacy run handling."""

    def test_legacy_no_state_no_restart(self):
        """#20: Legacy run (no state.json, no restart_config) with stale heartbeat → ORPHANED, no restart."""
        hb_ts = (datetime.datetime.utcnow() - datetime.timedelta(seconds=700)).strftime("%Y-%m-%dT%H:%M:%SZ")
        hb = {"timestamp": hb_ts, "phase": "running", "uptime_sec": 3600, "exit_code": 0}
        marker = _make_stale_marker(age_sec=180, hb_ts=hb_ts)

        bucket = MockBucket({
            "runs/test-run/heartbeat.json": MockBlob(hb),
            "runs/test-run/.reconciler_stale_seen": MockBlob(marker),
        })

        with patch.object(reconciler, "_vm_exists", return_value=False), \
             patch.object(reconciler, "_write_state_cas", return_value=True) as mock_write, \
             patch.object(reconciler, "_try_restart", return_value=None) as mock_restart:
            result = reconciler._reconcile_run(bucket, "test-run")

        assert result == "orphaned"
        # _write_state_cas should have been called to bootstrap ORPHANED
        mock_write.assert_called_once_with(bucket, "test-run", "ORPHANED", "legacy_bootstrap_orphaned")
        # _try_restart should have been called but returns None (no restart_config)
        mock_restart.assert_called_once()


class TestTryRestart:
    """#32, #33: Restart flow."""

    def test_restart_disabled_no_action(self):
        """#32: Restart not enabled → no restart action."""
        state = _make_state("ORPHANED")
        config = {"auto_restart_max": 3}
        bucket = MockBucket()

        with patch.object(reconciler, "_is_restart_enabled", return_value=False):
            result = reconciler._try_restart(bucket, "test-run", state, config)

        assert result is None

    def test_restart_no_config_no_action(self):
        """No restart_config → no restart."""
        state = _make_state("ORPHANED")
        bucket = MockBucket()

        with patch.object(reconciler, "_is_restart_enabled", return_value=True):
            result = reconciler._try_restart(bucket, "test-run", state, None)

        assert result is None

    def test_restart_attempts_exhausted(self):
        """Attempt >= max → no restart."""
        state = _make_state("ORPHANED", attempt=3)
        config = {"auto_restart_max": 3}
        bucket = MockBucket()

        with patch.object(reconciler, "_is_restart_enabled", return_value=True):
            result = reconciler._try_restart(bucket, "test-run", state, config)

        assert result is None

    def test_restart_stop_file_blocks(self):
        """#22: .stop file blocks restart."""
        state = _make_state("ORPHANED")
        config = {"auto_restart_max": 3}
        bucket = MockBucket({
            "runs/test-run/.stop": MockBlob("stopped"),
        })

        with patch.object(reconciler, "_is_restart_enabled", return_value=True):
            result = reconciler._try_restart(bucket, "test-run", state, config)

        assert result is None


class TestParseIso:
    """Timestamp parsing edge cases."""

    def test_standard_format(self):
        dt = reconciler._parse_iso("2026-02-28T12:00:00Z")
        assert dt.year == 2026

    def test_microsecond_format(self):
        dt = reconciler._parse_iso("2026-02-28T12:00:00.123456Z")
        assert dt.year == 2026

    def test_no_z_format(self):
        dt = reconciler._parse_iso("2026-02-28T12:00:00")
        assert dt.year == 2026

    def test_invalid_format(self):
        with pytest.raises(ValueError):
            reconciler._parse_iso("not-a-date")
