import logging
from typing import ClassVar, NamedTuple

import enocean2mqtt.protocol.utils
from enocean2mqtt.protocol import crc8
from enocean2mqtt.protocol.constants import DB0, DB2, DB3, DB4, DB6, PACKET, PARSE_RESULT, RORG
from enocean2mqtt.protocol.eep_codec import EepCodec

# Broadcast destination / placeholder sender used when a packet is created without explicit
# addresses (the sender is normally overridden with the transceiver's Base ID before sending).
BROADCAST_ADDRESS = [0xFF, 0xFF, 0xFF, 0xFF]
PLACEHOLDER_SENDER = [0xDE, 0xAD, 0xBE, 0xEF]

# Bit position of the LRN (teach-in) flag within DB0 of a 1BS/4BS telegram (1 = data, 0 = teach-in).
_LEARN_BIT_SHIFT = 3


class ParseResult(NamedTuple):
    """Outcome of :meth:`Packet.parse_msg`: status, the unconsumed buffer, and the packet (if any).

    Tuple-compatible, so existing index/unpack call sites keep working; the named fields document
    what each position means.
    """

    status: PARSE_RESULT
    remaining: list
    packet: "Packet | None"


class Packet:
    """Base class for an ESP3 packet.

    Used both for packet generation and, via ``Packet.parse_msg(buf)``, for parsing a received
    message — ``parse_msg`` returns the matching subclass when one is defined for the packet type.
    """

    logger = logging.getLogger("enocean2mqtt.protocol.packet")

    def __init__(self, packet_type, data=None, optional=None):
        self.packet_type = packet_type
        self.rorg = RORG.UNDEFINED
        self.rorg_func = None
        self.rorg_type = None
        self.rorg_manufacturer = None

        self.received = None

        self.data = data if isinstance(data, list) else []
        self.optional = optional if isinstance(optional, list) else []

        self.status = 0
        self.parsed: dict = {}
        self.repeater_count = 0
        # EEP interpretation is delegated to this collaborator (framing stays this class's concern).
        self._eep = EepCodec()

        self.parse()

    def __str__(self):
        data = [hex(o) for o in self.data]
        optional = [hex(o) for o in self.optional]
        return f"0x{self.packet_type:02X} {data} {optional} {self.parsed}"

    def __eq__(self, other):
        return (
            self.packet_type == other.packet_type
            and self.rorg == other.rorg
            and self.data == other.data
            and self.optional == other.optional
        )

    @property
    def _bit_data(self):
        # The payload bits: RORG (byte 0) and the sender id + status (last 5 bytes) frame the actual
        # data bytes in between. Valid for the RPS/1BS/4BS/VLD packets this bridge manipulates.
        return enocean2mqtt.protocol.utils.to_bitarray(
            self.data[1 : len(self.data) - 5], (len(self.data) - 6) * 8
        )

    @_bit_data.setter
    def _bit_data(self, value):
        # The same as getting the data, first and last 5 bits are ommitted, as they are defined...
        for byte in range(len(self.data) - 6):
            self.data[byte + 1] = enocean2mqtt.protocol.utils.from_bitarray(
                value[byte * 8 : (byte + 1) * 8]
            )

    @property
    def _bit_status(self):
        return enocean2mqtt.protocol.utils.to_bitarray(self.status)

    @_bit_status.setter
    def _bit_status(self, value):
        self.status = enocean2mqtt.protocol.utils.from_bitarray(value)

    @staticmethod
    def parse_msg(buf):
        """Parse one ESP3 message from *buf*.

        Returns a :class:`ParseResult` (status, remaining_buffer, packet_or_None).
        """
        # Without a start byte (0x55) there is nothing to parse yet.
        if 0x55 not in buf:
            return ParseResult(PARSE_RESULT.INCOMPLETE, [], None)

        # Work on a plain list of ints from the sync byte on (bytes/bytearray both iterate ints).
        buf = list(buf)
        buf = buf[buf.index(0x55) :]
        try:
            data_len = (buf[1] << 8) | buf[2]
            opt_len = buf[3]
        except IndexError:
            # If the fields don't exist, message is incomplete
            return ParseResult(PARSE_RESULT.INCOMPLETE, buf, None)

        # Header: 6 bytes, data, optional data and data checksum
        msg_len = 6 + data_len + opt_len + 1
        if len(buf) < msg_len:
            # If buffer isn't long enough, the message is incomplete
            return ParseResult(PARSE_RESULT.INCOMPLETE, buf, None)

        msg = buf[0:msg_len]
        buf = buf[msg_len:]

        packet_type = msg[4]
        data = msg[6 : 6 + data_len]
        opt_data = msg[6 + data_len : 6 + data_len + opt_len]

        # Check CRCs for header and data
        if msg[5] != crc8.calc(msg[1:5]):
            # Routine on noisy radio — the read loop resyncs past the bad frame. Log at DEBUG
            # (log_level: debug) with the raw header bytes for diagnosis, not as ERROR spam.
            Packet.logger.debug("Header CRC error, discarding frame: %s", bytes(msg[:6]).hex(" "))
            return ParseResult(PARSE_RESULT.CRC_MISMATCH, buf, None)
        if msg[6 + data_len + opt_len] != crc8.calc(msg[6 : 6 + data_len + opt_len]):
            Packet.logger.debug("Data CRC error, discarding frame: %s", bytes(msg).hex(" "))
            return ParseResult(PARSE_RESULT.CRC_MISMATCH, buf, None)

        # If we got this far, everything went ok (?)
        if packet_type == PACKET.RADIO_ERP1:
            # Need to handle UTE Teach-in here, as it's a separate packet type...
            if data[0] == RORG.UTE:
                packet = UTETeachInPacket(packet_type, data, opt_data)
            else:
                packet = RadioPacket(packet_type, data, opt_data)
        elif packet_type == PACKET.RESPONSE:
            packet = ResponsePacket(packet_type, data, opt_data)
        elif packet_type == PACKET.EVENT:
            packet = EventPacket(packet_type, data, opt_data)
        else:
            packet = Packet(packet_type, data, opt_data)

        return ParseResult(PARSE_RESULT.OK, buf, packet)

    @staticmethod
    def create_common_command(command_code, *payload):
        """Build a PACKET.COMMON_COMMAND (0x05); the code is the first data byte, then *payload."""
        return Packet(PACKET.COMMON_COMMAND, data=[int(command_code), *payload])

    @staticmethod
    def _default_addresses(destination, sender):
        """Fill unset destination/sender with the broadcast/placeholder defaults and validate both.

        The placeholder sender is normally overridden with the transceiver's Base ID before sending.
        """
        if destination is None:
            Packet.logger.warning("Replacing destination with broadcast address.")
            destination = list(BROADCAST_ADDRESS)
        if sender is None:
            Packet.logger.warning("Replacing sender with default address.")
            sender = list(PLACEHOLDER_SENDER)
        if not isinstance(destination, list) or len(destination) != 4:
            raise ValueError("Destination must a list containing 4 (numeric) values.")
        if not isinstance(sender, list) or len(sender) != 4:
            raise ValueError("Sender must a list containing 4 (numeric) values.")
        return destination, sender

    @staticmethod
    def create(
        packet_type,
        rorg,
        rorg_func,
        rorg_type,
        direction=None,
        command=None,
        destination=None,
        sender=None,
        learn=False,
        **kwargs,
    ):
        """
        Creates an packet ready for sending.
        Uses rorg, rorg_func and rorg_type to determine the values set based on EEP.
        Additional arguments (**kwargs) are used for setting the values.

        Currently only supports:
            - PACKET.RADIO_ERP1
            - RORGs RPS, BS1, BS4, VLD.

        TODO:
            - Require sender to be set? Would force the "correct" sender to be set.
            - Do we need to set telegram control bits?
              Might be useful for acting as a repeater?
        """

        if packet_type != PACKET.RADIO_ERP1:
            # At least for now, only support PACKET.RADIO_ERP1.
            raise ValueError("Packet type not supported by this function.")

        if rorg not in [RORG.RPS, RORG.BS1, RORG.BS4, RORG.VLD]:
            # At least for now, only support these RORGS.
            raise ValueError("RORG not supported by this function.")

        destination, sender = Packet._default_addresses(destination, sender)

        packet = Packet(packet_type, data=[], optional=[])
        packet.rorg = rorg
        packet.data = [packet.rorg]
        # Select EEP at this point, so we know how many bits we're dealing with (for VLD).
        packet.select_eep(rorg_func, rorg_type, direction, command)

        # Initialize data depending on the profile.
        if rorg in [RORG.RPS, RORG.BS1]:
            packet.data.extend([0])
        elif rorg == RORG.BS4:
            packet.data.extend([0, 0, 0, 0])
        else:  # VLD: length is command-specific — derive it from the selected case's fields.
            packet.data.extend([0] * packet._vld_data_bytes())
        packet.data.extend(sender)
        packet.data.extend([0])
        # Always use sub-telegram 3, maximum dbm (as per spec, when sending),
        # and no security (security not supported as per EnOcean Serial Protocol).
        packet.optional = [3, *destination, 255, 0]

        if command:
            # Set CMD to command, if applicable.. Helps with VLD.
            kwargs["CMD"] = command

        packet.set_eep(kwargs)
        if rorg in [RORG.BS1, RORG.BS4] and not learn:
            if rorg == RORG.BS1:
                packet.data[1] |= 1 << _LEARN_BIT_SHIFT
            if rorg == RORG.BS4:
                packet.data[4] |= 1 << _LEARN_BIT_SHIFT
        packet.data[-1] = packet.status

        # Parse the built packet, so it corresponds to the received packages
        # For example, stuff like RadioPacket.learn should be set.
        packet = Packet.parse_msg(packet.build()).packet
        packet.rorg = rorg
        packet.parse_eep(rorg_func, rorg_type, direction, command)
        return packet

    def parse(self):
        """Parse data from Packet"""
        # Parse status from messages
        if self.rorg in [RORG.RPS, RORG.BS1, RORG.BS4]:
            self.status = self.data[-1]
        if self.rorg == RORG.VLD:
            self.status = self.optional[-1]

        if self.rorg in [RORG.RPS, RORG.BS1, RORG.BS4]:
            # These message types should have repeater count in the last for bits of status.
            self.repeater_count = enocean2mqtt.protocol.utils.from_bitarray(self._bit_status[4:])
        return self.parsed

    def select_eep(self, rorg_func, rorg_type, direction=None, command=None):
        """Select the code-defined EEP profile for RORG-FUNC-TYPE (+ direction/command context)."""
        self.rorg_func = rorg_func
        self.rorg_type = rorg_type
        return self._eep.select(self.rorg, rorg_func, rorg_type, direction, command)

    def _vld_data_bytes(self):
        """VLD payload length in bytes for the selected command's case (min 1)."""
        return self._eep.vld_data_bytes(self._bit_data, self._bit_status)

    def parse_eep(self, rorg_func=None, rorg_type=None, direction=None, command=None):
        """Decode the telegram per its EEP profile into ``self.parsed``; returns the shortcuts."""
        if rorg_func is not None and rorg_type is not None:
            self.select_eep(rorg_func, rorg_type, direction, command)
        values = self._eep.decode(self._bit_data, self._bit_status)
        self.parsed.update(values)
        return list(values.keys())

    def set_eep(self, data):
        """Encode *data* ({shortcut: value}) into the packet bits per the selected EEP profile."""
        self._bit_data, self._bit_status = self._eep.encode(data, self._bit_data, self._bit_status)

    def build(self):
        """Build Packet for sending to EnOcean controller"""
        data_length = len(self.data)
        ords = [
            0x55,
            (data_length >> 8) & 0xFF,
            data_length & 0xFF,
            len(self.optional),
            int(self.packet_type),
        ]
        ords.append(crc8.calc(ords[1:5]))
        ords.extend(self.data)
        ords.extend(self.optional)
        ords.append(crc8.calc(ords[6:]))
        return ords


