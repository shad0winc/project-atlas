#!/usr/bin/env bash

atlas_command_help() {
  atlas_print_header

  cat <<'HELP'
Usage:
  atlas <command> [options]

Core Commands
-------------
  atlas help
  atlas version
  atlas status
  atlas services [--json]
  atlas service [help|list|show|runtime|health|summary|graph]
  atlas service list [--json]
  atlas service show <identifier> [--json]
  atlas service runtime <identifier> [--json]
  atlas service health [--json]
  atlas service health <identifier> [--json]
  atlas service summary [--json]
  atlas service graph [--json]
  atlas service doctor [--json]
  atlas service startup-policy [--json]
  atlas service updates [--json]
  atlas service history [<identifier>] [--json]
  atlas urls
  atlas git
  atlas test [all|core|sports]
  atlas health [json|--compact]
  atlas scheduler list
  atlas scheduler inspect <task>
  atlas scheduler register <task> <interval-seconds> <callback> [options]
  atlas scheduler remove <task>
  atlas scheduler run [task] [--due-only]
  atlas scheduler dry-run
  atlas scheduler history [--limit N]
  atlas scheduler sync [module]
  atlas users
  atlas user list [--json]
  atlas user show <username-or-id>
  atlas user create <username> [options]
  atlas user update <username-or-id> [options]
  atlas user enable <username-or-id>
  atlas user disable <username-or-id>
  atlas user link-jellyfin <username-or-id> <jellyfin-user-id>
  atlas user verify [username-or-id]
  atlas invite create [--email EMAIL] [--role ROLE] [--days N]
  atlas invite list [--status STATUS] [--json]
  atlas invite show <invite-id>
  atlas invite revoke <invite-id> [--revoked-by USER]
  atlas invite verify [--token TOKEN]
  atlas invite cleanup
  atlas favorite add --user USER --provider PROVIDER --item-id ID --type TYPE [options]
  atlas favorite remove (--favorite-id ID | --item-id ID --user USER --provider PROVIDER)
  atlas favorite list [--user USER] [--provider PROVIDER] [--type TYPE] [--json]
  atlas favorite show <favorite-id>
  atlas favorite verify

Modules
-------
  atlas modules
  atlas module list
  atlas module status <module>
  atlas module verify <module>
  atlas module doctor <module>
  atlas module install <module>
  atlas module uninstall <module>
  atlas module enable <module>
  atlas module disable <module>
  atlas module update <module>
  atlas module create <name>
  atlas module dependencies <module>
  atlas module services <module>
  atlas module health <module>
  atlas module info <module>
  atlas module validate <module>
  atlas module permissions <module>
  atlas module events <module>
  atlas module commands <module>
  atlas module exec <module> <command> [arguments...]

Maintenance
-----------
  atlas verify
  atlas doctor
  atlas update <core|ingress|all> --migration none
  atlas deployment status
  atlas deployment baseline
  atlas deployment rollback <deployment-id>
  atlas maintenance status
  atlas maintenance enable
  atlas maintenance disable
  atlas backup
  atlas restore inspect <archive>
  atlas restore verify <archive>
  atlas restore stage <archive>
  atlas restart
  atlas logs <container>

Intelligence
------------
  atlas ari collect
  atlas ari report
  atlas ari health-report
  atlas ari latest [--json]
  atlas ari history [--json]
  atlas ari growth [--json]
  atlas ari forecast [--json]
  atlas discovery [help|indexers|categories|applications|health|report]
  atlas operations [help|report|save|latest|history|compare]
  atlas operations report [--json] [--report-id REPORT_ID]
  atlas operations save [--json] [--report-id REPORT_ID]
  atlas operations latest [--json]
  atlas operations history [--limit LIMIT] [--json]
  atlas operations compare [--json] [--include-unchanged]
  atlas retention evaluate <provider> <item-id> [--json]
  atlas cleanup evaluate <provider> <item-id> [--json]
  atlas cleanup scan <provider> [--page-size N] [--json]
  atlas cleanup execute <provider> [--page-size N] [--json]
  atlas cleanup run <provider> [--page-size N] [--audit-path PATH] [--json]
  atlas cleanup history [--audit-path PATH] [--last N] [--provider PROVIDER] [--failures | --without-failures] [--json]

Runtime
-------
  atlas event publish <event> [payload] [source]
  atlas event list
  atlas event tail
  atlas event subscriber register <name>
  atlas event subscriber list
  atlas event subscriber pending <name>
  atlas event subscriber consume <name>
  atlas event subscriber filter <name> <pattern>
  atlas event subscriber info <name>
  atlas event subscriber reset <name>
  atlas event subscriber seek <name> <cursor>
  atlas event subscriber unregister <name>

HELP
}
