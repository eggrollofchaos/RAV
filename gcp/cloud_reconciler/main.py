"""Cloud Reconciler — detects orphaned/preempted runs and (optionally) restarts them.

Deployed as a Cloud Function (gen2) triggered by Cloud Scheduler.
Operates in two modes:
  - Detection (3a): notify-only, no state writes or VM creates
  - Restart (3b): full restart with restart.lock lease protocol

Two-stage stale detection prevents false positives:
  1. First observation: heartbeat stale > 600s → write .reconciler_stale_seen marker
  2. Second observation (>=2 min later): marker exists AND heartbeat still stale
     AND heartbeat_epoch unchanged AND VM confirmed gone → ORPHANED
"""

import datetime
import hashlib
import json
import logging
import os
import uuid

import functions_framework
import requests
from google.api_core.exceptions import NotFound, PreconditionFailed
from google.cloud import compute_v1, storage

from state_machine import (
    TERMINAL_STATES,
    can_transition,
    is_terminal,
    status_compat,
    transitions_hash,
)

logger = logging.getLogger("reconciler")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

BUCKET_NAME = os.environ.get("BUCKET", "ixqt-training-488109")
PROJECT = os.environ.get("PROJECT", "ixqt-488109")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"
HEARTBEAT_STALE_SEC = int(os.environ.get("HEARTBEAT_STALE_SEC", "600"))
RESTARTING_STUCK_SEC = int(os.environ.get("RESTARTING_STUCK_SEC", "600"))  # 10 min
STALE_MARKER_MIN_AGE_SEC = 120  # 2 min between first and second observation
MAX_DRIFT_REPAIR_CYCLES = 5

# Pinned VM name filter pattern for aggregatedList
VM_NAME_FILTER = 'name eq "ixqt-trainer-{run_id}-a.*"'

_storage_client = None
_compute_client = None


def _get_storage_client():
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _get_compute_client():
    global _compute_client
    if _compute_client is None:
        _compute_client = compute_v1.InstancesClient()
    return _compute_client


def _now_iso():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(s):
    """Parse ISO8601 timestamp to datetime."""
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {s}")


def _notify_discord(msg, dry_run=False):
    """Send Discord notification."""
    secret_url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not secret_url:
        return
    prefix = "[DRY-RUN] " if dry_run else ""
    payload = {"content": f"{prefix}{msg}"}
    try:
        requests.post(secret_url, json=payload, timeout=5)
    except Exception as e:
        logger.warning(f"Discord notify failed: {e}")


def _blob_text(bucket, path):
    """Read a GCS blob as text, return None if not found."""
    try:
        blob = bucket.blob(path)
        return blob.download_as_text()
    except Exception:
        return None


def _blob_json(bucket, path):
    """Read a GCS blob as JSON, return None if not found."""
    text = _blob_text(bucket, path)
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None
    return None


def _blob_exists(bucket, path):
    return bucket.blob(path).exists()


def _vm_exists(instance_name, zone, project=None):
    """Check if a VM exists via Compute Engine API."""
    project = project or PROJECT
    try:
        _get_compute_client().get(
            project=project, zone=zone, instance=instance_name
        )
        return True
    except NotFound:
        return False
    except Exception as e:
        logger.warning(f"VM existence check failed for {instance_name}: {e}")
        return True  # Fail-safe: assume exists if check fails


def _vm_search_by_pattern(run_id, project=None):
    """Search for VMs matching the naming pattern across all zones."""
    project = project or PROJECT
    filter_str = VM_NAME_FILTER.format(run_id=run_id)
    try:
        result = _get_compute_client().aggregated_list(
            project=project,
            filter=filter_str,
        )
        for zone_key, response in result:
            if response.instances:
                for inst in response.instances:
                    return {"name": inst.name, "zone": zone_key.split("/")[-1]}
        return None
    except Exception as e:
        logger.warning(f"VM pattern search failed: {e}")
        return None