class RadioPacket(Packet):
    destination: ClassVar[list[int]] = [0xFF, 0xFF, 0xFF, 0xFF]
    dBm = 0
    sender: ClassVar[list[int]] = [0xFF, 0xFF, 0xFF, 0xFF]
    learn = True
    contains_eep = False

    def __str__(self):
        packet_str = super().__str__()
        return f"{self.sender_hex}->{self.destination_hex} ({self.dBm} dBm): {packet_str}"

    @staticmethod
    def create(
        rorg,
        rorg_func,
        rorg_type,
        direction=None,
        command=None,
        destination=None,
        sender=None,
        learn=False,
        **kwargs,
    ):
        return Packet.create(
            PACKET.RADIO_ERP1,
            rorg,
            rorg_func,
            rorg_type,
            direction,
            command,
            destination,
            sender,
            learn,
            **kwargs,
        )

    @property
    def sender_int(self):
        return enocean2mqtt.protocol.utils.combine_hex(self.sender)

    @property
    def sender_hex(self):
        return enocean2mqtt.protocol.utils.to_hex_string(self.sender)

    @property
    def destination_int(self):
        return enocean2mqtt.protocol.utils.combine_hex(self.destination)

    @property
    def destination_hex(self):
        return enocean2mqtt.protocol.utils.to_hex_string(self.destination)

    def parse(self):
        self.destination = self.optional[1:5]
        self.dBm = -self.optional[5]
        self.sender = self.data[-5:-1]
        # Default to learn == True, as some devices don't have a learn button
        self.learn = True

        self.rorg = self.data[0]

        # parse learn bit and FUNC/TYPE, if applicable
        if self.rorg == RORG.BS1:
            self.learn = not self._bit_data[DB0.BIT_3]
        if self.rorg == RORG.BS4:
            self.learn = not self._bit_data[DB0.BIT_3]
            if self.learn:
                self.contains_eep = self._bit_data[DB0.BIT_7]
                if self.contains_eep:
                    # Get rorg_func and rorg_type from an unidirectional learn packet
                    self.rorg_func = enocean2mqtt.protocol.utils.from_bitarray(
                        self._bit_data[DB3.BIT_7 : DB3.BIT_1]
                    )
                    self.rorg_type = enocean2mqtt.protocol.utils.from_bitarray(
                        self._bit_data[DB3.BIT_1 : DB2.BIT_2]
                    )
                    self.rorg_manufacturer = enocean2mqtt.protocol.utils.from_bitarray(
                        self._bit_data[DB2.BIT_2 : DB0.BIT_7]
                    )
                    self.logger.debug(
                        "learn received, EEP detected, "
                        f"RORG: 0x{self.rorg:02X}, FUNC: 0x{self.rorg_func:02X}, "
                        f"TYPE: 0x{self.rorg_type:02X}, "
                        f"Manufacturer: 0x{self.rorg_manufacturer:02X}"
                    )

        return super().parse()


