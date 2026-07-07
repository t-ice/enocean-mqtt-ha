"""Discovery MAPPING fragment: A5 (4BS) environmental sensors.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import binary, dcfg, entity, sensor, vt
from enocean2mqtt.homeassistant.mapping._catalog import hum, svc, t_raw, temp_c, temp_pair

MAPPING = {
    165: {
        2: {
            1: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            2: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            3: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            4: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            5: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            6: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            7: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            8: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            9: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            10: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            11: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            16: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            17: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            18: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            19: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            20: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            21: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            22: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            23: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            24: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            25: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            26: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            27: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            32: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
            48: {
                'device_config': dcfg(),
                'entities': temp_pair(),
            },
        },
        4: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                    binary('status', '{% if value_json.TSN == 0 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                    binary('status', '{% if value_json.TSN == 0 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                ],
            },
        },
        6: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('lux_raw', '{% if value_json.RS == 0 %}\n  {{ value_json.ILL1 }}\n{% else %}\n  {{ value_json.ILL2 }}\n{% endif %}', device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', '{% if value_json.RS == 0 %}\n  {{ value_json.ILL1 | round(1) }}\n{% else %}\n  {{ value_json.ILL2 | round(1) }}\n{% endif %}', device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('ill1_raw', vt('ILL1'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill1', vt('ILL1', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill2_raw', vt('ILL2'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill2', vt('ILL2', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('lux_raw', '{% if value_json.RS == 0 %}\n  {{ value_json.ILL1 }}\n{% else %}\n  {{ value_json.ILL2 }}\n{% endif %}', device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', '{% if value_json.RS == 0 %}\n  {{ value_json.ILL1 | round(2) }}\n{% else %}\n  {{ value_json.ILL2 | round(2) }}\n{% endif %}', device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('ill1_raw', vt('ILL1'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill1', vt('ILL1', 'round(2)'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill2_raw', vt('ILL2'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('ill2', vt('ILL2', 'round(2)'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('temp', vt('TEMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('sv', vt('SV'), device_class='energy', state_class='total_increasing', unit='%'),
                    sensor('tmpav', vt('TMPAV'), state_class='measurement'),
                    sensor('enav', vt('ENAV'), device_class='energy', state_class='total_increasing'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ill2', vt('ILL2'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('ill1', vt('ILL1'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('rs', vt('RS'), state_class='measurement'),
                ],
            },
        },
        7: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    entity('sensor', 'v_raw', state_topic='', value_template=vt('SVC'), enabled_by_default='false', availability_topic='', availability_template='{% if value_json.SVA == 1 %}\n  online\n{% else %}\n  offline\n{% endif %}', device_class='voltage', state_class='measurement', unit_of_measurement='V'),
                    entity('sensor', 'voltage', state_topic='', value_template=vt('SVC', 'round(2)'), availability_topic='', availability_template='{% if value_json.SVA == 1 %}\n  online\n{% else %}\n  offline\n{% endif %}', device_class='voltage', state_class='measurement', unit_of_measurement='V'),
                    binary('pir', '{% if value_json.PIRS == 1 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    binary('pir', '{% if value_json.PIRS == 1 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    binary('pir', '{% if value_json.PIRS == 1 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    sensor('lux_raw', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                ],
            },
        },
        8: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('lux_raw', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    t_raw(),
                    temp_c(),
                    binary('pir', '{% if value_json.PIRS == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('lux_raw', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    t_raw(),
                    temp_c(),
                    binary('pir', '{% if value_json.PIRS == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('lux_raw', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx', enabled_by_default='false'),
                    sensor('lux', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    t_raw(),
                    temp_c(),
                    binary('pir', '{% if value_json.PIRS == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
        },
        9: {
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('humidity', vt('HUM'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('concentration', vt('Conc'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('temperature', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    binary('HSN', '{% if value_json.HSN == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('TSN', '{% if value_json.TSN == 0 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('conc', vt('Conc'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('tmp', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('tsn', vt('TSN'), state_class='measurement'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    sensor('conc', vt('Conc'), device_class='volatile_organic_compounds_parts', state_class='measurement', unit='ppb'),
                    sensor('voc_id', vt('VOC_ID'), device_class='volatile_organic_compounds_parts', state_class='measurement'),
                    sensor('scm', vt('SCM'), state_class='measurement'),
                ],
            },
            6: {
                'device_config': dcfg(),
                'entities': [
                    sensor('act', vt('Act'), state_class='measurement', unit='Bq/m3'),
                ],
            },
            7: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pm10', vt('PM10'), state_class='measurement', unit='µg/m3'),
                    sensor('pm2_5', "{{ value_json['PM2.5'] }}", state_class='measurement', unit='µg/m3'),
                    sensor('pm1', vt('PM1'), state_class='measurement', unit='µg/m3'),
                    sensor('pm10a', vt('PM10a'), state_class='measurement'),
                    sensor('pm2_5a', "{{ value_json['PM2.5a'] }}", state_class='measurement'),
                    sensor('pm1a', vt('PM1a'), state_class='measurement'),
                ],
            },
            8: {
                'device_config': dcfg(),
                'entities': [
                    sensor('co2', vt('CO2'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                ],
            },
            9: {
                'device_config': dcfg(),
                'entities': [
                    sensor('co2', vt('CO2'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('pfd', vt('PFD'), state_class='measurement'),
                ],
            },
            10: {
                'device_config': dcfg(),
                'entities': [
                    sensor('conc', vt('Conc'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('temp', vt('TEMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('sv', vt('SV'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('tsa', vt('TSA'), state_class='measurement'),
                    sensor('sva', vt('SVA'), device_class='voltage', state_class='measurement', unit='V'),
                ],
            },
            11: {
                'device_config': dcfg(),
                'entities': [
                    sensor('sv', vt('SV'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('ract', vt('Ract'), state_class='measurement', unit='According to'),
                    sensor('scm', vt('SCM'), state_class='measurement'),
                    sensor('vunit', vt('VUNIT'), state_class='measurement'),
                    sensor('sva', vt('SVA'), device_class='voltage', state_class='measurement', unit='V'),
                ],
            },
            12: {
                'device_config': dcfg(),
                'entities': [
                    sensor('conc', vt('Conc'), device_class='volatile_organic_compounds_parts', state_class='measurement'),
                    sensor('voc_id', "{{ value_json['VOC ID'] }}", device_class='volatile_organic_compounds_parts', state_class='measurement'),
                    sensor('unit', vt('Unit'), state_class='measurement'),
                    sensor('scm', vt('SCM'), state_class='measurement'),
                ],
            },
        },
        18: {
            0: {
                'device_config': dcfg(channel='DT'),
                'entities': [
                    entity('sensor', 'frequency', state_class='measurement', state_topic='DT1', value_template='{{ value_json.MR/(10**value_json.DIV) }}', device_class='frequency', unit_of_measurement='Hz'),
                    entity('sensor', 'counter', state_topic='DT0', state_class='total', value_template='{{ value_json.MR/(10**value_json.DIV) }}'),
                    entity('sensor', 'channel', state_topic='+', value_template=vt('CH', 'int(default=0)')),
                ],
            },
            1: {
                'device_config': dcfg(channel='DT'),
                'entities': [
                    entity('sensor', 'power', state_class='measurement', state_topic='DT1', value_template='{{ value_json.MR/(10**value_json.DIV) }}', device_class='power', unit_of_measurement='W'),
                    entity('sensor', 'energy', state_topic='DT0', state_class='total', value_template='{{ value_json.MR/(10**value_json.DIV) }}', device_class='energy', unit_of_measurement='kWh'),
                    entity('sensor', 'tariff', state_topic='+', value_template=vt('TI', 'int(default=0)')),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mr', vt('MR'), state_class='measurement'),
                    sensor('ti', vt('TI'), state_class='measurement', unit='1'),
                    sensor('dt', vt('DT'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mr', vt('MR'), state_class='measurement'),
                    sensor('ti', vt('TI'), state_class='measurement', unit='1'),
                    sensor('dt', vt('DT'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mr', vt('MR'), state_class='measurement', unit='gram'),
                    sensor('tmp', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('bl', vt('BL'), device_class='battery', state_class='measurement'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ps0', vt('PS0'), state_class='measurement'),
                    sensor('ps1', vt('PS1'), state_class='measurement'),
                    sensor('ps2', vt('PS2'), state_class='measurement'),
                    sensor('ps3', vt('PS3'), state_class='measurement'),
                    sensor('ps4', vt('PS4'), state_class='measurement'),
                    sensor('ps5', vt('PS5'), state_class='measurement'),
                    sensor('ps6', vt('PS6'), state_class='measurement'),
                    sensor('ps7', vt('PS7'), state_class='measurement'),
                    sensor('ps8', vt('PS8'), state_class='measurement'),
                    sensor('ps9', vt('PS9'), state_class='measurement'),
                    sensor('tmp', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('bl', vt('BL'), device_class='battery', state_class='measurement'),
                ],
            },
            16: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mr', vt('MR'), state_class='measurement'),
                    sensor('ch', vt('CH'), state_class='measurement'),
                    sensor('dt', vt('DT'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                ],
            },
        },
        20: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    binary('contact', '{% if value_json.CT == 0 %}OFF{% else %}ON{% endif %}', device_class='window'),
                ],
            },
            9: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    binary('state_2p', '{% if value_json.CT == 0 %}OFF{% else %}ON{% endif %}', device_class='window'),
                    sensor('state_3p', '{% if value_json.CT == 0 %}closed{% elif value_json.CT == 1 %}tilt{% elif value_json.CT == 3 %}open{% else %}reserved{% endif %}'),
                ],
            },
            10: {
                'device_config': dcfg(),
                'entities': [
                    sensor('v_raw', vt('SVC'), device_class='voltage', state_class='measurement', unit='V', enabled_by_default='false'),
                    sensor('voltage', vt('SVC', 'round(2)'), device_class='voltage', state_class='measurement', unit='V'),
                    binary('state_2p', '{% if value_json.CT == 0 %}OFF{% else %}ON{% endif %}', device_class='window'),
                    sensor('state_3p', '{% if value_json.CT == 0 %}closed{% elif value_json.CT == 1 %}tilt{% elif value_json.CT == 3 %}open{% else %}reserved{% endif %}'),
                    binary('vib', '{% if value_json.VIB == 1 %}ON{% else %}OFF{% endif %}', device_class='vibration'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    binary('ct', vt('CT'), device_class='opening'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('vib', vt('VIB'), state_class='measurement'),
                    binary('ct', vt('CT'), device_class='opening'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('vib', vt('VIB'), state_class='measurement'),
                    binary('ct', vt('CT'), device_class='opening'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('vib', vt('VIB'), state_class='measurement'),
                ],
            },
            6: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('vib', vt('VIB'), state_class='measurement'),
                ],
            },
            7: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    binary('dct', vt('DCT'), device_class='door'),
                    binary('lct', vt('LCT'), device_class='opening'),
                ],
            },
            8: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    binary('dct', vt('DCT'), device_class='door'),
                    binary('lct', vt('LCT'), device_class='opening'),
                    sensor('vib', vt('VIB'), state_class='measurement'),
                ],
            },
        },
        48: {
            3: {
                'device_config': dcfg(),
                'entities': [
                    t_raw(),
                    temp_c(),
                    binary('wake', '{% if value_json.WA0 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI3', '{% if value_json.DI3 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI2', '{% if value_json.DI2 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI1', '{% if value_json.DI1 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI0', '{% if value_json.DI0 == 0 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('value', vt('DV0')),
                    binary('DI2', '{% if value_json.DI2 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI1', '{% if value_json.DI1 == 0 %}OFF{% else %}ON{% endif %}'),
                    binary('DI0', '{% if value_json.DI0 == 0 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    svc(),
                    sensor('ips', vt('IPS'), state_class='measurement'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ips', vt('IPS'), state_class='measurement'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    sensor('vdd', vt('VDD'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('st', vt('ST'), state_class='measurement'),
                    sensor('ios', vt('IOS'), state_class='measurement'),
                ],
            },
        },
        17: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('isp', vt('ISP'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('dim', vt('DIM'), state_class='measurement', unit='N/A'),
                    sensor('rep', vt('REP'), state_class='measurement'),
                    sensor('prt', vt('PRT'), state_class='measurement'),
                    sensor('dhv', vt('DHV'), state_class='measurement'),
                    sensor('edim', vt('EDIM'), state_class='measurement'),
                    binary('mgc', vt('MGC'), device_class='opening'),
                    binary('occ', vt('OCC'), device_class='occupancy'),
                    sensor('pwr', vt('PWR'), state_class='measurement'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('cvar', vt('CVAR'), state_class='measurement', unit='%'),
                    sensor('fan', vt('FAN'), state_class='measurement'),
                    sensor('asp', vt('ASP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('alr', vt('ALR'), state_class='measurement'),
                    sensor('ctm', vt('CTM'), state_class='measurement'),
                    sensor('cst', vt('CST'), state_class='measurement'),
                    sensor('erh', vt('ERH'), device_class='energy', state_class='total_increasing'),
                    binary('ro', vt('RO'), device_class='occupancy'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('bsp', vt('BSP'), state_class='measurement', unit='%'),
                    sensor('as', vt('AS'), state_class='measurement'),
                    sensor('an', vt('AN'), state_class='measurement', unit='°'),
                    sensor('pvf', vt('PVF'), state_class='measurement'),
                    sensor('avf', vt('AVF'), state_class='measurement'),
                    sensor('es', vt('ES'), state_class='measurement'),
                    sensor('ep', vt('EP'), state_class='measurement'),
                    sensor('st', vt('ST'), state_class='measurement'),
                    sensor('sm', vt('SM'), state_class='measurement'),
                    sensor('motp', vt('MOTP'), state_class='measurement'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('p1', vt('P1'), state_class='measurement'),
                    sensor('p2', vt('P2'), state_class='measurement'),
                    sensor('p3', vt('P3'), state_class='measurement'),
                    sensor('sm', vt('SM'), state_class='measurement'),
                    sensor('ohf', vt('OHF'), state_class='measurement'),
                    sensor('es', vt('ES'), state_class='measurement'),
                    sensor('pm', vt('PM'), state_class='measurement'),
                    sensor('st', vt('ST'), state_class='measurement'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mt', vt('MT'), state_class='measurement'),
                    sensor('wm', vt('WM'), state_class='measurement'),
                    sensor('rs', vt('RS'), state_class='measurement'),
                ],
            },
        },
        55: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('drl', vt('DRL'), state_class='measurement', unit='N/A'),
                    sensor('tmpd', vt('TMPD'), state_class='measurement', unit='N/A'),
                    sensor('spwru', vt('SPWRU'), state_class='measurement'),
                    sensor('pwru', vt('PWRU'), state_class='measurement', unit='N/A'),
                    sensor('tmos', vt('TMOS'), state_class='measurement', unit='min'),
                    sensor('rsd', vt('RSD'), state_class='measurement'),
                    sensor('red', vt('RED'), state_class='measurement'),
                    sensor('mpwru', vt('MPWRU'), state_class='measurement'),
                ],
            },
        },
        5: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pressure', vt('BAR', 'round(1)'), device_class='atmospheric_pressure', state_class='measurement', unit='hPa'),
                    binary('event', '{% if value_json.TTP == 1 %}ON{% else %}OFF{% endif %}'),
                ],
            },
        },
    },
}
