"""Encode + transmit EnOcean telegrams from a sensor's send request.

The assembly is decomposed into named steps: pick direction + sender, create the ``RadioPacket``,
then apply exactly one payload strategy — learn-response, raw-data, or EEP-encoded default/data.
"""

from __future__ import annotations

import json
import logging

import enocean2mqtt.protocol.utils as utils
from enocean2mqtt.config import as_bool
from enocean2mqtt.domain.sensor import Sensor
from enocean2mqtt.protocol.constants import PACKET
from enocean2mqtt.protocol.packet import RadioPacket
from enocean2mqtt.protocol.security import DEFAULT_SLF, SecureDevice, encrypt_telegram, parse_slf

logger = logging.getLogger("enocean2mqtt.application.encoder")

# RORGs that must never be secure-wrapped on TX: the secure RORGs themselves (SEC 0x30, SEC_ENCAPS
# 0x31, SEC_CDM 0x33, SEC_TI 0x35) — already secure/control telegrams — and the signal telegram
# (0xD0). F6 (RPS/PTM) is deliberately NOT skipped: we secure it as 0x30 by design.
_SECURE_TX_SKIP_RORGS = frozenset({0x30, 0x31, 0x33, 0x35, 0xD0})


class PacketEncoder:
    def __init__(self, transport):
        self._transport = transport
        # Optional hook (set by the daemon) to persist an advanced outbound rolling code.
        self.on_secure_state_change = None

    async def send(
        self,
        sensor,
        destination,
        command=None,
        negate_direction=False,
        learn_data=None,
        default_sender=None,
    ):
        """Build and transmit the telegram for *sensor*."""
        sensor = Sensor.from_dict(sensor)  # accept a raw mapping too (idempotent for a Sensor)
        direction = self._direction(sensor, negate_direction)
        is_learn_response = learn_data is not None
        sender = self._sender(sensor, default_sender)
        force_learn = sensor.learn

        try:
            packet = RadioPacket.create(
                sensor.rorg,
                sensor.func,
                sensor.type,
                direction=direction,
                command=command,
                sender=sender,
                destination=destination,
                learn=is_learn_response | force_learn,
            )
        except ValueError as err:
            logger.error("Cannot create RF packet: %s", err)
            return

        # Exactly one payload strategy applies.
        if is_learn_response:
            self._apply_learn_response(packet, learn_data)
        elif sensor.has_raw_data:
            if not self._apply_raw_data(packet, sensor.raw_data):
                return  # invalid raw data — already logged
        else:
            self._apply_default_and_data(packet, sensor)

        # Secure TX: wrap the plaintext telegram into a 0x30/0x31 secure telegram (secure devices).
        if not is_learn_response and as_bool(sensor.security) and (sensor.key_snd or sensor.key):
            if packet.data[0] in _SECURE_TX_SKIP_RORGS:
                logger.debug("not securing RORG 0x%02X (not a securable telegram)", packet.data[0])
            else:
                packet = self._wrap_secure(packet, sensor)

        logger.info("sending: %s", packet)
        await self._transport.send(packet)

    def _wrap_secure(self, packet, sensor):
        """Encrypt+MAC the built telegram into a secure (0x30/0x31) one; advance outbound RLC."""
        slf = parse_slf(int(sensor.slf) if sensor.slf is not None else DEFAULT_SLF)
        dev = SecureDevice(
            key=bytes.fromhex(sensor.key_snd or sensor.key),
            rlc=int(sensor.rlc_snd or 0),
            rlc_size=slf.rlc_size,
            rlc_tx=slf.rlc_tx,
            cmac_len=slf.cmac_len,
        )
        rorg = packet.data[0]
        plaintext = bytes(packet.data[1:-5])  # DB payload (strip RORG + sender(4) + status)
        rorg_s, wire = encrypt_telegram(dev, rorg, plaintext)
        sensor["rlc_snd"] = dev.rlc
        if self.on_secure_state_change is not None:
            self.on_secure_state_change(sensor)
        new_data = [rorg_s, *wire, *packet.data[-5:-1], packet.data[-1]]
        return RadioPacket(PACKET.RADIO_ERP1, data=new_data, optional=packet.optional)

    @staticmethod
    def _direction(sensor, negate_direction):
        """The EEP direction indicator, inverted for a reply."""
        # device_config carries direction as "" when unset; an empty/falsy direction must NOT be
        # passed to RadioPacket.create -> select_eep (it would match no profile with that direction,
        # select nothing, and make set_eep a silent no-op — which breaks property-based commands
        # like FSB14 cover up/down/stop). Normalise falsy -> None.
        direction = sensor.direction or None
        if direction is None:
            return None
        if negate_direction:
            direction = 1 if direction == 2 else 2
        return direction

    @staticmethod
    def _sender(sensor, default_sender):
        """A sensor-specified sender (base_id + offset) or the transceiver's Base ID."""
        if sensor.sender is not None:
            return utils.int_to_bytes(sensor.sender)
        return default_sender

    @staticmethod
    def _apply_learn_response(packet, learn_data):
        """Copy the incoming EEP/manufacturer bytes and set the learn-ack flag."""
        packet.data[1:5] = learn_data[1:5]
        packet.data[4] = 0xF0

    @staticmethod
    def _apply_raw_data(packet, raw_data_str) -> bool:
        """Place user-supplied raw payload bytes; return False (logged) if the length is invalid."""
        logger.debug("sensor data: %s", raw_data_str)
        try:
            # hex-string format supports >8 bytes (VLD). -1 for RORG, -4 for the sender ID.
            raw_data = utils.from_hex_string(raw_data_str)
            if isinstance(raw_data, int):  # a single byte parses to an int; treat it as one byte
                raw_data = [raw_data]
            max_raw_data_len = len(packet.data) - 1 - 4
            if len(raw_data) == max_raw_data_len - 1:
                # status byte not supplied
                packet.data[1:max_raw_data_len] = raw_data
            elif len(raw_data) == max_raw_data_len:
                # status byte supplied
                packet.data[1:max_raw_data_len] = raw_data[:-1]
                packet.data[-1] = raw_data[-1]
            else:
                raise ValueError(
                    f"invalid raw_data length; expected "
                    f"[{max_raw_data_len - 1}:{max_raw_data_len}] bytes"
                )
        except (ValueError, TypeError) as ex:
            logger.warning("Invalid raw_data %r (%s); send dropped", raw_data_str, ex)
            return False
        return True

    @staticmethod
    def _apply_default_and_data(packet, sensor):
        """Seed with default_data (if any) then override with property-based data (if any)."""
        if sensor.default_data is not None:
            PacketEncoder._apply_default_data(packet, sensor.default_data)

        if sensor.data is not None:
            logger.debug("sensor data: %s", sensor.data)
            packet.set_eep(sensor.data)
            packet.data[-1] = packet.status
            packet.parse_eep()  # keep the packet's logging representation in sync
        else:
            logger.warning("sending only default data as answer to %s", sensor.name)

    @staticmethod
    def _apply_default_data(packet, default_data):
        """default_data is either a raw int literal (4 payload bytes) or a JSON EEP property map."""
        try:
            value = int(default_data, 0)  # raw int literal, e.g. "0xDEADBEEF"
            packet.data[1:5] = utils.int_to_bytes(value)
        except Exception:
            logger.debug("sensor default_data: %s", default_data)
            packet.set_eep(json.loads(default_data))
            packet.data[-1] = packet.status
            packet.parse_eep()