class UTETeachInPacket(RadioPacket):
    # Request types
    TEACH_IN = 0b00
    DELETE = 0b01
    NOT_SPECIFIC = 0b10

    # Response types
    NOT_ACCEPTED: ClassVar[list[bool]] = [False, False]
    TEACHIN_ACCEPTED: ClassVar[list[bool]] = [False, True]
    DELETE_ACCEPTED: ClassVar[list[bool]] = [True, False]
    EEP_NOT_SUPPORTED: ClassVar[list[bool]] = [True, True]

    unidirectional = False
    response_expected = False
    number_of_channels = 0xFF
    rorg_of_eep = RORG.UNDEFINED
    request_type = NOT_SPECIFIC
    channel = None

    contains_eep = True

    @property
    def bidirectional(self):
        return not self.unidirectional

    @property
    def teach_in(self):
        return self.request_type != self.DELETE

    @property
    def delete(self):
        return self.request_type == self.DELETE

    def parse(self):
        super().parse()
        self.unidirectional = not self._bit_data[DB6.BIT_7]
        self.response_expected = not self._bit_data[DB6.BIT_6]
        self.request_type = enocean2mqtt.protocol.utils.from_bitarray(
            self._bit_data[DB6.BIT_5 : DB6.BIT_3]
        )
        self.rorg_manufacturer = enocean2mqtt.protocol.utils.from_bitarray(
            self._bit_data[DB3.BIT_2 : DB2.BIT_7] + self._bit_data[DB4.BIT_7 : DB3.BIT_7]
        )
        self.channel = self.data[2]
        self.rorg_type = self.data[5]
        self.rorg_func = self.data[6]
        self.rorg_of_eep = self.data[7]
        if self.teach_in:
            self.learn = True
        return self.parsed

    def create_response_packet(self, sender_id, response=TEACHIN_ACCEPTED):
        # Create data:
        # - Respond with same RORG (UTE Teach-in)
        # - Always use bidirectional communication, set response code, set command identifier.
        # - Databytes 5 to 0 are copied from the original message
        # - Set sender id and status
        db6 = enocean2mqtt.protocol.utils.from_bitarray(
            [True, False, *response, False, False, False, True]
        )
        data = [self.rorg, db6, *self.data[2:8], *sender_id, 0]

        # Always use 0x03 to indicate sending, attach sender ID, dBm, and security level
        optional = [3, *self.sender, 255, 0]

        return RadioPacket(PACKET.RADIO_ERP1, data=data, optional=optional)


class ResponsePacket(Packet):
    response = 0
    response_data: ClassVar[list[int]] = []

    def parse(self):
        self.response = self.data[0]
        self.response_data = self.data[1:]
        return super().parse()


class EventPacket(Packet):
    event = 0
    event_data: ClassVar[list[int]] = []

    def parse(self):
        self.event = self.data[0]
        self.event_data = self.data[1:]
        return super().parse()
