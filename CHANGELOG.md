# Changelog

All notable changes to this project are documented in this file.

## Unreleased

Fixed:
- CI: replaced local symlinks for bats test libraries (`bats-core`, `bats-assert`,
  `bats-support`) with proper git submodules so tests run in CI environments.
- CI: added fallback adapter stubs in `test_helper.bash` so adapter contract tests
  pass without a local `gcp-spot-runner` checkout.
- CI: `test_state_transitions_parity.bats` now skips gracefully when sibling
  `gcp-spot-runner` checkout is not present.

Changed:
- `gcp/cloud_reconciler/deploy.sh` now delegates through shared helper
  `spot_runner_wrapper_run_project_reconciler_command_entrypoint_required`, so
  `SPOT_CONFIG_PATH` override wiring + runtime setup + `reconciler_deploy` dispatch
  are enforced by one runner entrypoint contract (using optional runtime args for RAV).
- `gcp/cloud_reconciler/deploy.sh` now calls
  `run_project_command "reconciler_deploy"` directly; removed wrapper-local
  `run_reconciler_deploy` alias from `scripts/gcp_runner_common.sh`.
- `scripts/{gcp_ops.sh,gcp_monitor.sh,gcp_version.sh}` now delegate through shared helper
  `spot_runner_wrapper_run_project_named_command_entrypoint_required` with fixed command names,
  and `scripts/gcp_runner_common.sh` dropped wrapper-local `run_ops_command`,
  `run_monitor_command`, and `run_version_command` aliases.
- `scripts/{gcp_ops.sh,gcp_monitor.sh,gcp_version.sh}` now derive command names from wrapper
  script names (`gcp_*.sh`) via shared helper
  `spot_runner_wrapper_run_project_named_command_from_script_entrypoint_required`, removing
  repeated hard-coded command strings in thin wrappers while preserving runtime-arg behavior.
- `scripts/{gcp_ops.sh,gcp_monitor.sh,gcp_version.sh}` now route through shared helper
  `spot_runner_wrapper_run_project_profile_named_command_from_script_entrypoint_required`,
  so standard-command wrappers inherit profile/command runtime defaults from the shared
  runner contract (including version-path optional env loading) without wrapper-local
  runtime arg literals.
- `scripts/gcp_runner_common.sh` now exposes `run_rav_standard_command_wrapper`, and
  `scripts/{gcp_ops.sh,gcp_monitor.sh,gcp_version.sh}` now call that one wrapper-common
  function (delegating through shared callsite entrypoint helper), removing repeated
  per-script adapter helper invocation blocks.
- `gcp/GETTING_STARTED.md` and `docs/INDEX.md` now document the standard-wrapper naming
  contract (`gcp_*.sh` -> derived command name) for thin operator wrappers.
- `scripts/gcp_runner_common.sh` `run_submit_entrypoint_with_job` now uses the shared
  optional-runtime submit-entrypoint contract directly (no wrapper-local no-op runtime
  callback needed).
- `scripts/gcp_runner_common.sh` now centralizes shared submit-wrapper runtime prep, context
  logging, and submit-entrypoint invocation through
  `prepare_rav_submit_runtime_and_print_context` +
  `run_submit_entrypoint_with_job`; `gcp_submit_primary.sh`,
  `gcp_submit_poc.sh`, and `gcp_submit_chexpert_experiment.sh` now only define
  mode-specific job commands.
- `scripts/{gcp_submit_primary.sh,gcp_submit_poc.sh,gcp_submit_chexpert_experiment.sh}` now
  delegate submit-shell + submit dispatch through shared helper
  `spot_runner_wrapper_run_project_submit_entrypoint_required`, reducing repeated
  wrapper-local submit-entrypoint wiring.
- `scripts/gcp_build_image.sh` now delegates build-arg composition through shared helper
  `spot_runner_wrapper_run_project_build_entrypoint_required`, reducing wrapper-local
  `--source` / `--cloudbuild-config` / optional `--image` wiring.
- `scripts/{gcp_ops.sh,gcp_monitor.sh,gcp_version.sh}` now delegate through shared helper
  `spot_runner_wrapper_run_project_command_entrypoint_required`, reducing repeated
  runtime+command entrypoint boilerplate in thin wrappers.
- `scripts/gcp_runner_common.sh` `run_project_command` now delegates through shared helper
  `spot_runner_wrapper_run_project_profile_command_with_paths_required`, reducing wrapper-local
  profile command argument plumbing while retaining shared config-mode behavior.
- `scripts/gcp_runner_common.sh` runtime setup now delegates through shared helper
  `spot_runner_wrapper_setup_project_profile_runtime_required`, reducing repeated
  profile runtime argument plumbing in the thin wrapper.
- `scripts/gcp_runner_common.sh` now routes common command dispatch (`ops`,
  `submit_with_job`, `build`, `monitor`, `version`, `reconciler_deploy`) through one
  wrapper-local helper `run_project_command`, which now directly requires shared
  profile-aware command helper
  `spot_runner_wrapper_run_project_profile_command_required`; shared runner helper
  ownership now handles profile+command config-mode selection plus fallback dispatch
  sequencing internally. `reconciler_deploy` now routes through the same shared
  dispatch path, removing the remaining wrapper-local fallback branch for dedicated
  reconciler deploy wiring.
- `tests/bats/test_runner_adapter.bats` fake runner adapter now stubs
  `spot_runner_wrapper_run_project_standard_command_compat_required`, keeping
  reconciler wrapper contract tests aligned with the shared dispatch-helper requirement.
- `tests/bats/{test_helper.bash,test_runner_adapter.bats}` now also stub
  `spot_runner_wrapper_run_project_standard_command_active_required` and
  `spot_runner_wrapper_run_project_standard_command_loaded_required`, keeping RAV
  adapter tests aligned with the new shared mode-specific dispatch entrypoints.
- `scripts/gcp_runner_common.sh` now delegates submit-shell/caffeinate setup through shared
  profile-aware helper
  `spot_runner_wrapper_prepare_project_submit_shell_for_profile_from_args_required`, and submit
  wrappers (`gcp_submit_primary.sh`, `gcp_submit_poc.sh`,
  `gcp_submit_chexpert_experiment.sh`) now forward `"$@"` directly to
  `prepare_submit_shell` (no wrapper-local submit-guard alias state required).
- `gcp/state_helpers.sh` now uses shared helper
  `spot_runner_wrapper_source_project_state_helpers_required_or_fail`, removing duplicate
  wrapper-local state-helper failure plumbing.
- `gcp/state_helpers.sh` now uses shared helper
  `spot_runner_wrapper_ensure_project_runner_defaults_if_unset_required` for conditional
  `RUNNER_DIR` default resolution, removing duplicated wrapper-local unset checks.
