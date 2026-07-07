#!/usr/bin/env bash
# Configure a Raspberry Pi (or similar Linux host) to expose the EnOcean USB stick as raw TCP :3000
# for the Home Assistant add-on. Manages the DISTRO ser2net service + its config — it does NOT add a
# second ser2net unit (two instances would fight over :3000 and the serial device).
#
# Robust across ser2net versions and Pi variants: it auto-detects the installed ser2net version
# (v4 YAML, e.g. Raspberry Pi OS Bookworm/Bullseye — or v3 .conf, e.g. Buster), the config path the
# service actually reads, and the stick's stable by-id device path. Idempotent and non-destructive:
# if something already serves :3000 it prints the current config and exits unless you pass --force.
# After writing it verifies ser2net came up on :3000 and rolls back the config on failure.
#
#   sudo ./install.sh                 # auto-detect the stick, write config, (re)start ser2net
#   sudo ./install.sh --device /dev/serial/by-id/usb-FTDI_...-if00-port0
#   sudo ./install.sh --device /dev/serial0     # EnOcean Pi GPIO hat (free the serial console first)
#   sudo ./install.sh --force         # overwrite an existing :3000 config
#        ./install.sh --check         # read-only: report what it detects, change nothing (no root)
#
# Afterwards set the add-on option  connection: <this-pi-ip-or-host>:3000
set -euo pipefail

PORT=3000
HERE="$(cd "$(dirname "$0")" && pwd)"
DEVICE=""
FORCE=0
CHECK=0

have() { command -v "$1" >/dev/null 2>&1; }
ts()   { date +%Y%m%d-%H%M%S; }

usage() {
  cat <<EOF
Usage: sudo $0 [--device PATH] [--force] [--check]
  --device PATH   serial device (default: auto-detect the /dev/serial/by-id path)
  --force         overwrite an existing :$PORT configuration
  --check         read-only: report what would be detected/used, change nothing
Afterwards set the add-on option  connection: <this-pi-ip-or-host>:$PORT
EOF
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --device) shift; DEVICE="${1:-}"; [[ -n "$DEVICE" ]] || { echo "--device needs a path" >&2; exit 2; }; shift ;;
    --force)  FORCE=1; shift ;;
    --check)  CHECK=1; shift ;;
    -h|--help) usage 0 ;;
    *) echo "Unknown argument: $1" >&2; usage 2 ;;
  esac
done

# ---------------------------------------------------------------------------
# Read-only detection helpers
# ---------------------------------------------------------------------------

# Echo the ser2net major version (e.g. "4" or "3"); empty if ser2net isn't installed.
ser2net_major() {
  local bin="" ver
  if have ser2net; then bin="ser2net"; elif [[ -x /usr/sbin/ser2net ]]; then bin="/usr/sbin/ser2net"; fi
  [[ -n "$bin" ]] || return 0
  ver="$("$bin" -v 2>&1 | head -1 || true)"
  sed -n 's/.*[Vv]ersion[^0-9]*\([0-9][0-9]*\).*/\1/p' <<<"$ver" | head -1
}

# Echo the config path ser2net actually reads: the service's ExecStart "-c <path>" if set, else the
# version default (v3 -> /etc/ser2net.conf, v4 -> /etc/ser2net.yaml).
config_path_for() {
  local major="$1" cfg="" line
  if have systemctl; then
    line="$(systemctl cat ser2net.service 2>/dev/null | grep -m1 '^ExecStart=' || true)"
    cfg="$(sed -n 's/.*-c[ =]\{1,\}\([^ ]\{1,\}\).*/\1/p' <<<"$line" | head -1)"
  fi
  if [[ -z "$cfg" ]]; then
    if [[ "$major" == "3" ]]; then cfg="/etc/ser2net.conf"; else cfg="/etc/ser2net.yaml"; fi
  fi
  echo "$cfg"
}

# 0 = :PORT in use, 1 = free, 2 = unknown (no ss/netstat available).
port_status() {
  if have ss; then
    ss -tlnH 2>/dev/null | grep -qE "[:.]${PORT}([[:space:]]|\$)" && return 0 || return 1
  fi
  if have netstat; then
    netstat -tln 2>/dev/null | grep -qE "[:.]${PORT}[[:space:]]" && return 0 || return 1
  fi
  return 2
}