def _write_state_cas(bucket, run_id, new_state, reason, actor="reconciler"):
    """CAS write to state.json. Returns True on success."""
    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would write state {new_state} for {run_id}")
        return True

    blob = bucket.blob(f"runs/{run_id}/state.json")

    for attempt in range(3):
        try:
            raw = blob.download_as_text()
            current = json.loads(raw)
            generation = blob.generation
        except Exception:
            current = {}
            generation = 0

        current_state = current.get("state")
        if is_terminal(current_state or ""):
            logger.info(f"State already terminal ({current_state}), skipping {new_state}")
            return False

        try:
            can_transition(current_state, new_state, actor)
        except ValueError as e:
            logger.error(f"Transition rejected: {e}")
            return False

        state_version = current.get("state_version", current.get("generation", 0)) + 1
        history = current.get("history", [])
        entry = {
            "from": current_state, "to": new_state,
            "at": _now_iso(), "by": actor, "reason": reason,
        }
        history.append(entry)
        if len(history) > 20:
            history = history[-20:]

        new_data = {
            "state": new_state,
            "prev_state": current_state,
            "state_version": state_version,
            "owner_id": current.get("owner_id", ""),
            "instance_name": current.get("instance_name", ""),
            "zone": current.get("zone", ""),
            "attempt": current.get("attempt", 0),
            "updated_at": _now_iso(),
            "updated_by": actor,
            "reason": reason,
            "history": history,
        }

        try:
            blob.upload_from_string(
                json.dumps(new_data, indent=2),
                content_type="application/json",
                if_generation_match=generation,
            )
        except PreconditionFailed:
            logger.info(f"CAS conflict on state.json (attempt {attempt+1}/3)")
            continue
        except Exception as e:
            logger.error(f"State write failed: {e}")
            return False

        # Write status.txt compatibility
        status_blob = bucket.blob(f"runs/{run_id}/status.txt")
        try:
            status_blob.upload_from_string(
                status_compat(new_state), content_type="text/plain"
            )
        except Exception:
            pass

        # Event log
        try:
            short_uuid = uuid.uuid4().hex[:8]
            ts = datetime.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
            event_blob = bucket.blob(f"runs/{run_id}/events/{ts}_reconciler_{short_uuid}.json")
            event_blob.upload_from_string(json.dumps(entry), content_type="application/json")
        except Exception:
            pass

        logger.info(f"State written: {current_state} → {new_state} for {run_id}")
        return True

    logger.error(f"CAS retries exhausted for {run_id}")
    return False


def _repair_status_drift(bucket, run_id, state_data):
    """Check and repair status.txt drift from state.json."""
    state = state_data.get("state", "")
    if not state or state == "RESTARTING":
        return  # Don't repair during RESTARTING

    expected_status = status_compat(state)
    actual_status = _blob_text(bucket, f"runs/{run_id}/status.txt")
    if actual_status is not None:
        actual_status = actual_status.strip()

    if actual_status == expected_status:
        return  # No drift

    # Check drift repair disabled marker
    if _blob_exists(bucket, f"runs/{run_id}/.drift_repair_disabled"):
        logger.warning(f"[{run_id}] Drift detected but repair disabled")
        return

    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would repair status.txt drift: '{actual_status}' → '{expected_status}'")
        return

    logger.warning(f"[{run_id}] Status drift: status.txt='{actual_status}', expected='{expected_status}'. Repairing.")
    try:
        blob = bucket.blob(f"runs/{run_id}/status.txt")
        blob.upload_from_string(expected_status, content_type="text/plain")
    except Exception as e:
        logger.error(f"Drift repair failed: {e}")