- `gcp/state_helpers.sh` now routes both of those state-wrapper steps through one shared helper
  `spot_runner_wrapper_init_project_state_helpers_wrapper_required`, reducing wrapper entrypoint
  glue and keeping state-wrapper initialization single-sourced in `gcp-spot-runner`.
- `tests/bats/test_helper.bash` fallback adapter stubs now include
  `spot_runner_wrapper_run_project_command_with_mode` (+ required variant),
  `spot_runner_wrapper_run_project_standard_command_required`,
  `spot_runner_wrapper_source_project_state_helpers_required_or_fail`, and
  `spot_runner_wrapper_ensure_project_runner_defaults_if_unset` (+ required variant), plus
  `spot_runner_wrapper_init_project_state_helpers_wrapper_required`, for parity with the
  expanded shared runner helper contract.
- `scripts/gcp_runner_common.sh` now resolves command config paths through shared helper
  `spot_runner_wrapper_resolve_config_path_required` (`active` for submit/ops/build/monitor,
  `loaded` for version), removing wrapper-local `_active_config_path` and
  `_loaded_config_path` glue.
- `tests/bats/test_helper.bash` fallback adapter stubs now include
  `spot_runner_wrapper_resolve_config_path` and
  `spot_runner_wrapper_resolve_config_path_required` for parity with the updated shared
  runner helper surface.
- **Revert iCloud git isolation**: Reverted `.git.nosync/` back to standard `.git/` directory
  after migrating repo from `~/Documents/Programming/` to `~/coding/` (outside iCloud scope).
  Removed gitdir redirect and xattr. Updated `.gitignore`, `.dockerignore`, `.gcloudignore`.
  Historical context preserved in comments.
- `scripts/gcp_runner_common.sh` now delegates project env loading, resolved `RUNNER_DIR`
  assignment, runtime validation, and install checks through shared project-wrapper helpers in
  `gcp-spot-runner/adapters/spot_runner_common.sh`, removing more wrapper-local setup logic.
- `scripts/gcp_runner_common.sh` now exposes `prepare_rav_runtime`, and RAV thin wrapper entrypoints
  (`gcp_submit_*`, `gcp_build_image.sh`, `gcp_ops.sh`, `gcp_monitor.sh`, `gcp_version.sh`,
  `gcp_iterate_chexpert.sh`) now call that shared setup path instead of repeating
  load/defaults/check/install/gcloud boilerplate per script.
- `scripts/gcp_runner_common.sh` `prepare_rav_runtime` now requires shared helper
  `spot_runner_wrapper_setup_project_runtime_required` directly, removing wrapper-local
  runtime setup fallback branches.
- Removed unused wrapper-local runtime shim functions from `scripts/gcp_runner_common.sh`
  (`load_rav_spot_env`, `check_runner_install`, `configure_gcloud_runtime`,
  `check_required_spot_vars`); runtime/env/install/gcloud validation remains centralized
  in shared helper `spot_runner_wrapper_setup_project_runtime_required`.
- `scripts/gcp_runner_common.sh` bootstrap preamble is now reduced to a single candidate-resolution
  loop plus required shared initializer call (`spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required`),
  removing the wrapper-local bootstrap helper function wrapper.
- `scripts/gcp_runner_common.sh` bootstrap preamble now delegates default candidate
  initializer wiring through shared helper
  `spot_runner_bootstrap_initialize_project_wrapper_from_default_candidates_required`,
  reducing duplicated bootstrap argument plumbing in thin wrappers.
- Removed unused wrapper-local shim functions `load_rav_spot_env_optional()` and
  `run_spotctl_with_config()` from `scripts/gcp_runner_common.sh`; runtime env loading and
  spotctl dispatch stay centralized behind shared required helper contracts.
- Removed unused wrapper-local shim function `apply_runner_defaults()` from
  `scripts/gcp_runner_common.sh`; state-helper runner-dir resolution now calls shared required
  helper `spot_runner_wrapper_apply_project_runner_defaults_required` directly.
- `tests/bats/test_runner_adapter.bats` removed direct tests for the retired
  `load_rav_spot_env_optional` and `run_spotctl_with_config` shims.
- `tests/bats/test_runner_adapter.bats` removed the direct test for retired shim
  `apply_runner_defaults`.
- `gcp/state_helpers.sh` now resolves default runner directory via shared required helper
  `spot_runner_wrapper_apply_project_runner_defaults_required` directly (instead of routing
  through the removed `apply_runner_defaults` shim).
- `gcp/cloud_reconciler/deploy.sh` now also uses `prepare_rav_runtime` (optional-env, no
  spot-var/gcloud checks) before delegating reconciler deploy through the shared runner contract.
- `gcp/cloud_reconciler/deploy.sh` now prefers shared helper
  `spot_runner_wrapper_apply_spot_config_path_override` for `SPOT_CONFIG_PATH` override wiring
  (with fallback for older runner helper surfaces).
- `gcp/cloud_reconciler/deploy.sh` now requires shared helper
  `spot_runner_wrapper_apply_spot_config_path_override_required`, dropping wrapper-local helper
  detection/fallback branches for `SPOT_CONFIG_PATH` override wiring.
- `gcp/state_helpers.sh` now calls `apply_runner_defaults` before loading shared
  `state_helpers.sh`, ensuring `RUNNER_DIR` resolution flows through shared runner-default
  logic even when `RUNNER_DIR` is not pre-exported.
- `scripts/gcp_runner_common.sh` now delegates direct `spotctl`, profiled dispatch, ops/build/monitor,
  and version command wiring through shared project-wrapper command helpers in
  `gcp-spot-runner/adapters/spot_runner_common.sh`.
- `tests/bats/test_runner_adapter.bats` now stubs shared project-wrapper command helpers directly
  so RAV adapter contract tests remain stable as command wiring moves deeper into shared runner
  helpers.
- `scripts/gcp_runner_common.sh` no longer carries local runtime/install contract declarations
  (profile hint text and required runner file list); those now resolve through shared profile-based
  helpers in `gcp-spot-runner/adapters/spot_runner_common.sh`.
- `scripts/gcp_runner_common.sh` now derives runner install hint text from shared profile helper
  `spot_runner_wrapper_profile_hint_or_default`, removing wrapper-local hint fallback logic and
  repeated inline hint literals across env-load/runtime/install/dispatch error paths.
- `scripts/gcp_runner_common.sh` now prefers shared hint assignment helper
  `spot_runner_wrapper_assign_profile_hint_compat`, reducing wrapper-local hint initialization
  branching while preserving compatibility with older helper surfaces.
- `scripts/gcp_runner_common.sh` now prefers shared hint-assignment entrypoint helper
  `spot_runner_wrapper_assign_profile_hint_entrypoint_compat_or_fallback`, reducing wrapper-local
  hint fallback branching across helper versions.
- `scripts/gcp_runner_common.sh` now drops redundant post-entrypoint fallback branches in profile
  hint assignment and submit-shell setup, relying on shared entrypoint helpers to own those
  fallback paths.
