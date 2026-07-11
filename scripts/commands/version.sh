#!/usr/bin/env bash

atlas_command_version() {
  atlas_print_header

  echo -n "Version: "
  cat "$ATLAS_PROJECT_DIR/VERSION" 2>/dev/null || echo "unknown"

  echo "Branch:  $(git -C "$ATLAS_PROJECT_DIR" branch --show-current 2>/dev/null || echo unknown)"
}
