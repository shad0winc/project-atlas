#!/usr/bin/env bash

atlas_command_status() {
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
}