- `scripts/gcp_runner_common.sh` bootstrap preamble now uses a simplified candidate loop and
  initializer call path while preserving shared bootstrap helper behavior.
- `scripts/gcp_runner_common.sh` bootstrap preamble now routes through shared helper
  `spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required`, centralizing
  candidate-list bootstrap initialization under one required entrypoint.
- `scripts/gcp_runner_common.sh` bootstrap candidate discovery now runs through a single ordered
  loop (`RUNNER_DIR`, primary sibling checkout, worktree sibling checkout), reducing additional
  wrapper-local branch duplication in the thin bootstrap preamble.
- `scripts/gcp_runner_common.sh` now delegates RAV runtime/env default initialization through
  shared helper `spot_runner_wrapper_apply_rav_defaults`, reducing wrapper-local default
  assignment logic.
- `scripts/gcp_runner_common.sh` bootstrap preamble now prefers shared runtime bootstrap helper
  `spot_runner_bootstrap_source_project_runtime`, with fallback to legacy
  bootstrap-contract/common sourcing paths for older runner checkouts.
- `tests/bats/test_runner_adapter.bats` fake runner helpers now cover the current
  project-wrapper helper contract for reconciler deploy wrapper execution.
- `tests/bats/test_helper.bash` and `tests/bats/test_runner_adapter.bats` now stub shared
  helper `spot_runner_wrapper_require_function_or_hint`, keeping wrapper tests hermetic as
  required-helper checks move into shared runner helper contracts.
- `scripts/gcp_runner_common.sh`, `gcp/cloud_reconciler/deploy.sh`, and `gcp/state_helpers.sh` now preserve shared wrapper semantics when pointed at older minimal runner helper stubs, including local env/config resolution and install/runtime guard fallbacks.
- RAV thin-wrapper runner resolution and parity tests now recognize sibling worktree checkouts such as `../gcp-spot-runner-codex` in addition to the standard sibling repo layout.
- `gcp/state_helpers.sh` now resolves `RUNNER_DIR` through `scripts/gcp_runner_common.sh` and delegates shared state-helper runtime loading/fallback behavior through `gcp-spot-runner/adapters/spot_runner_common.sh`.
- `gcp/state_helpers.sh` now routes state-helper runtime/fallback sourcing through shared helper
  `spot_runner_source_state_helpers_entrypoint_compat`, removing duplicated wrapper-local
  runtime-or-exit/shared-file fallback branches.
- `gcp/state_helpers.sh` now prefers shared wrapper-level helper
  `spot_runner_wrapper_source_project_state_helpers_entrypoint_compat`, reducing additional
  wrapper-local state-helper entrypoint fallback wiring.
- `gcp/state_helpers.sh` now prefers shared wrapper-level helper
  `spot_runner_wrapper_source_project_state_helpers_entrypoint_compat_or_fallback`, reducing
  additional wrapper-local state-helper fallback branching across helper versions.
- `gcp/state_helpers.sh` now prefers shared helper
  `spot_runner_wrapper_source_project_state_helpers_or_fail`, reducing additional wrapper-local
  state-helper entrypoint branching and direct fallback wiring.
- `gcp/state_helpers.sh` now drops the redundant direct runtime-or-exit fallback branch; the
  shared entrypoint helper owns that fallback behavior.
- `scripts/gcp_runner_common.sh` command helpers (`run_ops_command`, `run_build_command`, `run_monitor_command`, `run_version_command`) now rely on shared runner wrapper command helpers directly, removing local per-command fallback branches in RAV.
- `scripts/gcp_runner_common.sh` now routes `run_build_command` and `run_monitor_command`
  through shared helpers `spot_runner_wrapper_run_project_build_with_config` and
  `spot_runner_wrapper_run_project_monitor_with_config`, removing wrapper-local profiled
  dispatch shim wiring.
- `scripts/gcp_runner_common.sh` now centralizes required runner-helper checks through
  `_require_runner_function`, and `apply_runner_defaults` uses that helper when validating
  `spot_runner_wrapper_apply_rav_defaults`.
- `scripts/gcp_runner_common.sh` now centralizes active config resolution through
  `_active_config_path`, and submit/ops/build/monitor dispatch helpers consume that shared
  config-path helper instead of repeating inline config fallback expressions.
- `scripts/gcp_runner_common.sh` now resolves active/version config paths through shared helper
  `spot_runner_wrapper_resolve_active_config_path` (with local fallback for older runner
  checkouts), reducing wrapper-local config-path fallback logic.
- `scripts/gcp_runner_common.sh` now centralizes loaded-config-only resolution through
  `_loaded_config_path`; `run_version_command` and `gcp/cloud_reconciler/deploy.sh` now consume
  that helper so non-submit command paths consistently avoid default-config fallback unless a
  config file is actually loaded.
- `gcp/cloud_reconciler/deploy.sh` now derives default reconciler function/scheduler names via
  shared helper `spot_runner_wrapper_profile_reconciler_defaults_required` instead of wrapper-local
  hardcoded literals.
- `gcp/cloud_reconciler/deploy.sh` now delegates reconciler deploy through shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_with_profile_defaults_required`, removing
  wrapper-local default-name helper plumbing.
- `gcp/cloud_reconciler/deploy.sh` now delegates loaded-config resolution plus reconciler deploy
  through shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_with_loaded_config_required`, reducing
  wrapper-local config-path glue in the thin deploy wrapper.
- `scripts/gcp_runner_common.sh` now exposes `run_reconciler_deploy`, and
  `gcp/cloud_reconciler/deploy.sh` now delegates through that helper so deploy-wrapper dispatch
  arguments are single-sourced in runner-common.
- `_loaded_config_path` in `scripts/gcp_runner_common.sh` now prefers shared helper
  `spot_runner_wrapper_resolve_loaded_config_path` (with fallback to
  `spot_runner_wrapper_resolve_active_config_path` and local logic), reducing wrapper-local
  loaded-config branch handling.
- `scripts/gcp_runner_common.sh` now requires shared config-path helper contracts
  `spot_runner_wrapper_resolve_active_config_path_required` and
  `spot_runner_wrapper_resolve_loaded_config_path_required`, removing remaining wrapper-local
  config-path fallback branching after bootstrap.
- `scripts/gcp_runner_common.sh` now uses shared helper
  `spot_runner_wrapper_require_function_or_hint` directly for required-helper checks in
  `apply_runner_defaults`, dropping wrapper-local required-function check glue.
- `scripts/gcp_runner_common.sh` and `gcp/cloud_reconciler/deploy.sh` now derive profile
  dispatch from `RUNNER_PROFILE` instead of hardcoded `rav` literals, keeping profile identity
  single-sourced in the thin wrapper.
- `scripts/gcp_runner_common.sh` dispatch helpers (`run_spotctl_with_config`,
  `run_build_command`, `run_monitor_command`) now rely directly on shared wrapper dispatch
  helpers, removing local fallback branches for direct/profiler command routing.
