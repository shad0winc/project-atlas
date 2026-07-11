#!/usr/bin/env bash

atlas_print_header() {
  echo "Project Atlas"
  echo "Simplicity Meets Ingenuity"
  echo
}

atlas_ok() {
  echo "OK   $*"
}

atlas_warn() {
  echo "WARN $*"
}

atlas_fail() {
  echo "FAIL $*"
}

atlas_section() {
  local title="$1"

  echo "$title"
  printf '%*s\n' "${#title}" '' | tr ' ' '-'
}
