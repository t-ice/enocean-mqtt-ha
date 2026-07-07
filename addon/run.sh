#!/usr/bin/with-contenv bashio
# shellcheck shell=bash
# EnOcean-MQTT-Eltako add-on entry point.
#
#   * Transceiver endpoint from two options: `device` (a local serial /dev path, e.g. /dev/ttyUSB0,
#     copied from the startup log) or `tcp` (a remote ser2net host:port). TCP wins if both are set; the
#     daemon connects to serial or TCP natively.
#   * MQTT broker is auto-discovered from the `mqtt` service unless overridden.
#   * The HA-version-dependent entity-naming quirk is computed here, not a user option.

set -o errexit
set -o nounset

CONFIG_FILE="/data/enocean2mqtt.conf"
DB_FILE="/data/enocean2mqtt_db.json"
DEVICE_FILE="$(bashio::config 'device_file')"
LOG_FILE="$(bashio::config 'log_file' '/config/enocean2mqtt/enocean2mqtt.log')"
LOG_LEVEL="$(bashio::config 'log_level' 'info')"

bashio::config.require 'device_file'

# List the serial (tty) devices the Supervisor has mapped into the container — the same set offered
# for the `device` option. Prefers the stable by-id path. Best-effort: falls back to scanning /dev,
# and never fails the script (guarded for `set -o errexit`).
list_serial_devices() {
  local out=""
  out="$(bashio::api.supervisor GET /hardware/info 2>/dev/null \
        | jq -r '(.data.devices // .devices)[]? | select(.subsystem == "tty") | .by_id // .dev_path' \
        2>/dev/null || true)"
  if bashio::var.is_empty "${out}"; then
    shopt -s nullglob
    local -a nodes=(/dev/serial/by-id/* /dev/ttyUSB* /dev/ttyACM* /dev/ttyAMA*)
    shopt -u nullglob
    [ "${#nodes[@]}" -gt 0 ] && printf '%s\n' "${nodes[@]}"
  else
    echo "${out}"
  fi
}

# Transceiver endpoint from two native options: `device` (a local serial device path) or `tcp` (a
# remote ser2net endpoint as host:port). The daemon auto-detects serial vs TCP from the value. TCP
# wins if both are set, so a ser2net endpoint isn't blocked by a leftover device value. The available
# serial devices are listed (and a configured `device` is validated) only for a local setup — when no
# TCP endpoint is configured.
CONNECTION=""
if bashio::config.has_value 'tcp'; then
  CONNECTION="$(bashio::config 'tcp')"
  if bashio::config.has_value 'device'; then
    bashio::log.warning "Both a TCP endpoint and a device are set; using the TCP endpoint '${CONNECTION}'."
  fi
else
  AVAILABLE="$(list_serial_devices)"
  if bashio::var.is_empty "${AVAILABLE}"; then
    bashio::log.info "Available serial devices: none found — plug an EnOcean USB stick into the Home Assistant host, or set the TCP (ser2net) endpoint for a stick on a Raspberry Pi."
  else
    bashio::log.info "Available serial devices:"
    while IFS= read -r dev; do
      [ -n "${dev}" ] && bashio::log.info "  - ${dev}"
    done <<< "${AVAILABLE}"
  fi
  if bashio::config.has_value 'device'; then
    CONNECTION="$(bashio::config 'device')"
    if [ ! -e "${CONNECTION}" ]; then
      bashio::log.error "Configured device '${CONNECTION}' does not exist in the add-on."
      bashio::log.error "Set 'device' to one of the paths listed above, or set the TCP (ser2net) endpoint instead."
      bashio::exit.nok "Serial device '${CONNECTION}' not found."
    fi
  fi
fi
if bashio::var.is_empty "${CONNECTION}"; then
  bashio::exit.nok "No transceiver configured: set a Device (see the list above), or set the ser2net TCP endpoint (host:port)."
fi

# ---------------------------------------------------------------------------
# MQTT connection: prefer explicit config, else the Supervisor `mqtt` service.
# ---------------------------------------------------------------------------
MQTT_HOST="" MQTT_PORT="" MQTT_USER="" MQTT_PSWD=""
if bashio::config.has_value 'mqtt_host'; then
  MQTT_HOST="$(bashio::config 'mqtt_host')"
  MQTT_PORT="$(bashio::config 'mqtt_port' '1883')"
  MQTT_USER="$(bashio::config 'mqtt_user' '')"
  MQTT_PSWD="$(bashio::config 'mqtt_pwd' '')"
elif bashio::var.has_value "$(bashio::services 'mqtt')"; then
  bashio::log.info "Using MQTT broker from the Supervisor 'mqtt' service"
  MQTT_HOST="$(bashio::services 'mqtt' 'host')"
  MQTT_PORT="$(bashio::services 'mqtt' 'port')"
  MQTT_USER="$(bashio::services 'mqtt' 'username')"
  MQTT_PSWD="$(bashio::services 'mqtt' 'password')"
fi
if bashio::var.is_empty "${MQTT_HOST}"; then
  bashio::exit.nok "No MQTT broker configured and no 'mqtt' service available"
fi

# ---------------------------------------------------------------------------
# Entity-naming quirk: HA >= 2024.2 must NOT repeat the device name in entities.
# (Older releases behave the other way round.) Computed, not user-configurable.
# ---------------------------------------------------------------------------
USE_DEV_NAME_IN_ENTITY="False"
if bashio::var.has_value "$(bashio::core.version 2>/dev/null || true)"; then
  HA_VERSION="$(bashio::core.version)"
  YEAR="${HA_VERSION%%.*}"
  MONTH="$(echo "$HA_VERSION" | cut -d. -f2)"
  if [ "${YEAR:-0}" -lt 2024 ] || { [ "${YEAR:-0}" -eq 2024 ] && [ "${MONTH:-0}" -lt 2 ]; }; then
    USE_DEV_NAME_IN_ENTITY="True"
  fi
fi
bashio::log.info "use_dev_name_in_entity = ${USE_DEV_NAME_IN_ENTITY} (auto from HA ${HA_VERSION:-unknown})"

# ---------------------------------------------------------------------------
# Generate the daemon config (CONFIG section + the user's device list).
# ---------------------------------------------------------------------------
{
  echo "[CONFIG]"
  echo "enocean_port          = ${CONNECTION}"
  echo "send_interval_ms      = $(bashio::config 'send_interval_ms' '100')"
  echo "repeater              = $(bashio::config 'repeater' 'off')"
  bashio::config.has_value 'secure_psk' && echo "secure_psk            = $(bashio::config 'secure_psk')"
  echo "overlay               = HA"
  echo "db_file               = ${DB_FILE}"
  echo "ha_dev_name_in_entity = ${USE_DEV_NAME_IN_ENTITY}"
  echo "mqtt_discovery_prefix = homeassistant/"
  echo "mqtt_host             = ${MQTT_HOST}"
  echo "mqtt_port             = ${MQTT_PORT}"
  echo "mqtt_user             = ${MQTT_USER}"
  echo "mqtt_pwd              = ${MQTT_PSWD}"
  echo "mqtt_client_id        = enocean_gateway"
  echo "mqtt_keepalive        = 60"
  echo "mqtt_prefix           = enocean2mqtt/"
  # Optional MQTT TLS (written only when set; the daemon enables TLS when mqtt_ssl is true)
  bashio::config.has_value 'mqtt_ssl' && echo "mqtt_ssl              = $(bashio::config 'mqtt_ssl')"
  bashio::config.has_value 'mqtt_ssl_ca_certs' && echo "mqtt_ssl_ca_certs     = $(bashio::config 'mqtt_ssl_ca_certs')"
  bashio::config.has_value 'mqtt_ssl_certfile' && echo "mqtt_ssl_certfile     = $(bashio::config 'mqtt_ssl_certfile')"
  bashio::config.has_value 'mqtt_ssl_keyfile' && echo "mqtt_ssl_keyfile      = $(bashio::config 'mqtt_ssl_keyfile')"
  bashio::config.has_value 'mqtt_ssl_insecure' && echo "mqtt_ssl_insecure     = $(bashio::config 'mqtt_ssl_insecure')"
  echo ""
} > "${CONFIG_FILE}"
# The generated config holds the MQTT password in plaintext — keep it root-only.
chmod 600 "${CONFIG_FILE}"

# The device list is a devices.yaml, passed to the daemon as a separate config argument (it
# contributes sensors only).
DEVICE_ARGS=("${DEVICE_FILE}")

bashio::log.green "Starting EnOcean-MQTT-Eltako (connection: ${CONNECTION})"

# The daemon runs a single asyncio event loop that connects to the MQTT broker and the
# transceiver and self-heals connection drops (reconnect with exponential backoff), so run.sh
# needs no reachability probe or restart loop — a Raspberry Pi power-cycle or ser2net restart is
# recovered from inside the process. If the daemon ever exits, s6 restarts the service.
exec enocean2mqtt --log-level "${LOG_LEVEL}" --logfile "${LOG_FILE}" "${CONFIG_FILE}" "${DEVICE_ARGS[@]}"