# Resolve the transceiver into the global DEVICE. Return 0 on a single match, else 1 (prints why).
resolve_device() {
  if [[ -n "$DEVICE" ]]; then
    if [[ -e "$DEVICE" ]]; then echo "    device (from --device): $DEVICE"; return 0; fi
    echo "    --device $DEVICE does not exist" >&2; return 1
  fi
  local strong=() weak=() d uniq="" uart=""
  shopt -s nullglob
  for d in /dev/serial/by-id/*FTDI* /dev/serial/by-id/*[Ee][Nn][Oo][Cc][Ee][Aa][Nn]*; do strong+=("$d"); done
  for d in /dev/serial/by-id/*; do weak+=("$d"); done
  shopt -u nullglob
  # de-dup strong matches (by-id paths never contain spaces)
  for d in "${strong[@]:-}"; do
    [[ -n "$d" ]] || continue
    case " $uniq " in *" $d "*) ;; *) uniq="$uniq $d" ;; esac
  done
  read -r -a strong <<<"$uniq"

  if [[ "${#strong[@]}" -eq 1 ]]; then DEVICE="${strong[0]}"; echo "    device (auto-detected): $DEVICE"; return 0; fi
  if [[ "${#strong[@]}" -gt 1 ]]; then
    echo "    Multiple EnOcean-like adapters found — pass --device to choose one:" >&2
    printf '      %s\n' "${strong[@]}" >&2
    return 1
  fi
  if [[ "${#weak[@]}" -gt 0 ]]; then
    echo "    Could not confidently identify the stick. Pass --device <path>. Serial by-id devices:" >&2
    printf '      %s\n' "${weak[@]}" >&2
    return 1
  fi
  for d in /dev/serial0 /dev/ttyAMA0 /dev/ttyS0; do [[ -e "$d" ]] && { uart="$d"; break; }; done
  if [[ -n "$uart" ]]; then
    echo "    No USB serial found, but $uart exists (EnOcean Pi GPIO hat?)." >&2
    echo "    Free the serial console first (raspi-config -> Interface -> Serial: login shell OFF," >&2
    echo "    serial hardware ON), then re-run:  sudo $0 --device $uart" >&2
  else
    echo "    No serial devices found (/dev/serial/by-id and the GPIO UART are both empty)." >&2
  fi
  return 1
}

# Warn (only) about services that seize USB-serial adapters — a very common failure on Debian/Pi.
warn_grabbers() {
  local warned=0
  if have systemctl && systemctl is-active --quiet ModemManager 2>/dev/null; then
    warned=1
    echo "  ! ModemManager is active and may grab the USB serial device."
    echo "    fix: sudo systemctl mask --now ModemManager"
  fi
  if have brltty || { have dpkg && dpkg -s brltty >/dev/null 2>&1; }; then
    warned=1
    echo "  ! brltty is installed and is known to seize FTDI/CDC serial adapters."
    echo "    fix: sudo systemctl mask --now brltty brltty-udev 2>/dev/null; sudo apt-get purge -y brltty"
  fi
  [[ "$warned" -eq 0 ]] && echo "    none detected"
  return 0
}

# ---------------------------------------------------------------------------
# --check: report detection and exit without changing anything (no root needed)
# ---------------------------------------------------------------------------
MAJOR="$(ser2net_major || true)"

if [[ "$CHECK" -eq 1 ]]; then
  echo "==> ser2net"
  [[ -n "$MAJOR" ]] && echo "    installed: v$MAJOR" || echo "    not installed"
  echo "    config path: $(config_path_for "${MAJOR:-4}")"
  echo "==> device"
  resolve_device || true
  echo "==> serial-grabbing services"
  warn_grabbers
  echo "==> port :$PORT"
  set +e; port_status; ps=$?; set -e
  case "$ps" in
    0) echo "    in use (something already serves :$PORT)" ;;
    1) echo "    free" ;;
    2) echo "    unknown — install iproute2 for 'ss'" ;;
  esac
  echo "(--check: no changes made)"
  exit 0
fi

# ---------------------------------------------------------------------------
# Mutating path (needs root)
# ---------------------------------------------------------------------------
if [[ "$EUID" -ne 0 ]]; then echo "Please run as root (sudo $0), or use --check for a read-only report." >&2; exit 1; fi

if [[ -z "$MAJOR" ]]; then
  echo "==> ser2net not installed"
  if have apt-get; then
    echo "    installing via apt-get"
    apt-get update -qq
    apt-get install -y ser2net
    MAJOR="$(ser2net_major || true)"
  else
    echo "    apt-get is unavailable — install ser2net with your package manager, then re-run." >&2
    exit 1
  fi
fi
[[ -n "$MAJOR" ]] || { echo "ser2net still not detected after install." >&2; exit 1; }

CFG="$(config_path_for "$MAJOR")"
echo "==> ser2net v$MAJOR, config: $CFG"

echo "==> Locating the EnOcean transceiver"
resolve_device || exit 1

echo "==> Checking for serial-grabbing services"
warn_grabbers

set +e; port_status; ps=$?; set -e
if [[ "$ps" -eq 0 && "$FORCE" -ne 1 ]]; then
  echo "==> Something already listens on :$PORT. Current $CFG:"
  sed -n '1,60p' "$CFG" 2>/dev/null || echo "    (no $CFG)"
  echo "    Looks already set up. Re-run with --force to overwrite. Nothing changed."
  exit 0
fi
if [[ "$ps" -eq 2 && "$FORCE" -ne 1 ]]; then
  echo "Can't check whether :$PORT is already in use (no ss/netstat). Install iproute2, or re-run" >&2
  echo "with --force if you're sure nothing else uses it. Nothing changed." >&2
  exit 1
fi
[[ "$ps" -eq 0 && "$FORCE" -eq 1 ]] && echo "==> --force: overwriting the existing :$PORT configuration"

echo "==> Writing $CFG"
mkdir -p "$(dirname "$CFG")"
BACKUP=""
if [[ -f "$CFG" ]]; then BACKUP="${CFG}.bak.$(ts)"; cp -a "$CFG" "$BACKUP"; echo "    backed up -> $BACKUP"; fi
if [[ "$MAJOR" == "3" ]]; then
  # Legacy ser2net v3 line format: <port>:raw:<timeout>:<device>:<options>
  printf '%s:raw:0:%s:57600 8N1\n' "$PORT" "$DEVICE" > "$CFG"
else
  sed "s#__ENOCEAN_DEVICE__#${DEVICE}#g" "$HERE/ser2net.yaml" > "$CFG"
fi

echo "==> Enabling + (re)starting ser2net"
systemctl enable ser2net >/dev/null 2>&1 || true
systemctl restart ser2net || true

echo "==> Verifying ser2net is serving :$PORT"
ok=1
for _ in 1 2 3 4 5; do
  if systemctl is-active --quiet ser2net; then
    set +e; port_status; ps=$?; set -e
    if [[ "$ps" -ne 1 ]]; then ok=0; break; fi   # listening, or can't tell but service is up
  fi
  sleep 1
done
if [[ "$ok" -ne 0 ]]; then
  echo "!! ser2net did not come up on :$PORT — rolling back" >&2
  if [[ -n "$BACKUP" && -f "$BACKUP" ]]; then
    cp -a "$BACKUP" "$CFG"; echo "   restored previous $CFG" >&2
  else
    mv "$CFG" "${CFG}.failed.$(ts)" 2>/dev/null || true
  fi
  systemctl restart ser2net >/dev/null 2>&1 || true
  echo "   recent ser2net logs:" >&2
  journalctl -u ser2net -n 30 --no-pager 2>/dev/null || true
  exit 1
fi

echo
echo "Done — ser2net v$MAJOR is serving the stick on :$PORT."
echo "  device: $DEVICE"
echo "  verify: systemctl status ser2net ; ss -tlnp | grep $PORT"
echo
echo "Set the add-on option  connection: <this-pi-ip-or-host>:$PORT"
echo "Security: :$PORT is unauthenticated — restrict it to the HA host, e.g.:"
echo "  sudo ufw allow from <HA_HOST_IP> to any port $PORT proto tcp"
