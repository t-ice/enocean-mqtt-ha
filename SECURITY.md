# Security Policy

## Supported versions

Only the **latest released version** of the add-on receives security fixes. Please update before
reporting an issue, in case it is already resolved.

## Reporting a vulnerability

**Please do not open a public issue for security-sensitive problems** (for example broker credentials,
LAN/VPN exposure of the ser2net link, or anything that could compromise a user's Home Assistant).

Report privately using **GitHub's private vulnerability reporting**:

1. Go to the repository's **[Security](https://github.com/t-ice/enocean-mqtt-ha/security)** tab.
2. Click **Report a vulnerability** and describe the issue, how to reproduce it, and the impact.

You'll get a response as soon as possible. Once a fix is available and released, the advisory is
published with credit to the reporter (unless you prefer to remain anonymous).

## Scope

This add-on bridges EnOcean radio to MQTT. When assessing impact, note that it:

- talks to a **local serial device** or a **ser2net TCP endpoint** (which should stay on a trusted
  LAN or VPN — it is unauthenticated raw TCP by design);
- connects to an **MQTT broker** (by default the Supervisor's Mosquitto service);
- reads/writes **`/config/enocean2mqtt/`** and its own `/data`.

It requests no elevated privileges beyond `uart` access and is confined by an AppArmor profile
(`addon/apparmor.txt`).
