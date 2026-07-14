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
  local show_header="${2:-true}"

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

  if [[ "$show_header" == "true" ]]; then
    atlas_print_header
  fi

  echo "${ATLAS_MODULE_NAME:-$module}"
  echo
  echo "ID:           $module"
  echo "Version:      ${ATLAS_MODULE_VERSION:-unknown}"
  echo "Description:  ${ATLAS_MODULE_DESCRIPTION:-Not provided}"
  echo "Enabled:      $enabled"
  echo "Compose File: $compose_file"
  echo "Commands:     ${ATLAS_MODULE_DEPENDS_COMMANDS:-none}"
  echo "Services:     ${ATLAS_MODULE_DEPENDS_SERVICES:-none}"
  echo "Modules:      ${ATLAS_MODULE_DEPENDS_MODULES:-none}"
  echo "Owns:         ${ATLAS_MODULE_SERVICES:-none}"
  echo "Health URL:   ${ATLAS_MODULE_HEALTHCHECK_URL:-none}"

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

atlas_command_module_services() {
  local module="${1:-}"
  local show_header="${2:-true}"

  if ! atlas_module_exists "$module"; then
    echo "Unknown module: $module"
    return 1
  fi

  atlas_module_load "$module"

  if [[ "$show_header" == "true" ]]; then
    atlas_print_header
  fi

  atlas_section "Module Services"

  local services="${ATLAS_MODULE_SERVICES:-}"

  if [[ -z "$services" ]]; then
    echo "No services declared."
    return 0
  fi

  local service
  for service in $services; do
    local running="false"
    local health="n/a"

    if docker inspect \
      --format '{{.State.Running}}' \
      "$service" 2>/dev/null | grep -qx true; then
      running="true"
    fi

    health="$(
      docker inspect \
        --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' \
        "$service" 2>/dev/null || echo "missing"
    )"

    echo "$service"
    echo "  Running: $running"
    echo "  Health:  $health"
    echo
  done
}

atlas_command_module_health() {
  local module="${1:-}"
  local show_header="${2:-true}"

  if ! atlas_module_exists "$module"; then
    echo "Unknown module: $module"
    return 1
  fi

  atlas_module_load "$module"

  if [[ "$show_header" == "true" ]]; then
    atlas_print_header
  fi
  atlas_section "Module Health"

  local failed=0
  local services="${ATLAS_MODULE_SERVICES:-}"
  local health_url="${ATLAS_MODULE_HEALTHCHECK_URL:-}"

  if [[ -n "$services" ]]; then
    local service

    for service in $services; do
      if docker inspect \
        --format '{{.State.Running}}' \
        "$service" 2>/dev/null | grep -qx true; then
        atlas_ok "Service running: $service"
      else
        atlas_fail "Service unavailable: $service"
        failed=1
      fi
    done
  fi

  if [[ -n "$health_url" ]]; then
    if curl -fsS "$health_url" >/dev/null 2>&1; then
      atlas_ok "Health endpoint reachable: $health_url"
    else
      atlas_fail "Health endpoint unavailable: $health_url"
      failed=1
    fi
  fi

  if [[ -z "$services" && -z "$health_url" ]]; then
    atlas_warn "No runtime health checks declared"
  fi

  echo

  if [[ "$failed" -eq 0 ]]; then
    atlas_ok "Module health check passed"
  else
    atlas_fail "Module health check failed"
    return 1
  fi
}

atlas_command_module_info() {
  local module="${1:-}"

  if ! atlas_module_exists "$module"; then
    echo "Unknown module: $module"
    return 1
  fi

  atlas_module_load "$module"

  atlas_print_header
  atlas_section "Module Information"

  atlas_command_module_status "$module" false

  echo
  atlas_module_check_dependencies "$module"

  echo
  atlas_command_module_services "$module" false

  echo
  atlas_command_module_health "$module" false

  echo
  atlas_module_event_contract "$module"

}

atlas_command_module_usage() {
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
  echo "  atlas module dependencies <module>"
  echo "  atlas module services <module>"
  echo "  atlas module health <module>"
  echo "  atlas module validate <module>"
  echo "  atlas module permissions <module>"
  echo "  atlas module events <module>"
  echo "  atlas module publish <module> <event> [payload]"
  echo "  atlas module reconcile <module>"
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
      atlas_print_header

      local failed=0

      atlas_module_validate_configuration "$module_name" || failed=1

      echo

      atlas_module_check_dependencies "$module_name" || failed=1

      echo

      atlas_command_module_run_script "$module_name" "verify" || failed=1

      if [[ "$failed" -ne 0 ]]; then
        return 1
      fi
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

      local failed=0

      atlas_module_validate_configuration "$module_name" || failed=1

      echo

      atlas_module_check_dependencies "$module_name" || failed=1

      echo

      "$ATLAS_PROJECT_DIR/modules/$module_name/scripts/verify.sh" || failed=1

      if [[ "$failed" -ne 0 ]]; then
        return 1
      fi
      ;;

    install)
      atlas_print_header

      local failed=0

      atlas_module_validate_install_configuration "$module_name" || failed=1

      echo

      atlas_module_check_dependencies "$module_name" || failed=1

      if [[ "$failed" -ne 0 ]]; then
        return 1
      fi

      echo

      atlas_command_module_run_script "$module_name" "install" || return 1

      echo

      atlas_module_validate_configuration "$module_name" || return 1

      echo

      atlas_module_reconcile_event_subscriber "$module_name"
      ;;

    uninstall)
      atlas_command_module_run_script "$module_name" "uninstall"
      ;;

    enable)
      atlas_print_header

      atlas_command_module_enable "$module_name"

      echo

      atlas_module_reconcile_event_subscriber "$module_name"
      ;;

    disable)
      atlas_print_header
      atlas_command_module_disable "$module_name"
      ;;

    update)
      atlas_print_header

      local failed=0

      atlas_module_validate_configuration "$module_name" || failed=1

      echo

      atlas_module_check_dependencies "$module_name" || failed=1

      if [[ "$failed" -ne 0 ]]; then
        return 1
      fi

      echo

      atlas_module_reconcile_event_subscriber "$module_name" || return 1

      echo

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

    dependencies)
      atlas_print_header
      atlas_module_check_dependencies "$module_name"
      ;;

    services)
      atlas_command_module_services "$module_name"
      ;;

    health)
      atlas_command_module_health "$module_name"
      ;;

    info)
        atlas_command_module_info "$module_name"
        ;;

    validate)
      atlas_print_header
      atlas_module_validate_configuration "$module_name"
      ;;

    permissions)
      if ! atlas_module_exists "$module_name"; then
        echo "Unknown module: $module_name"
        return 1
      fi

      atlas_module_load "$module_name"

      atlas_print_header
      atlas_module_validate_permissions
      ;;

    events)
      atlas_print_header
      atlas_module_event_contract "$module_name"
      ;;

    publish)
      local event_name="${3:-}"
      local event_payload="${4:-}"

      atlas_print_header

      atlas_module_publish_event \
        "$module_name" \
        "$event_name" \
        "$event_payload"
      ;;

    reconcile)
      atlas_print_header
      atlas_module_reconcile_event_subscriber "$module_name"
      ;;

    sports)
      local sports_subcommand="${2:-subscriptions}"

      python3 \
        "$ATLAS_PROJECT_DIR/modules/sports/src/sports_cli.py" \
        "$sports_subcommand" \
        "${@:3}"
      ;;

    *)
      atlas_command_module_usage
      return 1
      ;;
  esac
}