- `tests/bats/test_helper.bash` now stubs
  `spot_runner_wrapper_run_project_build_with_config` and
  `spot_runner_wrapper_run_project_monitor_with_config`, keeping RAV adapter tests hermetic
  with the updated shared command-helper surface.
- `scripts/gcp_runner_common.sh` runtime/install guard helpers now rely directly on shared runner guard contracts (`spot_runner_require_wrapper_runtime_or_exit`, `spot_runner_wrapper_require_project_install_for_profile_compat_or_exit`), removing wrapper-local compatibility fallback branches.
- `scripts/gcp_runner_common.sh` optional env loading and resolved `RUNNER_DIR` selection now rely directly on shared compat helper contracts (`spot_runner_wrapper_load_project_env_optional_compat`, `spot_runner_wrapper_resolve_project_runner_dir_compat_or_exit`) after bootstrap, removing wrapper-local compatibility fallback branches for those paths.
- `scripts/gcp_runner_common.sh` now uses shared helper
  `spot_runner_wrapper_load_project_env_required_compat_or_exit` for required env-file guidance and
  `spot_runner_wrapper_run_project_submit_with_job` for submit wrapper defaults, reducing
  wrapper-local required-env and `--skip-build` command wiring.
- `scripts/gcp_runner_common.sh` submit path now delegates through
  `spot_runner_wrapper_run_project_submit_with_job_compat`, so submit wrappers use the shared
  runner entrypoint contract directly instead of carrying wrapper-local submit fallback logic.
- `gcp/cloud_reconciler/deploy.sh` now prefers shared reconciler deploy entrypoint compat helper
  `spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat`, keeping reconciler
  dispatch/fallback behavior centralized in `gcp-spot-runner`.
- `gcp/cloud_reconciler/deploy.sh` now uses a single shared entrypoint path plus direct
  `spotctl` fallback, removing duplicated intermediate reconciler fallback branches from RAV.
- `gcp/cloud_reconciler/deploy.sh` now prefers shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat_or_fallback`, further
  reducing wrapper-local reconciler deploy fallback wiring.
- `gcp/cloud_reconciler/deploy.sh` now drops the redundant legacy reconciler-entrypoint branch
  after the new shared helper check, keeping one direct `spotctl` fallback path.
- `gcp/cloud_reconciler/deploy.sh` now requires shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat_or_fallback` and delegates
  reconciler deploy through that contract directly, removing remaining wrapper-local fallback arg
  assembly.
- `gcp/cloud_reconciler/deploy.sh` now prefers shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_from_env` for default-name + env-override
  dispatch, while preserving fallback to
  `spot_runner_wrapper_run_project_reconciler_deploy_entrypoint_compat_or_fallback` for older
  runner helper surfaces.
- Removed project-local reconciler Python wrapper artifacts
  (`gcp/cloud_reconciler/{main.py,state_machine.py,requirements.txt,__init__.py}`); RAV now keeps
  only `gcp/cloud_reconciler/deploy.sh` as the thin project wrapper while reconciler implementation
  remains canonical in `gcp-spot-runner/cloud_reconciler/`.
- `gcp/cloud_reconciler/deploy.sh` now requires shared helper
  `spot_runner_wrapper_run_project_reconciler_deploy_from_env` directly (instead of carrying a
  wrapper-local fallback branch), further reducing RAV reconciler wrapper compatibility wiring.
- `gcp/state_helpers.sh` now requires shared helper
  `spot_runner_wrapper_source_project_state_helpers_or_fail` directly (instead of carrying a
  wrapper-local direct-source fallback branch), further reducing RAV state-helper wrapper
  compatibility wiring.
- `gcp/state_helpers.sh` now routes through shared required-helper
  `spot_runner_wrapper_source_project_state_helpers_required`, reducing wrapper-local
  state-helper contract enforcement boilerplate.
- `scripts/gcp_runner_common.sh` bootstrap/hint setup now routes through shared required-helper
  `spot_runner_bootstrap_initialize_project_wrapper_required`, centralizing contract enforcement
  for wrapper initialization.
- `scripts/gcp_runner_common.sh` `prepare_submit_shell` now routes through shared required-helper
  `spot_runner_wrapper_prepare_project_submit_shell_entrypoint_required`, centralizing
  submit-shell entrypoint contract enforcement.
- `scripts/gcp_runner_common.sh` `apply_runner_defaults` now routes through shared
  required-helper `spot_runner_wrapper_apply_rav_defaults_required`, centralizing RAV default
  initializer contract enforcement.
- `scripts/gcp_runner_common.sh` `apply_runner_defaults` now delegates through shared helper
  `spot_runner_wrapper_apply_project_runner_defaults_required`, reducing wrapper-local
  runner-dir/default setup plumbing.
- `tests/bats/test_helper.bash` and `tests/bats/test_runner_adapter.bats` now stub
  `spot_runner_wrapper_apply_rav_defaults_required`, keeping RAV adapter tests hermetic with
  the updated required-helper contract surface.
- `tests/bats/test_helper.bash` now stubs
  `spot_runner_bootstrap_initialize_project_wrapper_from_candidates_required`, keeping RAV
  bootstrap adapter tests hermetic with the updated required-helper contract surface.
- `gcp/cloud_reconciler/deploy.sh` now routes through shared required-helper
  `spot_runner_wrapper_run_project_reconciler_deploy_from_env_required`, reducing wrapper-local
  reconciler helper contract enforcement boilerplate.
- `tests/bats/test_runner_adapter.bats` reconciler adapter stub now includes the new shared
  compat helper symbols used by `scripts/gcp_runner_common.sh` bootstrap/env/install paths.
- `tests/bats/test_runner_adapter.bats` and `tests/bats/test_helper.bash` now include the
  submit compat helper stub so adapter tests remain hermetic when no sibling
  `gcp-spot-runner` checkout is available.
- `scripts/gcp_runner_common.sh` now exposes `prepare_submit_shell` and submit wrappers
  (`gcp_submit_primary.sh`, `gcp_submit_poc.sh`, `gcp_submit_chexpert_experiment.sh`,
  `gcp_iterate_chexpert.sh`) now delegate submit-shell/caffeinate setup through that helper,
  removing duplicated wrapper-local submit-shell preamble wiring.
- `scripts/gcp_runner_common.sh` `prepare_submit_shell` now delegates through shared runner helper
  `spot_runner_wrapper_prepare_project_submit_shell_compat`, reducing duplicated submit-shell
  wiring between IXQT/RAV thin wrappers.
- `scripts/gcp_runner_common.sh` `prepare_submit_shell` now prefers shared wrapper entrypoint
  helper `spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat`, reducing
  additional wrapper-local submit-shell fallback wiring.
- `scripts/gcp_runner_common.sh` `prepare_submit_shell` now prefers shared entrypoint-or-fallback
  helper `spot_runner_wrapper_prepare_project_submit_shell_entrypoint_compat_or_fallback`,
  reducing additional wrapper-local submit-shell fallback branching across helper versions.
- `scripts/gcp_runner_common.sh` now removes redundant legacy submit-shell fallback dispatch
  branches after the shared submit entrypoint helper check.
- `scripts/gcp_runner_common.sh` bootstrap runner-checkout discovery now routes through shared helper `adapters/spot_runner_bootstrap.sh`, replacing the duplicated local candidate-resolution preamble while keeping direct fallback to `adapters/spot_runner_common.sh`.
- `scripts/gcp_runner_common.sh` bootstrap runtime dispatch now uses shared helper
  `spot_runner_bootstrap_source_project_runtime_or_common`, removing duplicated local fallback
  branches across bootstrap runtime/adapter helper variants.
- `scripts/gcp_runner_common.sh` now prefers shared bootstrap entrypoint
  `spot_runner_bootstrap_source_project_entrypoint_compat`, centralizing bootstrap-library
  discovery + runtime fallback dispatch through one shared compat path.
- `scripts/gcp_runner_common.sh` now prefers shared bootstrap wrapper initializer
  `spot_runner_bootstrap_initialize_wrapper_compat`, reducing additional duplicated bootstrap
  fallback sequencing in the RAV thin wrapper.
- `scripts/gcp_runner_common.sh` now prefers shared bootstrap wrapper entrypoint helper
  `spot_runner_bootstrap_initialize_wrapper_entrypoint_compat`, reducing additional
  wrapper-local bootstrap initializer fallback wiring.
- `scripts/gcp_runner_common.sh` bootstrap preamble now prefers shared helper
  `spot_runner_bootstrap_initialize_wrapper_entrypoint_compat_or_fallback`, reducing
  duplicated bootstrap fallback branching in the thin wrapper.
- `scripts/gcp_runner_common.sh` bootstrap preamble now routes through shared helper
  `spot_runner_bootstrap_initialize_project_wrapper`, centralizing bootstrap initialization and
  profile-hint assignment under one shared bootstrap helper contract.
- `scripts/gcp_runner_common.sh` now removes the redundant direct source-entrypoint bootstrap
  fallback branch after shared bootstrap entrypoint helper checks.
- `tests/bats/test_runner_adapter.bats` fake runner helpers now cover the current shared wrapper runtime contract for `version` and reconciler deploy delegation after rebasing onto `gcp-spot-runner v0.6.34`.
- PR #1 follow-up cleanup: removed legacy `_require_runner_adapter_lib` from
  `scripts/gcp_runner_common.sh`, switched `gcp/cloud_reconciler/deploy.sh` to
  shared `check_runner_install`, and removed a duplicate
  `spot_runner_wrapper_require_project_install_for_profile_or_exit` stub definition in
  `tests/bats/test_runner_adapter.bats`.
- Restored `tests/bats/lib/{bats-core,bats-support,bats-assert}` as real git submodules
  (gitlink entries) and added `.gitmodules` URLs, so CI can initialize BATS dependencies
  instead of failing on missing local-only symlink targets.
- `tests/bats/test_runner_adapter.bats` now stubs required shared helper symbols in
  `load_rav_spot_env_optional` and `apply_runner_defaults` tests, and
  `tests/bats/test_state_transitions_parity.bats` now skips cleanly when a sibling
  `gcp-spot-runner` checkout is unavailable in CI.

Updated:
- App version to `v0.2.46-profile-install-runtime-contracts`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.6.38-profile-install-runtime-contracts` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`
- App version to `v0.2.44-project-wrapper-command-helpers`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.6.36-project-wrapper-command-helpers` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`
- App version to `v0.2.43-project-wrapper-runtime-helpers`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.6.35-project-wrapper-runtime-helpers` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`
- App version to `v0.2.42-runner-bootstrap-discovery`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.6.34-runner-bootstrap-discovery` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