def _reconcile_run(bucket, run_id):
    """Reconcile a single run. Returns action taken (string) or None."""
    prefix = f"runs/{run_id}/"

    # Read state.json
    state_data = _blob_json(bucket, f"{prefix}state.json")
    heartbeat_data = _blob_json(bucket, f"{prefix}heartbeat.json")
    restart_config = _blob_json(bucket, f"{prefix}restart_config.json")

    # Determine current state
    current_state = state_data.get("state") if state_data else None

    # Skip terminal states
    if current_state and is_terminal(current_state):
        return None

    # Repair status.txt drift
    if state_data:
        _repair_status_drift(bucket, run_id, state_data)

    # RESTARTING stuck-state recovery
    if current_state == "RESTARTING":
        updated_at = state_data.get("updated_at", "")
        if updated_at:
            try:
                updated_dt = _parse_iso(updated_at)
                age_sec = (datetime.datetime.utcnow() - updated_dt).total_seconds()
                if age_sec > RESTARTING_STUCK_SEC:
                    # Check if VM exists
                    inst_name = state_data.get("instance_name", "")
                    zone = state_data.get("zone", "")
                    vm_alive = False
                    if inst_name and zone:
                        vm_alive = _vm_exists(inst_name, zone)

                    hb_fresh = False
                    if heartbeat_data:
                        hb_ts = heartbeat_data.get("timestamp", "")
                        if hb_ts:
                            try:
                                hb_dt = _parse_iso(hb_ts)
                                hb_age = (datetime.datetime.utcnow() - hb_dt).total_seconds()
                                hb_fresh = hb_age < HEARTBEAT_STALE_SEC
                            except ValueError:
                                pass

                    if not vm_alive and not hb_fresh:
                        logger.warning(
                            f"[{run_id}] RESTARTING stuck (age={age_sec:.0f}s, no VM, no heartbeat). "
                            "Transitioning to ORPHANED."
                        )
                        _write_state_cas(bucket, run_id, "ORPHANED", "restarting_stuck_recovery")
                        # Clean up stale restart.lock
                        if not DRY_RUN:
                            try:
                                bucket.blob(f"{prefix}restart.lock").delete()
                            except Exception:
                                pass
                        _notify_discord(
                            f"WARN: [{run_id}] RESTARTING stuck for {age_sec:.0f}s. Recovered to ORPHANED.",
                            dry_run=DRY_RUN,
                        )
                        return "restarting_stuck_recovered"
            except ValueError:
                pass
        return None

    # Skip if no heartbeat yet (container may still be starting)
    if not heartbeat_data:
        # Legacy run check: no state.json AND no heartbeat AND no restart_config
        if not state_data and not restart_config:
            # Could be a very old run or one that never started
            return None
        return None

    # ── Two-stage stale detection ──

    hb_ts_str = heartbeat_data.get("timestamp", "")
    if not hb_ts_str:
        return None

    try:
        hb_dt = _parse_iso(hb_ts_str)
    except ValueError:
        return None

    hb_age_sec = (datetime.datetime.utcnow() - hb_dt).total_seconds()

    if hb_age_sec < HEARTBEAT_STALE_SEC:
        # Heartbeat is fresh — clear any stale marker
        if _blob_exists(bucket, f"{prefix}.reconciler_stale_seen"):
            if not DRY_RUN:
                try:
                    bucket.blob(f"{prefix}.reconciler_stale_seen").delete()
                except Exception:
                    pass
            logger.info(f"[{run_id}] Heartbeat recovered, cleared stale marker")
        return None

    # Heartbeat is stale
    stale_marker = _blob_json(bucket, f"{prefix}.reconciler_stale_seen")

    if stale_marker is None:
        # First observation
        marker_data = {
            "timestamp": _now_iso(),
            "heartbeat_epoch_at_observation": hb_ts_str,
        }
        if not DRY_RUN:
            try:
                blob = bucket.blob(f"{prefix}.reconciler_stale_seen")
                blob.upload_from_string(
                    json.dumps(marker_data), content_type="application/json"
                )
            except Exception as e:
                logger.error(f"Failed to write stale marker: {e}")
        logger.info(f"[{run_id}] First stale observation (hb_age={hb_age_sec:.0f}s)")
        _notify_discord(
            f"INFO: [{run_id}] Heartbeat stale ({hb_age_sec:.0f}s). First observation recorded.",
            dry_run=DRY_RUN,
        )
        return "stale_first_observation"

    # Second+ observation — verify conditions
    marker_ts = stale_marker.get("timestamp", "")
    marker_hb_epoch = stale_marker.get("heartbeat_epoch_at_observation", "")

    # Check minimum time between observations
    try:
        marker_dt = _parse_iso(marker_ts)
        marker_age = (datetime.datetime.utcnow() - marker_dt).total_seconds()
        if marker_age < STALE_MARKER_MIN_AGE_SEC:
            logger.info(f"[{run_id}] Stale marker too fresh ({marker_age:.0f}s < {STALE_MARKER_MIN_AGE_SEC}s)")
            return None
    except ValueError:
        pass

    # Verify heartbeat hasn't changed since marker was written
    if marker_hb_epoch and marker_hb_epoch != hb_ts_str:
        # Heartbeat changed but is still stale — reset marker
        logger.info(f"[{run_id}] Heartbeat changed since marker (was {marker_hb_epoch}, now {hb_ts_str}). Resetting marker.")
        if not DRY_RUN:
            try:
                bucket.blob(f"{prefix}.reconciler_stale_seen").delete()
            except Exception:
                pass
        return None

    # Verify VM is actually gone
    inst_name = ""
    zone = ""
    if state_data:
        inst_name = state_data.get("instance_name", "")
        zone = state_data.get("zone", "")

    # Fallback: check run_manifest
    if not inst_name or not zone:
        manifest = _blob_json(bucket, f"{prefix}run_manifest.json")
        if manifest:
            inst_name = inst_name or manifest.get("instance", "")
            zone = zone or manifest.get("zone", "")

    if inst_name and zone:
        if _vm_exists(inst_name, zone):
            logger.warning(f"[{run_id}] VM {inst_name} still exists despite stale heartbeat. Warning only.")
            _notify_discord(
                f"WARN: [{run_id}] Heartbeat stale ({hb_age_sec:.0f}s) but VM {inst_name} still exists.",
                dry_run=DRY_RUN,
            )
            return "stale_vm_alive"
    else:
        # No instance info — try pattern search
        vm_info = _vm_search_by_pattern(run_id)
        if vm_info:
            logger.warning(f"[{run_id}] Found VM via pattern: {vm_info['name']} ({vm_info['zone']})")
            return "stale_vm_found_by_pattern"

    # ── VM confirmed gone + 2 stale observations → ORPHANED ──

    if current_state == "PREEMPTED":
        # Already preempted — notification only needed, state is correct
        logger.info(f"[{run_id}] Already PREEMPTED, confirmed by reconciler")
        _notify_discord(
            f"INFO: [{run_id}] Confirmed PREEMPTED (stale heartbeat + VM gone).",
            dry_run=DRY_RUN,
        )
        return "preempted_confirmed"

    # Determine target state
    if state_data:
        target = "ORPHANED"
        _write_state_cas(bucket, run_id, target, "stale_heartbeat_vm_gone")
    else:
        # Legacy run: no state.json
        if not DRY_RUN:
            # Bootstrap ORPHANED state for legacy run
            _write_state_cas(bucket, run_id, "ORPHANED", "legacy_bootstrap_orphaned")
        logger.info(f"[{run_id}] Legacy run (no state.json): bootstrapped as ORPHANED")

    _notify_discord(
        f"WARN: [{run_id}] ORPHANED — heartbeat stale ({hb_age_sec:.0f}s), VM gone. "
        f"Instance: {inst_name or 'unknown'}",
        dry_run=DRY_RUN,
    )

    # Clean up stale marker
    if not DRY_RUN:
        try:
            bucket.blob(f"{prefix}.reconciler_stale_seen").delete()
        except Exception:
            pass

    # Attempt restart if eligible
    restart_action = _try_restart(bucket, run_id, state_data, restart_config)
    if restart_action:
        return restart_action

    return "orphaned"


