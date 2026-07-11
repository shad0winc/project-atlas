#!/usr/bin/env bash

atlas_command_modules() {
  atlas_print_header
  atlas_section "Installed Modules"

  local module

  while IFS= read -r module; do
    [[ -n "$module" ]] || continue

    atlas_module_load "$module"

    local enabled="No"

    if atlas_module_enabled "$module"; then
      enabled="Yes"
    fi

    echo "${ATLAS_MODULE_NAME:-$module}"
    echo "  ID:      $module"
    echo "  Version: ${ATLAS_MODULE_VERSION:-unknown}"
    echo "  Enabled: $enabled"
    echo
  done < <(atlas_module_list)
}

atlas_command_module_list() {
  atlas_print_header
  atlas_section "Atlas Module List"

  local module

  while IFS= read -r module; do
    [[ -n "$module" ]] || continue

    atlas_module_load "$module"

    local enabled="false"

    if atlas_module_enabled "$module"; then
      enabled="true"
    fi

    printf '%-16s %-8s %s\n' \
      "$module" \
      "$enabled" \
      "${ATLAS_MODULE_NAME:-$module}"
  done < <(atlas_module_list)
}

atlas_command_module_status() {
  local module="${1:-}"

  if [[ -z "$module" ]]; then
    echo "Usage: atlas module status <module>"
    return 1
  fi

  if ! atlas_module_exists "$module"; then
    echo "Unknown module: $module"
    return 1
  fi

  atlas_module_load "$module"

  local module_dir="$ATLAS_PROJECT_DIR/modules/$module"
  local compose_file="${ATLAS_MODULE_COMPOSE_FILE:-docker-compose.yml}"
  local enabled="false"

  if atlas_module_enabled "$module"; then
    enabled="true"
  fi

  atlas_print_header
  echo "${ATLAS_MODULE_NAME:-$module}"
  echo
  echo "ID:           $module"
  echo "Version:      ${ATLAS_MODULE_VERSION:-unknown}"
  echo "Description:  ${ATLAS_MODULE_DESCRIPTION:-Not provided}"
  echo "Enabled:      $enabled"
  echo "Compose File: $compose_file"

  if [[ -f "$module_dir/$compose_file" ]]; then
    echo "Compose:      present"
  else
    echo "Compose:      missing"
  fi

  if [[ -f "$module_dir/README.md" ]]; then
    echo "README:       present"
  else
    echo "README:       missing"
  fi

  if [[ -x "$module_dir/scripts/verify.sh" ]]; then
    echo "Verify:       present"
  else
    echo "Verify:       missing"
  fi
}

atlas_command_module_run_script() {
  local module="${1:-}"
  local script_name="${2:-}"

  if [[ -z "$module" || -z "$script_name" ]]; then
    echo "Usage: atlas module <command> <module>"
    return 1
  fi

  if ! atlas_module_exists "$module"; then
    echo "Unknown module: $module"
    return 1
  fi

  local script_path="$ATLAS_PROJECT_DIR/modules/$module/scripts/$script_name.sh"

  if [[ ! -x "$script_path" ]]; then
    echo "Module command unavailable: $module $script_name"
    echo "Missing executable: $script_path"
    return 1
  fi

  atlas_print_header
  "$script_path"
}

atlas_command_module_enable() {
  local module="${1:-}"

  atlas_module_set_enabled "$module" true

  echo "$module module enabled."
  echo
  echo "No containers were started."
}

atlas_command_module_disable() {
  local module="${1:-}"

  atlas_module_set_enabled "$module" false

  echo "$module module disabled."
  echo
  echo "No containers were stopped."
}

atlas_command_module() {
  local subcommand="${1:-list}"
  local module_name="${2:-}"

  case "$subcommand" in
    list)
      atlas_command_module_list
      ;;

    status)
      atlas_command_module_status "$module_name"
      ;;

    verify)
      atlas_command_module_run_script "$module_name" "verify"
      ;;

    doctor)
      if ! atlas_module_exists "$module_name"; then
        echo "Unknown module: $module_name"
        return 1
      fi

      atlas_print_header
      echo "Module Doctor"
      echo
      echo "Module:  $module_name"
      echo "Enabled: $(atlas_module_enabled "$module_name" && echo true || echo false)"
      echo

      "$ATLAS_PROJECT_DIR/modules/$module_name/scripts/verify.sh"
      ;;

    install)
      atlas_command_module_run_script "$module_name" "install"
      ;;

    uninstall)
      atlas_command_module_run_script "$module_name" "uninstall"
      ;;

    enable)
      atlas_print_header
      atlas_command_module_enable "$module_name"
      ;;

    disable)
      atlas_print_header
      atlas_command_module_disable "$module_name"
      ;;

    update)
      atlas_command_module_run_script "$module_name" "update"
      ;;

    create)
      local new_module_id="${2:-}"
      local new_module_name="${3:-}"
      local new_module_description="${4:-}"

      atlas_print_header

      "$ATLAS_PROJECT_DIR/scripts/atlas-module-create.sh" \
        "$new_module_id" \
        "$new_module_name" \
        "$new_module_description"
      ;;

    *)
      echo "Usage:"
      echo "  atlas module list"
      echo "  atlas module status <module>"
      echo "  atlas module verify <module>"
      echo "  atlas module doctor <module>"
      echo "  atlas module install <module>"
      echo "  atlas module uninstall <module>"
      echo "  atlas module enable <module>"
      echo "  atlas module disable <module>"
      echo "  atlas module update <module>"
      echo "  atlas module create <name>"
      return 1
      ;;
  esac
}