Added:
- Corrupt image handling in `src/rav_chest/data.py`: `__getitem__` catches `UnidentifiedImageError`/`OSError` and returns `None`; new `skip_none_collate` filters corrupt samples from batches.
- `scripts/train_chest_baseline.py` uses `skip_none_collate` and skips `None` batches in train/eval loops.
- CheXpert 5-task mixed uncertainty training/eval path:
  - `scripts/train_chexpert_5task_policy.py`
  - `scripts/eval_chexpert_5task_policy.py`
  - `configs/primary/chest_chexpert_5task_policy.yaml`
- CheXpert experiment orchestration helpers:
  - `scripts/gcp_submit_chexpert_experiment.sh`
  - `scripts/gcp_iterate_chexpert.sh`
  - `scripts/gcp_autotune_after_current_runs.sh`
- New regularized experiment configs:
  - `configs/primary/chest_chexpert_u0_regularized.yaml`
  - `configs/primary/chest_chexpert_u1_regularized.yaml`
  - `configs/primary/chest_chexpert_umixed_regularized.yaml`
  - `configs/primary/chest_chexpert_umixed_regularized_posw.yaml`
  - `configs/primary/chest_chexpert_effb0_umixed_posw.yaml`
- `gcp/DATASET_TRANSFER.md` troubleshooting entry for zero-byte files after `gcloud storage rsync` upload (~9% of CheXpert-Small affected), with detection commands and `-c` checksum re-sync fix.
- `gcp/GCP_NOTES.md` Section 13: DataLoader shared memory exhaustion root cause and `--shm-size=2g` fix.
- `gcp/GCP_NOTES.md` Section 14: Immediate preemption not retried (one-shot restart bug) root cause and while-loop fix.

Updated:
- `scripts/gcp_train_with_checkpoint_sync.sh` supports config-selected train/eval scripts via:
  - `project.train_script`
  - `project.eval_script`
- `gcp/GETTING_STARTED.md`, `gcp/GCP_NOTES.md`, and `docs/CHEST_RUNBOOK.md` now document the stale-image (`--skip-build`) failure mode and rebuild requirement after runtime file changes.
- `scripts/gcp_sync_chexpert_cache.sh` line 104: pass missing `"$uri"` arg to `_write_marker` (fixed `$2: unbound variable` crash after successful rsync).
- `gcp/rav_spot.env`: `MAX_RESTARTS` bumped from 3 to 10 (matching IXQT).
- `gcp/rav_spot.env`: GPU upgraded from T4 to L4 (`MACHINE_TYPE=g2-standard-8`, `GPU_TYPE=nvidia-l4`).
- `gcp/GCP_NOTES.md` Section 2→G documents the `_write_marker` unbound variable bug.
- Runner lineage: `gcp-spot-runner v0.6.27-wrapper-command-surface-helpers` (IXQT/RAV wrapper ops/build/monitor/reconciler dispatch and RAV submit now route through shared helper paths to reduce adapter duplication).

