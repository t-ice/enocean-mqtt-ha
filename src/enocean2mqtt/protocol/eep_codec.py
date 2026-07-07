"""EEP interpretation for a telegram, split out of the ESP3 ``Packet``.

``Packet`` handles ESP3 framing (sync byte, length, CRC, sub-telegram bytes); the *meaning* of the
payload — which EEP profile applies and how its fields decode/encode — lives here. A ``Packet``
composes one ``EepCodec`` and delegates ``select_eep``/``parse_eep``/``set_eep`` to it, so framing
no longer carries EEP interpretation as a concern (and the codec is unit-testable on its own).

The codec is stateful only in a small, telegram-scoped sense: it remembers the selected profile and
the direction/command context between ``select`` and the subsequent decode/encode. It never mutates
the packet; it operates on the bit arrays passed in and returns results.
"""

from __future__ import annotations

import logging

from enocean2mqtt.protocol.profiles import DEFAULT_PROFILE_REGISTRY, ProfileRegistry, engine
from enocean2mqtt.protocol.profiles._model import Profile

logger = logging.getLogger("enocean2mqtt.protocol.eep_codec")


class EepCodec:
    """Selects an EEP profile and decodes/encodes a telegram's bits against it.

    The profile source is injectable via *registry* (defaults to the code-defined profiles); the
    case-selection and field decode/encode remain stateless ``engine`` functions.
    """

    def __init__(self, registry: ProfileRegistry | None = None) -> None:
        self._registry = registry or DEFAULT_PROFILE_REGISTRY
        self.profile: Profile | None = None
        self.direction: int | None = None
        self.command: int | None = None

    def select(self, rorg, rorg_func, rorg_type, direction=None, command=None) -> bool:
        """Select the profile for RORG-FUNC-TYPE (+ direction/command context). True if found."""
        self.direction = direction
        self.command = command
        self.profile = self._registry.find(rorg, rorg_func, rorg_type)
        if self.profile is None:
            logger.debug("No EEP profile for RORG=%s FUNC=%s TYPE=%s", rorg, rorg_func, rorg_type)
        return self.profile is not None

    def _case(self, bit_data, bit_status):
        """Resolve the profile's active case from the current bits + direction/command context."""
        if self.profile is None:
            return None
        return engine.select_case(self.profile, bit_data, bit_status, self.direction, self.command)

    def vld_data_bytes(self, bit_data, bit_status) -> int:
        """VLD payload length in bytes for the selected command's case (min 1)."""
        case = self._case(bit_data, bit_status)
        fields = case.fields if case is not None else ()
        end_bits = max((f.offset + f.size for f in fields), default=8)
        return max(1, (end_bits + 7) // 8)

    def decode(self, bit_data, bit_status) -> dict:
        """Decode the telegram per the selected profile → {shortcut: {...}} (empty if no case)."""
        case = self._case(bit_data, bit_status)
        if case is None:
            return {}
        return engine.decode(case, bit_data, bit_status)

    def encode(self, data, bit_data, bit_status):
        """Encode *data* ({shortcut: value}) into the bits per the selected profile (a no-op if
        no case is selected). Returns the (possibly updated) bit arrays."""
        case = self._case(bit_data, bit_status)
        if case is None:
            return bit_data, bit_status
        return engine.encode(case, data, bit_data, bit_status)
