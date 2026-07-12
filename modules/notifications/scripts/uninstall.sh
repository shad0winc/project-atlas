#!/usr/bin/env bash
set -euo pipefail

module_id="notifications"

echo "$module_id module uninstall is intentionally conservative."
echo "No files, configuration, data, or containers were removed."
echo
echo "Manual cleanup locations:"
echo "  /mnt/storage/configs/$module_id"
echo "  /mnt/storage/$module_id"
