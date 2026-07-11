#!/usr/bin/env bash

atlas_module_directory() {
    echo "$ATLAS_PROJECT_DIR/modules"
}

atlas_module_exists() {
    local module="$1"

    [[ "$module" != "template" ]] || return 1
    [[ -f "$(atlas_module_directory)/$module/module.conf" ]]
}

atlas_module_load() {
    local module="$1"

    local conf
    conf="$(atlas_module_directory)/$module/module.conf"

    if [[ ! -f "$conf" ]]; then
        return 1
    fi

    # shellcheck disable=SC1090
    source "$conf"
}

atlas_module_list() {
    local dir
    local module

    for dir in "$(atlas_module_directory)"/*; do
        [[ -d "$dir" ]] || continue
        [[ -f "$dir/module.conf" ]] || continue

        module="$(basename "$dir")"

        [[ "$module" == "template" ]] && continue

        echo "$module"
    done | sort
}

atlas_module_enabled() {
    local module="$1"
    local variable

    variable="$(atlas_module_state_variable "$module")"

    [[ "${!variable:-false}" == "true" ]]
}

atlas_module_state_variable() {
    local module="$1"
    local variable="ATLAS_MODULE_${module^^}_ENABLED"

    echo "${variable//-/_}"
}

atlas_module_set_enabled() {
    local module="$1"
    local value="$2"

    if ! atlas_module_exists "$module"; then
        echo "Unknown module: $module"
        return 1
    fi

    if [[ "$value" != "true" && "$value" != "false" ]]; then
        echo "Invalid module state: $value"
        return 1
    fi

    local variable
    variable="$(atlas_module_state_variable "$module")"

    local state_file="$ATLAS_MODULE_STATE_FILE"

    if [[ ! -f "$state_file" ]]; then
        mkdir -p "$(dirname "$state_file")"
        touch "$state_file"
    fi

    if grep -q "^${variable}=" "$state_file"; then
        sed -i "s/^${variable}=.*/${variable}=${value}/" "$state_file"
    else
        echo "${variable}=${value}" >> "$state_file"
    fi
}

atlas_module_check_commands() {
    local commands="${ATLAS_MODULE_DEPENDS_COMMANDS:-}"
    local command
    local failed=0

    for command in $commands; do
        if command -v "$command" >/dev/null 2>&1; then
            atlas_ok "Command dependency: $command"
        else
            atlas_fail "Command dependency missing: $command"
            failed=1
        fi
    done

    return "$failed"
}

atlas_module_check_services() {
    local services="${ATLAS_MODULE_DEPENDS_SERVICES:-}"
    local service
    local failed=0

    for service in $services; do
        if docker inspect \
            --format '{{.State.Running}}' \
            "$service" 2>/dev/null | grep -qx true; then
            atlas_ok "Service dependency: $service"
        else
            atlas_fail "Service dependency unavailable: $service"
            failed=1
        fi
    done

    return "$failed"
}

atlas_module_check_modules() {
    local modules="${ATLAS_MODULE_DEPENDS_MODULES:-}"
    local dependency
    local failed=0

    for dependency in $modules; do
        if ! atlas_module_exists "$dependency"; then
            atlas_fail "Module dependency missing: $dependency"
            failed=1
            continue
        fi

        if atlas_module_enabled "$dependency"; then
            atlas_ok "Module dependency: $dependency"
        else
            atlas_fail "Module dependency disabled: $dependency"
            failed=1
        fi
    done

    return "$failed"
}

atlas_module_check_dependencies() {
    local module="${1:-}"

    if ! atlas_module_exists "$module"; then
        echo "Unknown module: $module"
        return 1
    fi

    atlas_module_load "$module"

    atlas_section "Module Dependencies"

    local failed=0

    atlas_module_check_commands || failed=1
    atlas_module_check_services || failed=1
    atlas_module_check_modules || failed=1

    if [[ "$failed" -eq 0 ]]; then
        echo
        atlas_ok "All dependencies satisfied"
        return 0
    fi

    echo
    atlas_fail "One or more dependencies are unavailable"
    return 1
}