- Adapter contract tests for shared runner delegation:
  - `tests/bats/test_runner_adapter.bats` verifies `scripts/gcp_runner_common.sh` maps submit/ops calls to `spotctl` with `--profile rav` + `--config` + `--job-command` semantics.
- `tests/bats/test_runner_adapter.bats` verifies `gcp_submit_primary.sh` / `gcp_submit_poc.sh` re-exec through `caffeinate` with `_SPOT_CAFFEINATED` guard in executable wrapper flow.
  - `tests/bats/test_runner_adapter.bats` verifies `apply_runner_defaults` aligns data-disk defaults with runner profile contract (`DATA_DISK_ENABLED=true`, mount path/device/fs defaults).
  - `tests/bats/test_runner_adapter.bats` verifies `watch --json` passthrough reaches shared runner ops unchanged.
  - `tests/bats/test_runner_adapter.bats` verifies `scripts/gcp_submit_primary.sh` and `scripts/gcp_submit_poc.sh` default job commands invoke `gcp_train_with_checkpoint_sync.sh` with expected config/eval split + sync interval, and that `SYNC_INTERVAL_SEC` overrides are reflected in submit payloads.
  - `tests/bats/test_runner_adapter.bats` verifies `JOB_COMMAND_PRIMARY` / `JOB_COMMAND_POC` override env vars are passed through verbatim to shared-runner submit payloads.
  - `tests/bats/test_runner_adapter.bats` verifies `gcp/cloud_reconciler/deploy.sh` delegates to `spotctl reconciler deploy` with expected profile/default args.
  - `tests/bats/test_runner_adapter.bats` verifies `run_build_command` delegates to `spotctl build --profile rav --config ...` with passthrough args.
  - `tests/bats/test_runner_adapter.bats` verifies `run_monitor_command` delegates to `spotctl monitor --profile rav --config ...` with passthrough args.
  - `tests/bats/test_runner_adapter.bats` verifies `gcp_build_image.sh` delegates primary build execution through shared `run_build_command`.
  - `tests/bats/test_runner_adapter.bats` verifies `gcp_monitor.sh` delegates through shared `run_monitor_command`.
  - `tests/bats/test_runner_adapter.bats` verifies unified `scripts/rav-gcp.sh` command dispatch/aliases for submit/build/monitor/ops flows.
  - `tests/bats/test_runner_adapter.bats` verifies `rav-gcp --version` alias dispatch to shared runner version wrapper.
  - `tests/bats/test_runner_adapter.bats` verifies `rav-gcp -V` short-flag alias dispatch to shared runner version wrapper.
  - `tests/bats/test_state_helpers_wrapper.bats` verifies `gcp/state_helpers.sh` resolves and sources shared `gcp-spot-runner/state_helpers.sh`.
  - `tests/bats/test_state_transitions_parity.bats` verifies `gcp/state_transitions.json` hash matches `gcp-spot-runner/cloud_reconciler/state_transitions.json`.
  - `tests/bats/test_version_parity.bats` verifies app-version references stay aligned across `src/rav_chest/version.py`, `README.md`, `gcp/GCP_NOTES.md`, and unreleased changelog entries; also checks runner-lineage version parity across those docs.
  - `.github/workflows/gcp-adapter-tests.yml` runs RAV adapter BATS suites on push/PR.
  - `scripts/gcp_monitor.sh` thin wrapper for `spotctl monitor --profile rav`.
  - `scripts/rav-gcp.sh` unified CLI wrapper for RAV GCP operations (`submit`/`poc`/`build`/`monitor`/`ops` + status/event/serial/list/watch/delete/preempt aliases).

Updated:
- `scripts/gcp_runner_common.sh` now defaults `DATA_DISK_MOUNT_PATH` to `/var/lib/spot-data` (COS writable path) to match runner profile/runtime defaults.
- `scripts/gcp_runner_common.sh` now defaults `DATA_DISK_ENABLED=true` to match RAV profile/runtime contract.
- `scripts/gcp_build_image.sh` now delegates build execution (including staged-source fallback) through `spotctl build --profile rav`.
- `scripts/rav-gcp.sh` now supports `--version` / `-V` aliases (delegates to `gcp_version.sh` -> `spotctl version`).
- `gcp/cloud_reconciler/deploy.sh` now sources shared adapter helper library `gcp-spot-runner/adapters/spot_runner_common.sh` for canonical install checks and `spotctl` execution wiring.
- `tests/bats/test_runner_adapter.bats` now stages a fake shared adapter helper in reconciler-wrapper fixture setup to keep adapter contract coverage aligned with deploy wrapper behavior.
- `Makefile` GCP targets now route through unified `scripts/rav-gcp.sh` command surface.
- RAV operator docs now treat `./scripts/rav-gcp.sh` as canonical command entrypoint while preserving `scripts/gcp_*.sh` compatibility wrappers:
  - `README.md`
  - `gcp/GETTING_STARTED.md`
  - `gcp/GCP_NOTES.md`
  - `docs/CHEST_RUNBOOK.md`
