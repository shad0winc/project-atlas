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