def _is_restart_enabled(bucket):
    """Check if reconciler restart is enabled via GCS feature flag."""
    try:
        text = _blob_text(bucket, ".reconciler_restart_enabled")
        if text:
            data = json.loads(text)
            return data.get("enabled_at") is not None
    except Exception:
        pass
    return False


def _acquire_restart_lock_cas(bucket, run_id, attempt):
    """Acquire restart.lock via CAS (if-generation-match=0). Returns (blob, generation) or None."""
    blob = bucket.blob(f"runs/{run_id}/restart.lock")
    payload = json.dumps({
        "actor": "reconciler",
        "hostname": "cloud-function",
        "acquired_at": _now_iso(),
        "attempt": attempt,
        "ttl_sec": 300,
    })
    try:
        blob.upload_from_string(payload, content_type="application/json", if_generation_match=0)
        return blob, blob.generation
    except PreconditionFailed:
        # Lock exists — check if stale and reclaimable
        try:
            existing = json.loads(blob.download_as_text())
            existing_gen = blob.generation
            acquired_at = existing.get("acquired_at", "")
            ttl = existing.get("ttl_sec", 300)
            if acquired_at:
                acq_dt = _parse_iso(acquired_at)
                age = (datetime.datetime.utcnow() - acq_dt).total_seconds()
                if age > ttl:
                    # Stale — attempt atomic reclaim
                    try:
                        blob.delete(if_generation_match=existing_gen)
                        # Re-acquire
                        blob.upload_from_string(
                            payload, content_type="application/json", if_generation_match=0
                        )
                        logger.info(f"[{run_id}] Reclaimed stale restart.lock (age={age:.0f}s)")
                        return blob, blob.generation
                    except PreconditionFailed:
                        logger.info(f"[{run_id}] Restart lock reclaim race lost")
                        return None
        except Exception as e:
            logger.warning(f"[{run_id}] Error checking stale lock: {e}")
        return None
    except Exception as e:
        logger.error(f"[{run_id}] Restart lock acquire failed: {e}")
        return None


