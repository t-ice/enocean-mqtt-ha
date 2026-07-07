import enocean2mqtt.protocol.utils


def test_to_hex_string():
    assert enocean2mqtt.protocol.utils.to_hex_string(0) == "00"
    assert enocean2mqtt.protocol.utils.to_hex_string(15) == "0F"
    assert enocean2mqtt.protocol.utils.to_hex_string(16) == "10"
    assert enocean2mqtt.protocol.utils.to_hex_string(22) == "16"

    assert enocean2mqtt.protocol.utils.to_hex_string([0, 15, 16, 22]) == "00:0F:10:16"
    assert enocean2mqtt.protocol.utils.to_hex_string([0x00, 0x0F, 0x10, 0x16]) == "00:0F:10:16"


def test_from_hex_string():
    assert enocean2mqtt.protocol.utils.from_hex_string("00") == 0
    assert enocean2mqtt.protocol.utils.from_hex_string("0F") == 15
    assert enocean2mqtt.protocol.utils.from_hex_string("10") == 16
    assert enocean2mqtt.protocol.utils.from_hex_string("16") == 22

    assert enocean2mqtt.protocol.utils.from_hex_string("00:0F:10:16") == [0, 15, 16, 22]
    assert enocean2mqtt.protocol.utils.from_hex_string("00:0F:10:16") == [0x00, 0x0F, 0x10, 0x16]
