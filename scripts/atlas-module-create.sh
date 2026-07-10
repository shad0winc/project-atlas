#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/opt/project-atlas"
TEMPLATE_DIR="$PROJECT_DIR/modules/template"

usage() {
  echo "Usage:"
  echo "  atlas-module-create.sh <module-id> [module-name] [description]"
}

module_id="${1:-}"
module_name="${2:-}"
module_description="${3:-}"

if [[ -z "$module_id" ]]; then
  usage
  exit 1
fi

if [[ ! "$module_id" =~ ^[a-z][a-z0-9-]*$ ]]; then
  echo "Invalid module ID: $module_id"
  echo "Use lowercase letters, numbers, and hyphens."
  echo "The first character must be a letter."
  exit 1
fi

if [[ "$module_id" == "template" ]]; then
  echo "The module ID 'template' is reserved."
  exit 1
fi

module_dir="$PROJECT_DIR/modules/$module_id"

if [[ -e "$module_dir" ]]; then
  echo "Module already exists: $module_dir"
  exit 1
fi

if [[ ! -d "$TEMPLATE_DIR" ]]; then
  echo "Missing module template: $TEMPLATE_DIR"
  exit 1
fi

if [[ -z "$module_name" ]]; then
  module_name="$(
    printf '%s' "$module_id" |
      tr '-' ' ' |
      sed -E 's/(^| )[a-z]/\U&/g'
  )"
fi

if [[ -z "$module_description" ]]; then
  module_description="Optional Project Atlas $module_name module."
fi

echo "Creating Atlas module..."
echo
echo "ID:          $module_id"
echo "Name:        $module_name"
echo "Description: $module_description"
echo

cp -a "$TEMPLATE_DIR" "$module_dir"

while IFS= read -r -d '' file; do
  sed -i \
-e "s|__MODULE_ID__|$module_id|g" \
-e "s|__MODULE_NAME__|$module_name|g" \
-e "s|__MODULE_DESCRIPTION__|$module_description|g" \
    "$file"
done < <(
  find "$module_dir" \
    -type f \
    ! -name '*.png' \
    ! -name '*.jpg' \
    ! -name '*.jpeg' \
    ! -name '*.gif' \
    -print0
)

chmod +x "$module_dir/scripts/"*.sh

echo "Module scaffold created:"
echo "  $module_dir"
echo
echo "Next steps:"
echo "  1. Review modules/$module_id/module.conf"
echo "  2. Review modules/$module_id/docker-compose.yml"
echo "  3. Run modules/$module_id/scripts/install.sh"
echo "  4. Run modules/$module_id/scripts/verify.sh"
