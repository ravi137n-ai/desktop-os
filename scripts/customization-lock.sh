#!/usr/bin/env bash
# Source this helper. Keep the descriptor open for the entire customization.
# Never unlink the lock file: overlapping processes must lock the same inode.
acquire_customization_lock() {
  local lock_file="$1"
  exec {DESKTOP_OS_CUSTOMIZATION_LOCK_FD}>>"$lock_file"
  if ! flock -n "$DESKTOP_OS_CUSTOMIZATION_LOCK_FD"; then
    echo "Refusing: this target is already being customized." >&2
    return 1
  fi
}