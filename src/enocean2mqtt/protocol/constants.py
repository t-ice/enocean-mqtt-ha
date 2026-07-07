"""ESP3 / EEP protocol constants.

Owned, restyled reference tables mirroring the EnOcean specification (packet types, return/event
codes, RORGs, data-byte bit indices). Enum values are the specification's numbers — kept verbatim by
nature; members this bridge does not yet act on are retained as the documented reference surface
(see docs/esp3-compliance.md), not dead code.
"""

from enum import IntEnum


# EnOceanSerialProtocol3.pdf / 12
class PACKET(IntEnum):
    RESERVED = 0x00
    # RADIO == RADIO_ERP1
    # Kept for backwards compatibility reasons, for example custom packet
    # generation shouldn't be affected...
    RADIO = 0x01
    RADIO_ERP1 = 0x01
    RESPONSE = 0x02
    RADIO_SUB_TEL = 0x03
    EVENT = 0x04
    COMMON_COMMAND = 0x05
    SMART_ACK_COMMAND = 0x06
    REMOTE_MAN_COMMAND = 0x07
    RADIO_MESSAGE = 0x09
    # RADIO_ADVANCED == RADIO_ERP2
    # Kept for backwards compatibility reasons
    RADIO_ADVANCED = 0x0A
    RADIO_ERP2 = 0x0A
    RADIO_802_15_4 = 0x10
    COMMAND_2_4 = 0x11


# Common command codes carried as the first data byte of a PACKET.COMMON_COMMAND (0x05).
# EnOceanSerialProtocol3.pdf / 24 (the ones this daemon issues; codes verified against ESP3 V1.37).
class COMMON_COMMAND_CODE(IntEnum):
    CO_WR_RESET = 0x02  # reset the transceiver
    CO_RD_VERSION = 0x03  # read app/API version, chip id + version, app description
    CO_WR_IDBASE = 0x07  # set the Base ID (max 10 writes for the transceiver's lifetime)
    CO_RD_IDBASE = 0x08  # read the transceiver's Base ID (used as our default sender)
    CO_WR_REPEATER = 0x09  # set repeater on/off + level (1 or 2)
    CO_RD_REPEATER = 0x0A  # read repeater enable + level
    CO_WR_FILTER_ADD = 0x0B  # add an RX filter
    CO_WR_FILTER_DEL = 0x0C  # delete an RX filter
    CO_WR_FILTER_DEL_ALL = 0x0D  # delete all RX filters
    CO_WR_FILTER_ENABLE = 0x0E  # enable/disable RX filtering
    CO_RD_FILTER = 0x0F  # read the configured RX filters
    CO_WR_SUBTEL = 0x11  # enable sub-telegram info in RX
    CO_WR_MODE = 0x1C  # ERP1 (0x00) vs advanced/ERP2 (0x01) telegram mode
    CO_RD_NUMSECUREDEVICES = 0x1D  # count of secured devices
    CO_RD_DUTYCYCLE_LIMIT = 0x23  # remaining TX duty-cycle budget (0x24 = CO_SET_BAUDRATE)
    CO_WR_REMAN_CODE = 0x2E  # set the 32-bit remote-management security code


# EnOceanSerialProtocol3.pdf / 18
class RETURN_CODE(IntEnum):
    OK = 0x00
    ERROR = 0x01
    NOT_SUPPORTED = 0x02
    WRONG_PARAM = 0x03
    OPERATION_DENIED = 0x04


# EnOceanSerialProtocol3.pdf / 20
class EVENT_CODE(IntEnum):
    SA_RECLAIM_NOT_SUCCESFUL = 0x01
    SA_CONFIRM_LEARN = 0x02
    SA_LEARN_ACK = 0x03
    CO_READY = 0x04
    CO_EVENT_SECUREDEVICES = 0x05
    CO_DUTYCYCLE_LIMIT = 0x06  # TX duty-cycle budget exhausted; transmits are throttled
    CO_TRANSMIT_FAILED = 0x07  # a transmit could not be sent (e.g. duty cycle / collision)


# EnOcean_Equipment_Profiles_EEP_V2.61_public.pdf / 8
class RORG(IntEnum):
    UNDEFINED = 0x00
    RPS = 0xF6
    BS1 = 0xD5
    BS4 = 0xA5
    VLD = 0xD2
    MSC = 0xD1
    ADT = 0xA6
    SM_LRN_REQ = 0xC6
    SM_LRN_ANS = 0xC7
    SM_REC = 0xA7
    SYS_EX = 0xC5
    SEC = 0x30
    SEC_ENCAPS = 0x31
    SEC_DECRYPTED = 0x32  # host-facing result of decrypting a 0x30 (RORG-less) secure telegram
    SEC_CDM = 0x33  # secure chained (segmented) message
    SEC_TI = 0x35  # secure teach-in telegram
    UTE = 0xD4


# Results for message parsing
class PARSE_RESULT(IntEnum):
    OK = 0x00
    INCOMPLETE = 0x01
    CRC_MISMATCH = 0x03


# Data byte indexing
# Starts from the end, so works on messages of all length.
class DB0:
    BIT_0 = -1
    BIT_1 = -2
    BIT_2 = -3
    BIT_3 = -4
    BIT_4 = -5
    BIT_5 = -6
    BIT_6 = -7
    BIT_7 = -8


class DB1:
    BIT_0 = -9
    BIT_1 = -10
    BIT_2 = -11
    BIT_3 = -12
    BIT_4 = -13
    BIT_5 = -14
    BIT_6 = -15
    BIT_7 = -16


class DB2:
    BIT_0 = -17
    BIT_1 = -18
    BIT_2 = -19
    BIT_3 = -20
    BIT_4 = -21
    BIT_5 = -22
    BIT_6 = -23
    BIT_7 = -24


class DB3:
    BIT_0 = -25
    BIT_1 = -26
    BIT_2 = -27
    BIT_3 = -28
    BIT_4 = -29
    BIT_5 = -30
    BIT_6 = -31
    BIT_7 = -32


class DB4:
    BIT_0 = -33
    BIT_1 = -34
    BIT_2 = -35
    BIT_3 = -36
    BIT_4 = -37
    BIT_5 = -38
    BIT_6 = -39
    BIT_7 = -40


class DB5:
    BIT_0 = -41
    BIT_1 = -42
    BIT_2 = -43
    BIT_3 = -44
    BIT_4 = -45
    BIT_5 = -46
    BIT_6 = -47
    BIT_7 = -48


class DB6:
    BIT_0 = -49
    BIT_1 = -50
    BIT_2 = -51
    BIT_3 = -52
    BIT_4 = -53
    BIT_5 = -54
    BIT_6 = -55
    BIT_7 = -56
