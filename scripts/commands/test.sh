#!/usr/bin/env bash

atlas_test_compile() {
  python3 -m compileall -q atlas modules/sports/src tests
}

atlas_test_core() {
  echo "Core Tests"
  echo "----------"
  python3 -m unittest discover -s tests -p 'test_*.py' -v
}

atlas_test_sports() {
  local runner="$ATLAS_PROJECT_DIR/modules/sports/tests/run_tests.py"

  if [[ ! -f "$runner" ]]; then
    echo "Sports test runner not found: $runner" >&2
    return 1
  fi

  echo "Sports Integration Tests"
  echo "------------------------"
  python3 "$runner"
}

atlas_command_test() {
  local scope="${1:-all}"

  atlas_print_header

  case "$scope" in
    all)
      atlas_test_compile
      atlas_test_core
      atlas_test_sports
      ;;
    core)
      atlas_test_compile
      atlas_test_core
      ;;
    sports)
      atlas_test_compile
      atlas_test_sports
      ;;
    *)
      echo "Usage: atlas test [all|core|sports]" >&2
      return 1
      ;;
  esac

  echo
  echo "Atlas test scope '$scope': PASS"
}