def _clear_owner_lock_preconditioned(bucket, run_id, project=None):
    """Clear run_owner.json / .owner.lock with preconditioned delete."""
    project = project or PROJECT

    for lock_name in [".owner.lock"]:
        blob = bucket.blob(f"runs/{run_id}/{lock_name}")
        try:
            raw = blob.download_as_text()
            gen = blob.generation
            data = json.loads(raw)
        except Exception:
            continue

        # Verify owner instance is gone
        inst = data.get("instance", "")
        zone = data.get("zone", "")
        if inst and zone:
            if _vm_exists(inst, zone, project):
                logger.error(f"[{run_id}] Owner VM {inst} still exists. Aborting restart.")
                return False

        # Delete with generation match
        try:
            blob.delete(if_generation_match=gen)
            logger.info(f"[{run_id}] Owner lock cleared")
        except PreconditionFailed:
            logger.error(f"[{run_id}] Owner lock generation mismatch")
            return False

    return True


def _create_vm_from_config(run_id, restart_config, attempt, zone):
    """Create a VM from restart_config.json parameters."""
    project = restart_config.get("project", PROJECT)
    machine_type = restart_config.get("machine_type", "n1-standard-8")
    image = restart_config.get("image", "")
    sa = restart_config.get("service_account", "")
    bucket = restart_config.get("bucket", BUCKET_NAME)
    boot_disk_size = restart_config.get("boot_disk_size_gb", "50")
    boot_disk_type = restart_config.get("boot_disk_type", "pd-ssd")
    gpu_enabled = restart_config.get("gpu_enabled", False)
    gpu_type = restart_config.get("gpu_type", "")
    metadata_prefix = restart_config.get("metadata_prefix", "spot")
    runner_label = restart_config.get("runner_label", "spot-runner")
    job_command = restart_config.get("job_command", "")
    conda_env = restart_config.get("conda_env", "")
    notify_secret = restart_config.get("notify_secret", "")
    container_name = restart_config.get("container_name", "spot-runner")
    region = restart_config.get("region", "us-east1")

    import base64
    job_b64 = base64.b64encode(job_command.encode()).decode()

    # Sanitize VM name
    label_run_id = run_id.lower().replace("_", "-")[:55]
    vm_name = f"{container_name}-{label_run_id}-{attempt}"[:63].lower()
    # Ensure starts with letter
    if not vm_name[0].isalpha():
        vm_name = f"vm-{vm_name}"[:63]

    compute_client = _get_compute_client()

    # Build metadata
    metadata_items = [
        {"key": f"{metadata_prefix}-image-ref", "value": image},
        {"key": f"{metadata_prefix}-run-id", "value": run_id},
        {"key": f"{metadata_prefix}-bucket", "value": bucket},
        {"key": f"{metadata_prefix}-job-command", "value": job_b64},
        {"key": f"{metadata_prefix}-conda-env", "value": conda_env},
        {"key": f"{metadata_prefix}-notify-secret", "value": notify_secret},
        {"key": "spot-metadata-prefix", "value": metadata_prefix},
    ]
    if gpu_enabled:
        metadata_items.append({"key": "install-nvidia-driver", "value": "true"})

    # Read startup script
    # For reconciler, we need the startup script content
    # It should be available from the restart_config or from GCS
    startup_script = restart_config.get("startup_script", "")
    if startup_script:
        metadata_items.append({"key": "startup-script", "value": startup_script})

    instance_resource = compute_v1.Instance(
        name=vm_name,
        machine_type=f"zones/{zone}/machineTypes/{machine_type}",
        scheduling=compute_v1.Scheduling(
            provisioning_model="SPOT",
            instance_termination_action="DELETE",
            on_host_maintenance="TERMINATE",
        ),
        disks=[
            compute_v1.AttachedDisk(
                auto_delete=True,
                boot=True,
                initialize_params=compute_v1.AttachedDiskInitializeParams(
                    source_image="projects/cos-cloud/global/images/family/cos-stable",
                    disk_size_gb=int(boot_disk_size),
                    disk_type=f"zones/{zone}/diskTypes/{boot_disk_type}",
                ),
            )
        ],
        network_interfaces=[
            compute_v1.NetworkInterface(
                access_configs=[compute_v1.AccessConfig(name="External NAT")]
            )
        ],
        service_accounts=[
            compute_v1.ServiceAccount(email=sa, scopes=["https://www.googleapis.com/auth/cloud-platform"])
        ],
        metadata=compute_v1.Metadata(items=metadata_items),
        labels={
            "runner_label": runner_label,
            "run_id": label_run_id,
            "project": project,
            "region": region,
        },
    )

    if gpu_enabled and gpu_type:
        instance_resource.guest_accelerators = [
            compute_v1.AcceleratorConfig(
                accelerator_type=f"zones/{zone}/acceleratorTypes/{gpu_type}",
                accelerator_count=1,
            )
        ]

    try:
        op = compute_client.insert(project=project, zone=zone, instance_resource=instance_resource)
        op.result()  # Wait for completion

        # Verify instance exists
        compute_client.get(project=project, zone=zone, instance=vm_name)
        return vm_name
    except Exception as e:
        logger.error(f"VM creation failed: {e}")
        return None


