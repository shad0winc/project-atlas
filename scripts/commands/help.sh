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
  atlas services
  atlas urls
  atlas git

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

Maintenance
-----------
  atlas verify
  atlas doctor
  atlas update
  atlas backup
  atlas restart
  atlas logs <container>

Intelligence
------------
  atlas ari collect
  atlas ari report

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

HELP
}
