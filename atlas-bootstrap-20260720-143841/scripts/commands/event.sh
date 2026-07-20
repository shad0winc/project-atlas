#!/usr/bin/env bash

atlas_command_event() {
  local action="${1:-}"
  shift || true

  case "$action" in
    publish)
      local event="${1:-}"
      local payload="${2:-}"
      local source="${3:-atlas}"

      if [[ -z "$payload" ]]; then
        payload='{}'
      fi

      atlas_print_header
      atlas_event_publish "$event" "$payload" "$source"
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

    subscriber)
      local subscriber_action="${1:-}"
      local subscriber_name="${2:-}"

      case "$subscriber_action" in
        register)
          atlas_print_header
          atlas_event_subscriber_register "$subscriber_name"
          ;;

        list)
          atlas_print_header
          atlas_section "Event Subscribers"
          atlas_event_subscriber_list
          ;;

        pending)
          atlas_print_header
          atlas_section "Pending Events"
          atlas_event_subscriber_pending "$subscriber_name"
          ;;

        consume)
          atlas_print_header
          atlas_section "Consumed Events"
          atlas_event_subscriber_consume "$subscriber_name"
          ;;

        filter)
          atlas_print_header
          atlas_event_subscriber_filter \
            "$subscriber_name" \
            "${3:-*}"
          ;;

        info)
          atlas_print_header
          atlas_section "Subscriber Information"
          atlas_event_subscriber_info "$subscriber_name"
          ;;

        reset)
          atlas_print_header
          atlas_event_subscriber_reset "$subscriber_name"
          ;;

        seek)
          atlas_print_header
          atlas_event_subscriber_seek \
            "$subscriber_name" \
            "${3:-}"
          ;;

        unregister)
          atlas_print_header
          atlas_event_subscriber_unregister "$subscriber_name"
          ;;

        *)
          echo "Usage:"
          echo "  atlas event subscriber register <name>"
          echo "  atlas event subscriber list"
          echo "  atlas event subscriber pending <name>"
          echo "  atlas event subscriber consume <name>"
          echo "  atlas event subscriber register <name>"
          echo "  atlas event subscriber list"
          echo "  atlas event subscriber pending <name>"
          echo "  atlas event subscriber consume <name>"
          echo "  atlas event subscriber filter <name> <pattern>"
          echo "  atlas event subscriber info <name>"
          echo "  atlas event subscriber reset <name>"
          echo "  atlas event subscriber seek <name> <cursor>"
          echo "  atlas event subscriber unregister <name>"
          return 1
          ;;
      esac
      ;;

    *)
      echo "  atlas event publish <event> [payload] [source]"
      echo "  atlas event publish <event> [payload]"
      echo "  atlas event list"
      echo "  atlas event tail"
      return 1
      ;;
  esac
}