- Runner lineage docs synchronized to `gcp-spot-runner v0.6.27-wrapper-command-surface-helpers` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`
- App version to `v0.2.35-wrapper-command-surface-helpers`.
- Added `AGENTS.md` routing file that points shared GCP orchestration behavior to `../gcp-spot-runner/docs/INDEX.md`.

Changed:
- `scripts/gcp_submit_primary.sh`, `scripts/gcp_submit_poc.sh`, `scripts/gcp_submit_chexpert_experiment.sh`, and `scripts/gcp_iterate_chexpert.sh` now route submit preamble setup (`caffeinate` re-exec + ignore-HUP trap) through shared helper compatibility wiring (`spot_runner_prepare_submit_shell_compat`) in `scripts/gcp_runner_common.sh`, with canonical `_SPOT_CAFFEINATED` guard + legacy alias compatibility.
- `scripts/gcp_runner_common.sh` now sources shared adapter helper library `gcp-spot-runner/adapters/spot_runner_common.sh` for canonical runner install checks and `spotctl` invocation wiring.
- `scripts/gcp_runner_common.sh` now dispatches directly to shared compat helpers (`spot_runner_run_spotctl_compat`, `spot_runner_run_profiled_compat`) rather than carrying local safe-helper fallback branches.
- `scripts/gcp_runner_common.sh` now uses shared submit-preamble compat helpers (`spot_runner_maybe_reexec_caffeinate_compat`, `spot_runner_prepare_submit_shell_compat`) from `gcp-spot-runner` when available, with local compatibility fallback definitions only for missing-helper checkouts.
- `scripts/gcp_runner_common.sh` now uses shared cached helper loading (`spot_runner_require_adapter_lib_cached`) for adapter library sourcing instead of wrapper-local loaded-flag/source logic.
- `scripts/gcp_runner_common.sh` now routes loader symbol guard + cached helper loading through shared strict helper (`spot_runner_require_adapter_lib_cached_strict`) to remove wrapper-local guard boilerplate.
- `scripts/gcp_runner_common.sh` now validates required shared helper symbols via `spot_runner_require_functions_or_hint` and removes wrapper-local submit-compat fallback definitions.
- `scripts/gcp_runner_common.sh` now delegates adapter runtime init through shared helper `spot_runner_require_wrapper_runtime`, replacing duplicated wrapper init sequences.
- `scripts/gcp_runner_common.sh` now resolves `RUNNER_DIR` in `apply_runner_defaults` via shared helper `spot_runner_resolve_runner_dir_compat`, removing wrapper-local compatibility resolution logic.
- `scripts/gcp_runner_common.sh` command shim functions (`run_spotctl_with_config`, `_run_profiled_with_config`) now delegate through shared wrapper-dispatch helpers (`spot_runner_wrapper_run_spotctl_compat`, `spot_runner_wrapper_run_profiled_compat`).
- `scripts/gcp_runner_common.sh` now routes `run_ops_command`, `run_build_command`, and `run_monitor_command` through shared wrapper command helpers (`spot_runner_wrapper_run_ops_compat`, `spot_runner_wrapper_run_profiled_command_compat`) before compatibility fallback paths.
- `gcp/cloud_reconciler/deploy.sh` now dispatches through shared reconciler-deploy wrapper helper (`spot_runner_wrapper_run_reconciler_deploy_compat`) before compatibility fallbacks.
- `gcp/state_helpers.sh` now delegates wrapper resolution/source behavior through shared adapter loader `gcp-spot-runner/adapters/state_helpers_wrapper.sh` (instead of carrying full local resolver/source logic).
- Removed runner-internal BATS checks from RAV adapter test suite (`tests/bats/test_submit_stopped.bats`, `tests/bats/test_lib_restart.bats`, `tests/bats/test_entrypoint.bats`).
- Replaced structural-only `tests/bats/test_caffeinate.bats` with behavior-first wrapper execution tests in `tests/bats/test_runner_adapter.bats`.
- Removed duplicate state-machine BATS behavior suite from RAV (`tests/bats/test_state_machine.bats`); shared transition behavior is now validated in `gcp-spot-runner/tests/bats/test_state_helpers.bats`.
- Removed duplicate shared reconciler Python suites from RAV (`tests/test_reconciler.py`, `tests/test_state_machine.py`); canonical reconciler/state-machine Python tests now live in `gcp-spot-runner/tests/test_reconciler_runtime.py`.
- `gcp/state_helpers.sh` is now a thin wrapper over shared runner helper implementation (`gcp-spot-runner/state_helpers.sh`).

## v0.2.13-profile-hook-runtime - 2026-03-02

Updated:
- `scripts/gcp_submit_primary.sh` default job command now runs training only; dataset sync is expected via runner profile hook (`pre_job_sync`).
- `gcp/rav_spot.env.example` updated to document hook-driven primary submit behavior.
- App version to `v0.2.13-profile-hook-runtime`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.4-profile-hook-runtime` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.12-profile-runtime-submit - 2026-03-02

Updated:
- `scripts/gcp_runner_common.sh` submit/ops path simplified to profile runtime invocation (no temporary generated config files):
  - submit: `spotctl submit --profile rav --config gcp/rav_spot.env --job-command "<cmd>"`
  - ops: `spotctl ops --profile rav --config gcp/rav_spot.env ...`
- App version to `v0.2.12-profile-runtime-submit`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.3-submit-job-command-override` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.11-reconciler-profile-wrapper - 2026-03-02

Updated:
- `gcp/cloud_reconciler/deploy.sh` now delegates reconciler deploy with explicit shared profile resolution:
  - `python3 -m spotctl reconciler deploy --profile rav`
  - optional `--config gcp/rav_spot.env` (or `SPOT_CONFIG_PATH`) for env overlay values.
- App version to `v0.2.11-reconciler-profile-wrapper`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.2-reconciler-profile-runtime` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.10-spotctl-direct-wrapper - 2026-03-02

Updated:
- `scripts/gcp_runner_common.sh` now delegates submit/ops directly to `python3 -m spotctl` with `SPOT_CONFIG_PATH`, instead of temp symlinked runner script execution.
- `gcp/cloud_reconciler/deploy.sh` now delegates via shared runner interface:
  - `python3 -m spotctl reconciler deploy`
  instead of invoking runner deploy internals directly.
- Runner install checks now validate `spotctl` + legacy backend files in `gcp-spot-runner`.
- App version to `v0.2.10-spotctl-direct-wrapper`.
- Runner lineage docs synchronized to `gcp-spot-runner v0.5.0-spotctl-cli-shims` in:
  - `README.md`
  - `gcp/GCP_NOTES.md`

## v0.2.9-reconciler-centralized-wrapper - 2026-03-02

Updated:
- `gcp/cloud_reconciler/main.py` and `state_machine.py` are now thin wrappers that execute shared source from `gcp-spot-runner/cloud_reconciler/`.
- `gcp/cloud_reconciler/deploy.sh` now delegates deployment to shared runner deploy script.
- `gcp/cloud_reconciler/requirements.txt` now points to shared runner requirements.
- App version to `v0.2.9-reconciler-centralized-wrapper`.
- Spot runner lineage version in README to `gcp-spot-runner v0.4.0-reconciler-centralization`.

## v0.2.8-reconciler-phase1-hardening - 2026-03-02

Updated:
- GCP persistent-disk docs and defaults now use a writable COS mount path:
  - `DATA_DISK_MOUNT_PATH="/var/lib/spot-data"`
  - Avoids startup failure: `mkdir: cannot create directory '/mnt/spot-data': Read-only file system`
- GCP troubleshooting docs now include explicit diagnosis/remediation for the COS read-only mount-path failure.
- GCP docs now call out region selection flexibility (for example `us-central1`) when `us-east1` is shared/constrained.
- Cloud reconciler hardening (Phase 1 reliability):
  - `gcp/cloud_reconciler/state_machine.py`: transition-file path resolution now works in both source and flat Cloud Function deploy layouts.
  - `gcp/cloud_reconciler/main.py`: restart attempt persistence fixed via `attempt_override`; restart now fails closed when `startup_script` is missing.
  - `gcp/cloud_reconciler/main.py`: persistent data disk now attaches on reconciler restarts, including startup metadata for mount behavior.
  - `gcp/cloud_reconciler/main.py`: restart zone is pinned when `data_disk_enabled=true` to avoid cross-zone disk attach failures.
  - `gcp/cloud_reconciler/main.py` + `deploy.sh`: removed IXQT-pinned defaults; runtime/deploy config is now env-driven.
