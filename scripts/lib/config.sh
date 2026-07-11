#!/usr/bin/env bash

atlas_load_config() {
  local project_dir="${ATLAS_PROJECT_DIR:-/opt/project-atlas}"
  local config_file="$project_dir/config/atlas.conf"
  local module_state_file="$project_dir/config/modules/modules.conf"

  if [[ ! -f "$config_file" ]]; then
    echo "Missing Atlas config: $config_file" >&2
    return 1
  fi

  # shellcheck disable=SC1090
  source "$config_file"

  if [[ -f "$module_state_file" ]]; then
    # shellcheck disable=SC1090
    source "$module_state_file"
  fi

  export ATLAS_PROJECT_DIR
  export ATLAS_MODULE_STATE_FILE="$module_state_file"
}
