#!/usr/bin/env bash

atlas_command_event() {
  local action="${1:-}"
  shift || true

  case "$action" in
    publish)
      local event="${1:-}"
      local payload="${2:-}"

      if [[ -z "$payload" ]]; then
        payload='{}'
      fi

      atlas_print_header
      atlas_event_publish "$event" "$payload"
      ;;

    list)
      atlas_print_header
      atlas_section "Atlas Events"
      atlas_event_list
      ;;

    tail)
      atlas_print_header
      atlas_section "Recent Atlas Events"
      atlas_event_tail
      ;;

    *)
      echo "Usage:"
      echo "  atlas event publish <event> [payload]"
      echo "  atlas event list"
      echo "  atlas event tail"
      return 1
      ;;
  esac
}