- Reconciler tests expanded:
  - `tests/test_reconciler.py`: added behavior tests for incremented-attempt persistence, disk-zone pinning, and startup-script requirement.
  - `tests/test_state_machine.py`: added transitions path resolution coverage.
- App version to `v0.2.8-reconciler-phase1-hardening`.
- Spot runner lineage version in README to `gcp-spot-runner v0.3.1-phase1-reliability-hardening`.

## v0.2.7-gcp-docs-version-sync - 2026-03-01

Added:
- Cross-repo version lineage documentation in README (`RAV` + `gcp-spot-runner` mapping).
- GCP notes updates for recent CheXpert incident triage and run-history interpretation.

Updated:
- App version to `v0.2.7-gcp-docs-version-sync`.
- Documentation pointers for active GCP operations notes and runner-version context.

## v0.2.6-gcp-spot-resilience - 2026-03-01

Added:
- **State machine** (`gcp/state_transitions.json`, `gcp/state_helpers.sh`): Canonical state contract (RUNNING, COMPLETE, FAILED, PARTIAL, PREEMPTED, ORPHANED, RESTARTING, STOPPED) with CAS transitions via GCS `if_generation_match`.
- **Preemption watcher** (`gcp/entrypoint.sh`): Background process polls GCE metadata preemption endpoint every 5s; on preempt, CAS writes PREEMPTED state, sends Discord notification, kills heartbeat.
- **`_write_state()` CAS helper** (`gcp/entrypoint.sh`): Python-based state transitions with state_transitions.json validation, status.txt compatibility mapping, event logging.
- **Startup terminal guard** (`gcp/entrypoint.sh`): VM reads state.json before owner-lock; self-deletes on terminal state (STOPPED/COMPLETE/FAILED/PARTIAL).
- **Cloud reconciler** (`gcp/cloud_reconciler/`): Cloud Function for two-stage stale detection (heartbeat stale + VM confirmed gone), status.txt drift repair, restart orchestration via restart.lock.
- **`restart_config.json`** (`scripts/gcp_submit_primary.sh`): Authoritative restart source written at submit time with all VM parameters.
- **STOPPED handling** in submit scripts: poll loop, status classification, and pre-poll smoke check all handle STOPPED as terminal.
- **`caffeinate` + HUP trap** (`scripts/gcp_submit_primary.sh`, `scripts/gcp_submit_poc.sh`): Prevent macOS idle sleep and survive terminal close.
- **Secret Manager integration** (`scripts/gcp_runner_common.sh`): `ixqt-notify-secret` metadata passed to VMs for Discord webhook resolution via REST API.
- **BATS tests** (`tests/bats/`): 119 tests covering state machine, preemption watcher, CAS transitions, reconciler detection/restart, restart.lock protocol, status.txt drift repair.
- **Python tests** (`tests/test_reconciler.py`, `tests/test_state_machine.py`): 77 tests for reconciler and state machine logic.

Updated:
- PARTIAL status migration: now canonical `PARTIAL` (detail in `status_meta.json`, not in status string).
- `gcp/Dockerfile.train` packages `state_transitions.json` into container image.
- App version to `v0.2.6-gcp-spot-resilience`.

## v0.2.5 - 2026-02-28

Updated:
- Moved GCP_NOTES to `gcp/`, documented GPU fix and ops commands.

## v0.2.4-agent-qa-chat - 2026-02-27

Added:
- Natural-language model Q&A support in `src/rav_chest/llm.py` via `answer_question_about_report`.
- New Streamlit `Ask Agent` page with chat-style interaction grounded in report context.
- Inference payload persistence in Streamlit session state so users can run inference then ask follow-up questions immediately.

Updated:
- Sidebar model selector now supports both rewrite and Q&A flows (`LLM Model (Rewrite/Q&A)`).
- App version to `v0.2.4-agent-qa-chat`.

## v0.2.3-gcp-build-hardening - 2026-02-27

Added:
- Explicit Cloud Build upload rules in `.gcloudignore` (source-only allowlist plus cache/artifact exclusions).
- Centralized one-off GCP setup/fix commands section in `gcp/GETTING_STARTED.md`.

Updated:
- GCP wrapper runtime hardening in `scripts/gcp_runner_common.sh`:
  - `CLOUDSDK_CORE_DISABLE_PROMPTS=1`
  - `CLOUDSDK_PYTHON_SITEPACKAGES=0`
  - auto-select `CLOUDSDK_PYTHON` from local `.venv` when available
  - normalize `RUNNER_DIR` to an absolute path
- GCP wrapper scripts now consistently apply runtime config before invoking gcloud/runner:
  - `scripts/gcp_build_image.sh`
  - `scripts/gcp_submit_primary.sh`
  - `scripts/gcp_submit_poc.sh`
  - `scripts/gcp_ops.sh`
- App version to `v0.2.3-gcp-build-hardening`.

## v0.2.2-gcp-getting-started-docs - 2026-02-27

Added:
- GCP onboarding/quickstart guide at `gcp/GETTING_STARTED.md`.

Updated:
- Added cross-links to the guide from README and chest runbook GCP sections.
- App version to `v0.2.2-gcp-getting-started-docs`.

## v0.2.1-gcp-spot-checkpoint-resume - 2026-02-27

Added:
- GCP training wrapper at `scripts/gcp_train_with_checkpoint_sync.sh` to make spot runs preemption-safe.
- Periodic sync of checkpoints/metrics to GCS during training (`SYNC_INTERVAL_SEC`).
- Bootstrap resume behavior: auto-download `last.pt` from GCS and pass `--resume-checkpoint` when available.
- `--run-id` resume workflow documented for both primary and POC submit paths.

Updated:
- Spot submit wrappers now route both tracks through checkpoint-sync wrapper:
  - `scripts/gcp_submit_primary.sh`
  - `scripts/gcp_submit_poc.sh`
- `gcp/rav_spot.env.example` with `SYNC_INTERVAL_SEC` and updated override examples.
- README + runbook GCP sections with explicit checkpoint sync/resume behavior.
- App version to `v0.2.1-gcp-spot-checkpoint-resume`.

## v0.2.0-openai-llm-rewrite - 2026-02-27

Added:
- OpenAI API wrapper module at `src/rav_chest/llm.py`.
- CLI wrapper at `scripts/llm_wrapper.py` with prompt mode and report-JSON rewrite mode.
- Optional Streamlit inference rewrite flow:
  - Sidebar toggle `Rewrite impression with OpenAI`.
  - Model selector `LLM Model`.
  - Side-by-side deterministic vs rewritten impression display.
  - `llm_rewrite` metadata persisted in downloaded report JSON.
- Automatic `.env` API key resolution for `OPENAI_API_KEY`.
- `.env.example` template for local key setup.

Updated:
- `requirements.txt` with `openai>=1.0,<2`.
- README and runbook usage docs for wrapper + Streamlit LLM rewrite flow.
- Sidebar app version string to `v0.2.0-openai-llm-rewrite`.