def _try_restart(bucket, run_id, state_data, restart_config):
    """Attempt to restart a run after PREEMPTED/ORPHANED detection."""
    if DRY_RUN:
        logger.info(f"[DRY-RUN] Would attempt restart for {run_id}")
        _notify_discord(f"INFO: [{run_id}] Would restart (dry-run).", dry_run=True)
        return None

    if not _is_restart_enabled(bucket):
        logger.info(f"[{run_id}] Restart not enabled (missing .reconciler_restart_enabled)")
        return None

    if not restart_config:
        logger.info(f"[{run_id}] No restart_config.json — cannot restart (legacy run?)")
        return None

    current_state = state_data.get("state") if state_data else None
    if current_state not in ("PREEMPTED", "ORPHANED"):
        return None

    # Check attempt count
    max_restarts = restart_config.get("auto_restart_max", 3)
    current_attempt = state_data.get("attempt", 0) if state_data else 0
    if current_attempt >= max_restarts:
        logger.info(f"[{run_id}] Restart exhausted ({current_attempt}/{max_restarts})")
        return None

    # Check .stop file
    if _blob_exists(bucket, f"runs/{run_id}/.stop"):
        logger.info(f"[{run_id}] .stop file exists, skipping restart")
        return None

    new_attempt = current_attempt + 1
    logger.info(f"[{run_id}] Attempting restart (attempt {new_attempt}/{max_restarts})")

    # Step 1: Acquire restart.lock
    lock_result = _acquire_restart_lock_cas(bucket, run_id, new_attempt)
    if not lock_result:
        logger.info(f"[{run_id}] Could not acquire restart.lock (another actor may be restarting)")
        return None
    lock_blob, lock_gen = lock_result

    try:
        # Step 2: Clear owner lock
        if not _clear_owner_lock_preconditioned(bucket, run_id):
            raise RuntimeError("Owner lock clearance failed")

        # Step 3: CAS state → RESTARTING
        if not _write_state_cas(bucket, run_id, "RESTARTING", "reconciler_restart"):
            raise RuntimeError("CAS RESTARTING failed")

        # Step 4: Create VM
        zones = restart_config.get("fallback_zones", [])
        if not zones:
            zones = [restart_config.get("zone", "us-east1-c")]

        vm_name = None
        final_zone = None
        for zone in zones:
            vm_name = _create_vm_from_config(run_id, restart_config, new_attempt, zone)
            if vm_name:
                final_zone = zone
                break
            logger.warning(f"[{run_id}] Zone {zone} failed, trying next...")

        if not vm_name:
            raise RuntimeError("All zones exhausted")

        # Step 5: Release restart.lock (create op DONE + instance exists)
        try:
            lock_blob.delete(if_generation_match=lock_gen)
        except Exception:
            lock_blob.delete()

        _notify_discord(
            f"INFO: [{run_id}] Restarted as {vm_name} in {final_zone} "
            f"(attempt {new_attempt}/{max_restarts})"
        )
        logger.info(f"[{run_id}] Restart successful: {vm_name} in {final_zone}")
        return "restarted"

    except Exception as e:
        logger.error(f"[{run_id}] Restart failed: {e}")

        # Rollback: state back to previous
        if state_data:
            prev = state_data.get("state", "ORPHANED")
            _write_state_cas(bucket, run_id, prev, "restart_rollback")

        # Release lock
        try:
            lock_blob.delete(if_generation_match=lock_gen)
        except Exception:
            try:
                lock_blob.delete()
            except Exception:
                pass

        _notify_discord(f"ERROR: [{run_id}] Restart failed: {e}")
        return "restart_failed"


