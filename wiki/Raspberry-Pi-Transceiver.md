# Raspberry Pi EnOcean transceiver (ser2net)

The EnOcean USB stick lives on a Raspberry Pi that acts as the RF frontend; the add-on connects to
it over raw TCP. The add-on speaks TCP to ser2net natively (no socat, no PTY bridge).

![ser2net topology: on the Raspberry Pi the EnOcean USB stick (/dev/serial/by-id/…) connects at
57600 8N1 to ser2net, which exposes a raw TCP port :3000; the enocean2mqtt add-on on the Home
Assistant host connects to pi:3000 over raw TCP (LAN only / VPN).](https://raw.githubusercontent.com/t-ice/enocean-mqtt-ha/master/docs/img/ser2net-topology.png)


**Prerequisites (Pi):** a Linux host with `systemd` + `udev` and `ser2net`. The installer supports
both **ser2net v4** (YAML config) and **ser2net v3** (`.conf`) and detects which is installed. On
Debian/Ubuntu it installs `ser2net` for you.

## Setup (on the Pi)

```bash
git clone <this repo> && cd enocean-mqtt-ha
./pi/install.sh --check      # optional: read-only report of what it detects (no root, no changes)
sudo ./pi/install.sh
```

`install.sh` manages the **distro `ser2net.service`** (it does *not* add a second ser2net unit —
two would fight over `:3000` and the serial device). It is idempotent and non-destructive:

- installs `ser2net` if missing (via `apt-get`; otherwise it tells you to install it and stops);
- **detects the ser2net version and the config path the service actually reads** (from the unit's
  `ExecStart -c`, else the version default), and writes the matching format — v4 YAML or the v3
  `.conf` line — as a raw-TCP config (port 3000, 57600 8N1, `accepter: tcp` — never telnet, which
  would 0xFF-escape and corrupt ESP3 frames), backing up any existing config first;
- auto-detects the stick's **stable by-id path** — FTDI (USB300/FAM-USB) and EnOcean-branded
  adapters. It's reboot- and re-plug-safe, so **no udev rule is needed**. If several candidates
  match (or it's a CDC/`ttyACM` stick it can't identify) it lists them and asks you to pass
  `--device <path>`; for the **EnOcean Pi GPIO hat** pass `--device /dev/serial0`;
- warns (only) if **ModemManager** or **brltty** are present — both are known to seize USB-serial
  adapters — and prints how to neutralize them;
- **if something already serves `:3000` it prints the current config and exits** unless you pass
  `--force` — so it won't clobber a working setup by accident;
- after (re)starting, **verifies ser2net is actually listening on `:3000`; if not, it restores the
  previous config and prints the recent `journalctl` output**, so a bad start never leaves you with
  a silently broken service.

Verify:

```bash
systemctl status ser2net
ss -tlnp | grep 3000
```

### Optional: fixed `/dev/enocean` symlink

If you run **multiple FTDI devices** and prefer a fixed name over the by-id path, install the
optional udev rule and point the installer at it:

```bash
sudo install -m0644 pi/99-enocean.rules /etc/udev/rules.d/ && sudo udevadm control --reload && sudo udevadm trigger
sudo ./pi/install.sh --device /dev/enocean
```

(Set the `ATTRS{serial}` line in the rule first to disambiguate the right stick.)

## Troubleshooting (Pi side)

Run `./pi/install.sh --check` first — it reports the ser2net version, the config path, the detected
device, any serial-grabbers, and whether `:3000` is already in use, without changing anything.

- **ser2net won't start after install** — the installer already rolls the config back and prints the
  last log lines; see more with `journalctl -u ser2net -e`. Usually the device path is wrong or busy.
- **Device not found / wrong device** — pass `--device <path>`. List candidates with
  `ls -l /dev/serial/by-id/`. A CDC/`ttyACM` stick or several FTDI adapters won't auto-select.
- **Port claimed by ModemManager/brltty** — `sudo systemctl mask --now ModemManager` (and, for
  brltty, `sudo apt-get purge -y brltty`), then re-run.
- **EnOcean Pi GPIO hat** (no USB stick) — enable the UART and disable the serial *login shell*
  (`raspi-config` → Interface → Serial), then `sudo ./pi/install.sh --device /dev/serial0`.

## Add-on side

Set the add-on option **`tcp`** to `<pi-ip-or-host>:3000` (leave `device` empty; if both are set,
TCP wins). No socat, no PTY. If the Pi
power-cycles or ser2net restarts, the daemon reconnects on its own (exponential backoff inside the
asyncio loop — no external probe or restart loop). The add-on's native transport uses `socket://`
(raw TCP), matching ser2net's raw `accepter`, so ESP3 framing is preserved.

## Security

Port 3000 is unauthenticated and unencrypted. Restrict it to the HA host, e.g.:

```bash
sudo ufw allow from <HA_HOST_IP> to any port 3000 proto tcp
```

For cross-segment links use WireGuard/stunnel.

## Switching to a local stick instead

Prefer to plug the stick directly into the Home Assistant host? Clear the `tcp` option and set
`device` to the stick's serial path — start the add-on once and its **Log** lists the available serial
devices, so you can copy the right `/dev/…` path.
