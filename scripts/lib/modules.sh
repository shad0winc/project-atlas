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

atlas_module_validate_files() {
    local module="$1"
    local module_dir="$ATLAS_PROJECT_DIR/modules/$module"
    local files="${ATLAS_MODULE_REQUIRED_FILES:-}"
    local file
    local failed=0

    [[ -n "$files" ]] || return 0

    while IFS= read -r file; do
        [[ -n "$file" ]] || continue

        if [[ -f "$module_dir/$file" ]]; then
            atlas_ok "Required file: $file"
        else
            atlas_fail "Required file missing: $file"
            failed=1
        fi
    done < <(printf '%s\n' "$files" | tr '|' '\n')

    return "$failed"
}

atlas_module_validate_directories() {
    local directories="${ATLAS_MODULE_REQUIRED_DIRECTORIES:-}"
    local directory
    local failed=0

    [[ -n "$directories" ]] || return 0

    while IFS= read -r directory; do
        [[ -n "$directory" ]] || continue

        if [[ -d "$directory" ]]; then
            atlas_ok "Required directory: $directory"
        else
            atlas_fail "Required directory missing: $directory"
            failed=1
        fi
    done < <(printf '%s\n' "$directories" | tr '|' '\n')

    return "$failed"
}

atlas_module_validate_environment() {
    local variables="${ATLAS_MODULE_REQUIRED_ENV:-}"
    local variable
    local failed=0

    [[ -n "$variables" ]] || return 0

    while IFS= read -r variable; do
        [[ -n "$variable" ]] || continue

        if [[ -n "${!variable:-}" ]]; then
            atlas_ok "Required environment variable: $variable"
        else
            atlas_fail "Required environment variable missing: $variable"
            failed=1
        fi
    done < <(printf '%s\n' "$variables" | tr '|' '\n')

    return "$failed"
}

atlas_module_validate_configuration() {
    local module="${1:-}"

    if ! atlas_module_exists "$module"; then
        echo "Unknown module: $module"
        return 1
    fi

    atlas_module_load "$module"

    atlas_section "Module Configuration"

    local failed=0

    atlas_module_validate_files "$module" || failed=1
    atlas_module_validate_directories || failed=1
    atlas_module_validate_writable_directories || failed=1

    echo

    atlas_module_validate_permissions || failed=1
    atlas_module_validate_environment || failed=1

    echo

    if [[ "$failed" -eq 0 ]]; then
        atlas_ok "Module configuration valid"
        return 0
    fi

    atlas_fail "Module configuration invalid"
    return 1
}

atlas_module_validate_writable_directories() {
    local directories="${ATLAS_MODULE_WRITABLE_DIRECTORIES:-}"
    local directory
    local failed=0

    [[ -n "$directories" ]] || return 0

    while IFS= read -r directory; do
        [[ -n "$directory" ]] || continue

        local test_file="$directory/.atlas-write-test"

        if touch "$test_file" >/dev/null 2>&1; then
            rm -f "$test_file"
            atlas_ok "Writable directory: $directory"
        else
            atlas_fail "Directory not writable: $directory"
            failed=1
        fi
    done < <(printf '%s\n' "$directories" | tr '|' '\n')

    return "$failed"
}

atlas_module_validate_install_configuration() {
    local module="${1:-}"

    if ! atlas_module_exists "$module"; then
        echo "Unknown module: $module"
        return 1
    fi

    atlas_module_load "$module"

    atlas_section "Install Configuration"

    local failed=0

    atlas_module_validate_files "$module" || failed=1
    atlas_module_validate_environment || failed=1

    echo

    if [[ "$failed" -eq 0 ]]; then
        atlas_ok "Install configuration valid"
        return 0
    fi

    atlas_fail "Install configuration invalid"
    return 1
}

atlas_module_validate_permissions() {
    local directories="${ATLAS_MODULE_WRITABLE_DIRECTORIES:-}"
    local expected_mode="${ATLAS_MODULE_DIRECTORY_MODE:-}"
    local expected_uid="${ATLAS_MODULE_EXPECTED_UID:-}"
    local expected_gid="${ATLAS_MODULE_EXPECTED_GID:-}"

    local directory
    local failed=0

    [[ -n "$directories" ]] || return 0

    atlas_section "Module Permissions"

    while IFS= read -r directory; do
        [[ -n "$directory" ]] || continue

        if [[ ! -d "$directory" ]]; then
            atlas_fail "Directory missing: $directory"
            failed=1
            continue
        fi

        local actual_mode
        local actual_uid
        local actual_gid

        actual_mode="$(stat -c '%a' "$directory")"
        actual_uid="$(stat -c '%u' "$directory")"
        actual_gid="$(stat -c '%g' "$directory")"

        if [[ -n "$expected_mode" ]]; then
            if [[ "$actual_mode" == "$expected_mode" ]]; then
                atlas_ok "Directory mode: $directory ($actual_mode)"
            else
                atlas_fail \
                    "Directory mode: $directory ($actual_mode, expected $expected_mode)"
                failed=1
            fi
        fi

        if [[ -n "$expected_uid" ]]; then
            if [[ "$actual_uid" == "$expected_uid" ]]; then
                atlas_ok "Directory UID: $directory ($actual_uid)"
            else
                atlas_fail \
                    "Directory UID: $directory ($actual_uid, expected $expected_uid)"
                failed=1
            fi
        fi

        if [[ -n "$expected_gid" ]]; then
            if [[ "$actual_gid" == "$expected_gid" ]]; then
                atlas_ok "Directory GID: $directory ($actual_gid)"
            else
                atlas_fail \
                    "Directory GID: $directory ($actual_gid, expected $expected_gid)"
                failed=1
            fi
        fi
    done < <(printf '%s\n' "$directories" | tr '|' '\n')

    echo

    if [[ "$failed" -eq 0 ]]; then
        atlas_ok "Module permission contract satisfied"
        return 0
    fi

    atlas_fail "Module permission contract violated"
    return 1
}

atlas_module_event_contract() {
    local module="${1:-}"

    if ! atlas_module_exists "$module"; then
        atlas_fail "Unknown module: $module"
        return 1
    fi

    atlas_module_load "$module"

    local publishes="${ATLAS_MODULE_EVENTS_PUBLISHES:-}"
    local subscribes="${ATLAS_MODULE_EVENTS_SUBSCRIBES:-}"

    atlas_section "Module Event Contract"

    echo "Publishes:"

    if [[ -z "$publishes" ]]; then
        echo "  none"
    else
        local event=""

        while IFS= read -r event; do
            [[ -n "$event" ]] || continue
            echo "  $event"
        done < <(printf '%s\n' "$publishes" | tr '|' '\n')
    fi

    echo
    echo "Subscribes:"

    if [[ -z "$subscribes" ]]; then
        echo "  none"
    else
        local pattern=""

        while IFS= read -r pattern; do
            [[ -n "$pattern" ]] || continue
            echo "  $pattern"
        done < <(printf '%s\n' "$subscribes" | tr '|' '\n')
    fi
}