def _discover_active_runs(bucket):
    """Discover run IDs that may need reconciliation.

    Looks for runs with heartbeat.json (active or recently active).
    """
    run_ids = set()
    prefix = "runs/"

    # List all run prefixes that have heartbeat.json
    blobs = bucket.list_blobs(prefix=prefix, delimiter="/")
    # The prefixes represent run directories
    for page in blobs.pages:
        for prefix_name in page.prefixes:
            # prefix_name looks like "runs/some-run-id/"
            run_id = prefix_name.replace("runs/", "").rstrip("/")
            if run_id:
                run_ids.add(run_id)

    return run_ids


def reconcile_all():
    """Main reconciliation loop. Scans all active runs."""
    logger.info(f"Reconciler starting (DRY_RUN={DRY_RUN}, project={PROJECT}, bucket={BUCKET_NAME})")

    # Log state_transitions.json hash
    try:
        th = transitions_hash()
        logger.info(f"state_transitions.json SHA-256: {th}")
    except Exception:
        logger.warning("Could not compute transitions hash")

    client = _get_storage_client()
    bucket = client.bucket(BUCKET_NAME)

    run_ids = _discover_active_runs(bucket)
    logger.info(f"Discovered {len(run_ids)} run(s)")

    actions = {}
    for run_id in sorted(run_ids):
        try:
            action = _reconcile_run(bucket, run_id)
            if action:
                actions[run_id] = action
        except Exception as e:
            logger.error(f"Error reconciling {run_id}: {e}", exc_info=True)

    logger.info(f"Reconciliation complete. Actions: {len(actions)}")
    for rid, act in actions.items():
        logger.info(f"  {rid}: {act}")

    return actions


@functions_framework.http
def reconcile_http(request):
    """HTTP entry point for Cloud Functions."""
    actions = reconcile_all()
    return json.dumps({"status": "ok", "actions": actions}), 200


@functions_framework.cloud_event
def reconcile_event(cloud_event):
    """Cloud Event entry point (for Pub/Sub trigger from Cloud Scheduler)."""
    reconcile_all()


if __name__ == "__main__":
    reconcile_all()
