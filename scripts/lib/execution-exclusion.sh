# Shared ephemeral exclusion for Scheduler and live Atlas transactions.
#
# This is intentionally separate from:
#   - deployments/update.lock, which is durable recovery ownership; and
#   - scheduler/tasks.lock, which serializes Scheduler executions.
#
# The kernel flock exists only while the owning process is alive. Failed
# transactional operations may release this ephemeral lock while retaining
# deployments/update.lock; Scheduler separately refuses to run while that
# durable lock exists.

atlas_execution_exclusion_lock_file() {
  printf '%s/deployment-scheduler.lock\n' \
    "$ATLAS_RUNTIME_CONFIG_DIR"
}

atlas_execution_exclusion_acquire() {
  local output_variable="${1:-}"
  local lock
  local acquired_fd

  [[ "$output_variable" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || {
    echo \
      'ERROR: invalid execution-exclusion descriptor variable.' \
      >&2
    return 1
  }

  lock="$(atlas_execution_exclusion_lock_file)"

  mkdir -p "$(dirname "$lock")" || {
    echo \
      'ERROR: unable to prepare deployment/Scheduler exclusion lock.' \
      >&2
    return 1
  }

  exec {acquired_fd}> "$lock" || {
    echo \
      'ERROR: unable to open deployment/Scheduler exclusion lock.' \
      >&2
    return 1
  }

  if ! flock -n "$acquired_fd"; then
    exec {acquired_fd}>&-

    echo \
      'ERROR: Scheduler/deployment execution is already in progress.' \
      >&2

    return 1
  fi

  printf -v "$output_variable" '%s' "$acquired_fd"
}

atlas_execution_exclusion_release() {
  local fd="${1:-}"
  local status=0

  [[ "$fd" =~ ^[0-9]+$ ]] || {
    echo \
      'ERROR: invalid execution-exclusion descriptor.' \
      >&2
    return 1
  }

  flock -u "$fd" || status=$?

  # fd is validated as numeric above before interpolation.
  eval "exec ${fd}>&-" || status=1

  return "$status"
}
