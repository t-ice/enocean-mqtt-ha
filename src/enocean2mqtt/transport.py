"""EnOcean transport helpers.

The daemon talks to the EnOcean transceiver either over a local serial device (``/dev/ttyUSB0``)
or over TCP to a remote ``ser2net`` instance on the Raspberry Pi that hosts the USB stick. These
helpers normalise the configured ``connection`` string and decide whether it is a network endpoint;
the actual async I/O lives in :mod:`enocean2mqtt.async_transport`.
"""

from __future__ import annotations

import re

# host:port  or  host:port with an explicit scheme we recognise.
_HOSTPORT_RE = re.compile(r"^[^/\s]+:\d+$")


def normalize_port(port: str) -> str:
    """Return a normalised URL for *port*.

    - ``socket://…``, ``rfc2217://…`` and other explicit schemes are passed through.
    - a bare ``host:port`` becomes ``socket://host:port`` (raw TCP to ser2net).
    - anything else (``/dev/ttyUSB0``, ``COM3``) is treated as a local device.
    """
    port = port.strip()
    if "://" in port:
        return port
    if _HOSTPORT_RE.match(port):
        return f"socket://{port}"
    return port


def is_network_port(port: str) -> bool:
    """True if *port* refers to a network transceiver (ser2net) rather than a local device."""
    return "://" in normalize_port(port) and not normalize_port(port).startswith("spy://")
