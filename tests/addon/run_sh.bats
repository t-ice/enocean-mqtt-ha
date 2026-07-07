#!/usr/bin/env bats
# Static checks on addon/run.sh. Run with: bats tests/addon/  (CI installs bats-core).
# Behavioural config-generation is covered indirectly by the daemon tests; here we guard the
# shell contract: valid syntax, the single `connection` option wired to enocean_port, and MQTT
# auto-discovery from the service.

@test "run.sh is syntactically valid bash" {
  run bash -n addon/run.sh
  [ "$status" -eq 0 ]
}

@test "device/tcp options resolve to enocean_port (tcp wins)" {
  grep -q "bashio::config 'tcp'" addon/run.sh
  grep -q "bashio::config 'device'" addon/run.sh
  grep -q 'enocean_port          = ${CONNECTION}' addon/run.sh
}

@test "lists the available serial devices (local setup only)" {
  # For a no-TCP (local) setup, run.sh enumerates the mapped tty devices and logs them.
  grep -q 'GET /hardware/info' addon/run.sh
  grep -q 'Available serial devices' addon/run.sh
}

@test "validates a configured device exists" {
  # A configured 'device' path that isn't present fails fast instead of a cryptic serial error.
  grep -qF '! -e "${CONNECTION}"' addon/run.sh
  grep -q 'Configured device' addon/run.sh
  grep -q "bashio::config.has_value 'device'" addon/run.sh
}

@test "MQTT falls back to the Supervisor mqtt service" {
  grep -q "bashio::services 'mqtt'" addon/run.sh
}

@test "device list is passed to the daemon as an argument" {
  grep -q 'DEVICE_ARGS=("${DEVICE_FILE}")' addon/run.sh
  grep -q '"${DEVICE_ARGS\[@\]}"' addon/run.sh
}

@test "daemon is exec'd directly (async core self-heals; no restart loop)" {
  # The asyncio daemon reconnects internally, so run.sh no longer loops or probes /dev/tcp.
  ! grep -q 'while true; do' addon/run.sh
  ! grep -q '/dev/tcp/' addon/run.sh
  grep -q 'exec enocean2mqtt --log-level' addon/run.sh
}
