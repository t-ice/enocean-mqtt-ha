"""Discovery MAPPING fragment: D2 (VLD) devices — covers, room panels, sensors, ventilation.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import binary, dcfg, entity, sensor, vt
from enocean2mqtt.homeassistant.mapping._catalog import cover_pair, hum, room_panel, temp_c

MAPPING = {
    210: {
        3: {
            10: {
                'device_config': {'command': '', 'channel': '', 'log_learn': ''},
                'entities': [
                    sensor('battery', vt('BATT'), device_class='battery', state_class='measurement', unit='%'),
                    entity('binary_sensor', 'single', state_topic='', value_template='{% if value_json.BA == 1 %}ON{% else %}OFF{% endif %}', enabled_by_default='false'),
                    entity('binary_sensor', 'double', state_topic='', value_template='{% if value_json.BA == 2 %}ON{% else %}OFF{% endif %}', enabled_by_default='false'),
                    entity('binary_sensor', 'long_press', state_topic='', value_template='{% if value_json.BA == 3 %}ON{% else %}OFF{% endif %}', enabled_by_default='false'),
                    entity('binary_sensor', 'long_released', state_topic='', value_template='{% if value_json.BA == 4 %}ON{% else %}OFF{% endif %}', enabled_by_default='false'),
                    entity('device_automation', 'trig_single', automation_type='trigger', type='button_short_press', subtype='button_1', topic='', payload='1', value_template=vt('BA')),
                    entity('device_automation', 'trig_double', automation_type='trigger', type='button_double_press', subtype='button_1', topic='', payload='2', value_template=vt('BA')),
                    entity('device_automation', 'trig_long_press', automation_type='trigger', type='button_long_press', subtype='button_1', topic='', payload='3', value_template=vt('BA')),
                    entity('device_automation', 'trig_long_released', automation_type='trigger', type='button_long_release', subtype='button_1', topic='', payload='4', value_template=vt('BA')),
                ],
            },
            16: {
                'device_config': dcfg(),
                'entities': [
                    binary('window', '{% if value_json.WIN == 2 %}OFF{% else %}ON{% endif %}', device_class='window'),
                    sensor('handle', "{% set v = value_json.WIN | int %}{{ ['?','open (from tilted)','closed','open','tilted'][v] if v < 5 else v }}", icon='mdi:window-closed-variant'),
                ],
            },
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('action', vt('RI2'), icon='mdi:gesture-tap-button'),
                ],
            },
        },
        5: {
            0: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': cover_pair(),
            },
            2: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': cover_pair(),
            },
            1: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': cover_pair(),
            },
            4: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': cover_pair(),
            },
            5: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': cover_pair(),
            },
        },
        20: {
            48: {
                'device_config': dcfg(),
                'entities': [
                    binary('alarm', '{% if value_json.SMA0 == 1 %}ON{% else %}OFF{% endif %}', device_class='smoke'),
                    binary('fault_mode', '{% if value_json.SMA1 == 1 %}ON{% else %}OFF{% endif %}'),
                    entity('binary_sensor', 'maintenance', state_topic='', value_template='{% if value_json.SMA2 == 1 %}ON{% else %}OFF{% endif %}', device_class='problem', icon='mdi:tools'),
                    entity('binary_sensor', 'humidity_range', state_topic='', value_template='{% if value_json.SMA3 == 1 %}ON{% else %}OFF{% endif %}', device_class='problem', icon='mdi:water-percent-alert'),
                    entity('binary_sensor', 'temperature_range', state_topic='', value_template='{% if value_json.SMA4 == 1 %}ON{% else %}OFF{% endif %}', device_class='problem', icon='mdi:thermometer-alert'),
                    sensor('last_maintenance', vt('SMA5'), unit='week', icon='mdi:wrench-clock'),
                    sensor('energy', '{% if value_json.ES == 0 %}High {% elif value_json.ES == 1 %}Medium {% elif value_json.ES == 2 %}Low {% else %}Critical {% endif %}', icon='mdi:battery-heart'),
                    sensor('end_of_life', vt('RPLT'), unit='month', icon='mdi:calendar-clock'),
                    sensor('temperature', vt('TMP8', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('humidity', vt('HUM', 'round(1)'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('comfort', '{% if value_json.HCI == 0 %}Good {% elif value_json.HCI == 1 %}Medium {% elif value_json.HCI == 2 %}Bad {% else %}Error {% endif %}', icon='mdi:sofa'),
                    sensor('air_quality', '{% if value_json.IAQTH == 0 %}Optimal {% elif value_json.IAQTH == 1 %}Dry {% elif value_json.IAQTH == 2 %}High humidity {% elif value_json.IAQTH == 3 %}High temperature and humidity {% elif value_json.IAQTH == 4 %}Out of range {% else %}Error {% endif %}', icon='mdi:weather-windy'),
                ],
            },
            65: {
                'device_config': dcfg(),
                'entities': [
                    sensor('tmp', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('hum', vt('HUM'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('acc', vt('ACC'), state_class='measurement'),
                    sensor('acx', vt('ACX'), state_class='measurement', unit='g'),
                    sensor('acy', vt('ACY'), state_class='measurement', unit='g'),
                    sensor('acz', vt('ACZ'), state_class='measurement', unit='g'),
                    binary('co', vt('CO'), device_class='opening'),
                ],
            },
            64: {
                'device_config': dcfg(),
                'entities': [
                    sensor('tmp', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('hum', vt('HUM'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('ill', vt('ILL'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('acc', vt('ACC'), state_class='measurement'),
                    sensor('acx', vt('ACX'), state_class='measurement', unit='g'),
                    sensor('acy', vt('ACY'), state_class='measurement', unit='g'),
                    sensor('acz', vt('ACZ'), state_class='measurement', unit='g'),
                ],
            },
        },
        80: {
            0: {
                'device_config': dcfg(command='MT', channel='MT'),
                'entities': [
                    entity('button', 'query_basic_status', command_topic='req', payload_press='{"MT":"0","RMT":"0","send":"clear"}'),
                    entity('button', 'query_extended_status', command_topic='req', payload_press='{"MT":"0","RMT":"1","send":"clear"}'),
                    entity('select', 'operating_mode', options=['Off', 'Level 1', 'Level 2', 'Level 3', 'Level 4', 'Automatic', 'Automatic on demand', 'Supply air only', 'Exhaust air only'], command_topic='req', command_template='{% set modes = {"Off": "0", "Level 1": "1", "Level 2": "2", "Level 3": "3", "Level 4": "4", "Automatic": "11", "Automatic on demand": 12, "Supply air only": 13, "Exhaust air only": 14} %} {"MT":"1","DOMC":"{{modes[value]}}","OMC":"0","TOMC":"0","COT":"127","HT":"127","AQT":"127","send":"clear"}', state_topic='MT2', value_template='{% set modes = {0: "Off", 1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4", 11: "Automatic", 12: "Automatic on demand", 13: "Supply air only", 14: "Exhaust air only"} %} {{ modes[value_json.OMS] }}', icon='mdi:hvac'),
                    entity('sensor', 't_outdoor', state_topic='MT2', value_template=vt('OUTT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_supply', state_topic='MT2', value_template=vt('SPLYT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 'supply_air_flow', state_topic='MT2', value_template=vt('SPLYFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'exhaust_air_flow', state_topic='MT2', value_template=vt('EXHFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'supply_fan_speed', state_topic='MT2', value_template=vt('SPLYFS'), unit_of_measurement='rpm'),
                    entity('sensor', 'exhaust_fan_speed', state_topic='MT2', value_template=vt('EXHFS'), unit_of_measurement='rpm'),
                ],
            },
            1: {
                'device_config': dcfg(command='MT', channel='MT'),
                'entities': [
                    entity('button', 'query_basic_status', command_topic='req', payload_press='{"MT":"0","RMT":"0","send":"clear"}'),
                    entity('button', 'query_extended_status', command_topic='req', payload_press='{"MT":"0","RMT":"1","send":"clear"}'),
                    entity('select', 'operating_mode', options=['Off', 'Level 1', 'Level 2', 'Level 3', 'Level 4', 'Automatic', 'Automatic on demand', 'Supply air only', 'Exhaust air only'], command_topic='req', command_template='{% set modes = {"Off": "0", "Level 1": "1", "Level 2": "2", "Level 3": "3", "Level 4": "4", "Automatic": "11", "Automatic on demand": 12, "Supply air only": 13, "Exhaust air only": 14} %} {"MT":"1","DOMC":"{{modes[value]}}","OMC":"0","TOMC":"0","COT":"127","HT":"127","AQT":"127","send":"clear"}', state_topic='MT2', value_template='{% set modes = {0: "Off", 1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4", 11: "Automatic", 12: "Automatic on demand", 13: "Supply air only", 14: "Exhaust air only"} %} {{ modes[value_json.OMS] }}', icon='mdi:hvac'),
                    entity('sensor', 't_outdoor', state_topic='MT2', value_template=vt('OUTT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_supply', state_topic='MT2', value_template=vt('SPLYT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 'supply_air_flow', state_topic='MT2', value_template=vt('SPLYFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'exhaust_air_flow', state_topic='MT2', value_template=vt('EXHFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'supply_fan_speed', state_topic='MT2', value_template=vt('SPLYFS'), unit_of_measurement='rpm'),
                    entity('sensor', 'exhaust_fan_speed', state_topic='MT2', value_template=vt('EXHFS'), unit_of_measurement='rpm'),
                ],
            },
            16: {
                'device_config': dcfg(command='MT', channel='MT'),
                'entities': [
                    entity('button', 'query_basic_status', command_topic='req', payload_press='{"MT":"0","RMT":"0","send":"clear"}'),
                    entity('button', 'query_extended_status', command_topic='req', payload_press='{"MT":"0","RMT":"1","send":"clear"}'),
                    entity('select', 'operating_mode', options=['Off', 'Level 1', 'Level 2', 'Level 3', 'Level 4', 'Automatic', 'Automatic on demand', 'Supply air only', 'Exhaust air only'], command_topic='req', command_template='{% set modes = {"Off": "0", "Level 1": "1", "Level 2": "2", "Level 3": "3", "Level 4": "4", "Automatic": "11", "Automatic on demand": 12, "Supply air only": 13, "Exhaust air only": 14} %} {"MT":"1","DOMC":"{{modes[value]}}","OMC":"0","TOMC":"0","COT":"127","HT":"127","AQT":"127","RTT":"0","send":"clear"}', state_topic='MT2', value_template='{% set modes = {0: "Off", 1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4", 11: "Automatic", 12: "Automatic on demand", 13: "Supply air only", 14: "Exhaust air only"} %} {{ modes[value_json.OMS] }}', icon='mdi:hvac'),
                    entity('sensor', 't_outdoor', state_topic='MT2', value_template=vt('OUTT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_supply', state_topic='MT2', value_template=vt('SPLYT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_indoor', state_topic='MT2', value_template=vt('INT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_exhaust', state_topic='MT2', value_template=vt('EXHT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 'supply_air_flow', state_topic='MT2', value_template=vt('SPLYFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'exhaust_air_flow', state_topic='MT2', value_template=vt('EXHFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'supply_fan_speed', state_topic='MT2', value_template=vt('SPLYFS'), unit_of_measurement='rpm'),
                    entity('sensor', 'exhaust_fan_speed', state_topic='MT2', value_template=vt('EXHFS'), unit_of_measurement='rpm'),
                ],
            },
            17: {
                'device_config': dcfg(command='MT', channel='MT'),
                'entities': [
                    entity('button', 'query_basic_status', command_topic='req', payload_press='{"MT":"0","RMT":"0","send":"clear"}'),
                    entity('button', 'query_extended_status', command_topic='req', payload_press='{"MT":"0","RMT":"1","send":"clear"}'),
                    entity('select', 'operating_mode', options=['Off', 'Level 1', 'Level 2', 'Level 3', 'Level 4', 'Automatic', 'Automatic on demand', 'Supply air only', 'Exhaust air only'], command_topic='req', command_template='{% set modes = {"Off": "0", "Level 1": "1", "Level 2": "2", "Level 3": "3", "Level 4": "4", "Automatic": "11", "Automatic on demand": 12, "Supply air only": 13, "Exhaust air only": 14} %} {"MT":"1","DOMC":"{{modes[value]}}","OMC":"0","HBC":"0","TOMC":"0","COT":"127","HT":"127","AQT":"127","RTT":"0","send":"clear"}', state_topic='MT2', value_template='{% set modes = {0: "Off", 1: "Level 1", 2: "Level 2", 3: "Level 3", 4: "Level 4", 11: "Automatic", 12: "Automatic on demand", 13: "Supply air only", 14: "Exhaust air only"} %} {{ modes[value_json.OMS] }}', icon='mdi:hvac'),
                    entity('sensor', 't_outdoor', state_topic='MT2', value_template=vt('OUTT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_supply', state_topic='MT2', value_template=vt('SPLYT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_indoor', state_topic='MT2', value_template=vt('INT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 't_exhaust', state_topic='MT2', value_template=vt('EXHT'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 'supply_air_flow', state_topic='MT2', value_template=vt('SPLYFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'exhaust_air_flow', state_topic='MT2', value_template=vt('EXHFF'), unit_of_measurement='m3/h'),
                    entity('sensor', 'supply_fan_speed', state_topic='MT2', value_template=vt('SPLYFS'), unit_of_measurement='rpm'),
                    entity('sensor', 'exhaust_fan_speed', state_topic='MT2', value_template=vt('EXHFS'), unit_of_measurement='rpm'),
                ],
            },
        },
        0: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mi', vt('MI'), state_class='measurement'),
                    sensor('kp', vt('KP'), state_class='measurement'),
                    sensor('cv', vt('CV'), state_class='measurement'),
                    sensor('md', vt('MD'), state_class='measurement'),
                    sensor('f', vt('F'), state_class='measurement'),
                    sensor('m', vt('M'), state_class='measurement'),
                    sensor('ta', vt('TA'), state_class='measurement'),
                    binary('pr', vt('PR'), device_class='occupancy'),
                    sensor('za', vt('ZA'), state_class='measurement'),
                    sensor('sa', vt('Sa'), state_class='measurement'),
                    sensor('sb', vt('Sb'), state_class='measurement'),
                    sensor('sc', vt('Sc'), state_class='measurement'),
                    binary('sd', vt('Sd'), device_class='window'),
                    sensor('se', vt('Se'), state_class='measurement'),
                    sensor('va__lsb', "{{ value_json['VA (LSB)'] }}", state_class='measurement', unit='°'),
                    sensor('spr', vt('SPR'), state_class='measurement'),
                    sensor('sps', vt('SPS'), state_class='measurement'),
                    sensor('tt__lsb', "{{ value_json['TT (LSB)'] }}", state_class='measurement'),
                    sensor('ka', vt('KA'), state_class='measurement'),
                    sensor('st', vt('ST'), state_class='measurement', unit='°'),
                ],
            },
        },
        10: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('bl', vt('BL'), device_class='battery', state_class='measurement'),
                    sensor('ch1', vt('CH1'), state_class='measurement'),
                    sensor('ch2', vt('CH2'), state_class='measurement'),
                    sensor('ch3', vt('CH3'), state_class='measurement'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('bl', vt('BL'), device_class='battery', state_class='measurement'),
                    sensor('ch1', vt('CH1'), state_class='measurement'),
                    sensor('ch2', vt('CH2'), state_class='measurement'),
                    sensor('ch3', vt('CH3'), state_class='measurement'),
                ],
            },
        },
        49: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('rm', vt('RM'), state_class='measurement'),
                    sensor('cmd', vt('CMD'), state_class='measurement'),
                    sensor('bus', vt('BUS'), state_class='measurement'),
                    sensor('mch', vt('MCH'), state_class='measurement', unit='1'),
                    sensor('unit1', vt('UNIT1'), state_class='measurement'),
                    sensor('unit2', vt('UNIT2'), state_class='measurement'),
                    sensor('addr', vt('ADDR'), state_class='measurement', unit='1'),
                    sensor('facp', vt('FACP'), state_class='measurement'),
                    sensor('nop', vt('NOP'), state_class='measurement'),
                    sensor('rst', vt('RST'), state_class='measurement'),
                    sensor('prot', vt('PROT'), state_class='measurement'),
                    sensor('mstat', vt('MSTAT'), state_class='measurement'),
                    sensor('vsel', vt('VSEL'), state_class='measurement'),
                    sensor('vunit', vt('VUNIT'), state_class='measurement'),
                    sensor('val', vt('VAL'), state_class='measurement', unit='According to VUNIT'),
                ],
            },
        },
        50: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pf', vt('PF'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                    sensor('ch1', vt('CH1'), device_class='current', state_class='measurement', unit='A'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pf', vt('PF'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                    sensor('ch1', vt('CH1'), device_class='current', state_class='measurement', unit='A'),
                    sensor('ch2', vt('CH2'), device_class='current', state_class='measurement', unit='A'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pf', vt('PF'), state_class='measurement'),
                    sensor('div', vt('DIV'), state_class='measurement'),
                    sensor('ch1', vt('CH1'), device_class='current', state_class='measurement', unit='A'),
                    sensor('ch2', vt('CH2'), device_class='current', state_class='measurement', unit='A'),
                    sensor('ch3', vt('CH3'), device_class='current', state_class='measurement', unit='A'),
                ],
            },
        },
        51: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('mid', vt('MID'), state_class='measurement'),
                    sensor('req', vt('REQ'), state_class='measurement'),
                    sensor('ext', vt('EXT'), device_class='temperature', state_class='measurement', unit='°C'),
                    binary('wos', vt('WOS'), device_class='window'),
                    binary('pis', vt('PIS'), device_class='motion'),
                    sensor('rts', vt('RTS'), state_class='measurement'),
                    sensor('cvs', vt('CVS'), state_class='measurement'),
                    sensor('cos', vt('COS'), state_class='measurement'),
                    sensor('c2s', vt('C2S'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('p1s', vt('P1S'), state_class='measurement'),
                    sensor('p2s', vt('P2S'), state_class='measurement'),
                    sensor('p10s', vt('P10S'), state_class='measurement'),
                    sensor('ras', vt('RAS'), state_class='measurement'),
                    sensor('sos', vt('SOS'), state_class='measurement'),
                    sensor('hys', vt('HYS'), state_class='measurement'),
                    sensor('ams', vt('AMS'), state_class='measurement'),
                    sensor('prs', vt('PRS'), state_class='measurement'),
                    sensor('tss', vt('TSS'), state_class='measurement'),
                    sensor('tns', vt('TNS'), state_class='measurement'),
                    sensor('dcs', vt('DCS'), state_class='measurement'),
                    sensor('dgs', vt('DGS'), state_class='measurement'),
                    sensor('tpt', vt('TPT'), state_class='measurement'),
                    sensor('etd', vt('ETD'), state_class='measurement'),
                    sensor('etm', vt('ETM'), state_class='measurement', unit='Min'),
                    sensor('eth', vt('ETH'), state_class='measurement', unit='Hour'),
                    sensor('std', vt('STD'), state_class='measurement'),
                    sensor('stm', vt('STM'), state_class='measurement', unit='Min'),
                    sensor('sth', vt('STH'), state_class='measurement', unit='Hour'),
                    sensor('tsp', vt('TSP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('csc', vt('CSC'), state_class='measurement'),
                    sensor('day', vt('DAY'), state_class='measurement', unit='Day'),
                    sensor('mon', vt('MON'), state_class='measurement', unit='Mon'),
                    sensor('yr', vt('YR'), state_class='measurement', unit='Year'),
                    sensor('min', vt('MIN'), state_class='measurement', unit='Min'),
                    sensor('hr', vt('HR'), state_class='measurement', unit='Hour'),
                    sensor('dayw', vt('DAYW'), state_class='measurement'),
                    sensor('erf', vt('ERF'), state_class='measurement'),
                    sensor('htf', vt('HTF'), state_class='measurement'),
                    sensor('pwf', vt('PWF'), state_class='measurement'),
                    binary('wof', vt('WOF'), device_class='window'),
                    binary('pif', vt('PIF'), device_class='motion'),
                    sensor('klu', vt('KLU'), state_class='measurement'),
                    sensor('rtf', vt('RTF'), state_class='measurement'),
                    sensor('dgf', vt('DGF'), state_class='measurement'),
                    sensor('int', vt('INT'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('em', vt('EM'), device_class='energy', state_class='total_increasing', unit='kWh'),
                    sensor('dts', vt('DTS'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('fwv', vt('FWV'), state_class='measurement', unit='-'),
                    sensor('cvv', vt('CVV'), device_class='volatile_organic_compounds_parts', state_class='measurement', unit='ppb'),
                    sensor('voct', vt('VOCT'), device_class='volatile_organic_compounds_parts', state_class='measurement', unit='ppm'),
                    sensor('c2v', vt('C2V'), device_class='carbon_dioxide', state_class='measurement', unit='ppm'),
                    sensor('sov', vt('SOV'), state_class='measurement', unit='dB'),
                    sensor('pm1', vt('PM1'), state_class='measurement', unit='μg/m3'),
                    sensor('pm2', vt('PM2'), state_class='measurement', unit='μg/m3'),
                    sensor('pm10', vt('PM10'), state_class='measurement', unit='μg/m3'),
                    sensor('rav', vt('RAV'), state_class='measurement', unit='μSv/h'),
                    sensor('amv', vt('AMV'), device_class='wind_speed', state_class='measurement', unit='m/s'),
                    sensor('prv', vt('PRV'), device_class='atmospheric_pressure', state_class='measurement', unit='hPa'),
                    sensor('hyv', vt('HYV'), state_class='measurement', unit='%'),
                ],
            },
        },
        52: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('chn', vt('CHN'), state_class='measurement'),
                    sensor('cmd', vt('CMD'), state_class='measurement'),
                    sensor('tmp', vt('TMP'), state_class='measurement'),
                    sensor('sp', vt('SP'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('opm', vt('OPM'), state_class='measurement'),
                    sensor('cfg', vt('CFG'), state_class='measurement'),
                    sensor('dur', vt('DUR'), state_class='measurement'),
                    sensor('shf', vt('SHF'), device_class='temperature', state_class='measurement', unit='K'),
                    sensor('ovr', vt('OVR'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('pnl', vt('PNL'), device_class='temperature', state_class='measurement', unit='°C'),
                ],
            },
        },
        64: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('outen', vt('OUTEN'), state_class='measurement'),
                    sensor('dra', vt('DRA'), state_class='measurement'),
                    sensor('dhar', vt('DHAR'), state_class='measurement'),
                    binary('occ', vt('OCC'), device_class='occupancy'),
                    sensor('sreas', vt('SREAS'), state_class='measurement'),
                    sensor('mi', vt('MI'), state_class='measurement'),
                    sensor('dlvl', vt('DLVL'), state_class='measurement'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('outen', vt('OUTEN'), state_class='measurement'),
                    sensor('dra', vt('DRA'), state_class='measurement'),
                    sensor('dhar', vt('DHAR'), state_class='measurement'),
                    binary('occ', vt('OCC'), device_class='occupancy'),
                    sensor('sreas', vt('SREAS'), state_class='measurement'),
                    sensor('mi', vt('MI'), state_class='measurement'),
                    sensor('dlvlr', vt('DLVLR'), state_class='measurement'),
                    sensor('dlvlg', vt('DLVLG'), state_class='measurement'),
                    sensor('dlvlb', vt('DLVLB'), state_class='measurement'),
                ],
            },
        },
        160: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('fdb', vt('FDB'), state_class='measurement'),
                    sensor('req', vt('REQ'), state_class='measurement'),
                ],
            },
        },
        176: {
            81: {
                'device_config': dcfg(),
                'entities': [
                    sensor('wa', vt('WA'), state_class='measurement'),
                ],
            },
        },
        32: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('fan_speed', vt('FSS'), unit='%', icon='mdi:fan'),
                    sensor('humidity', vt('HUM'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('operating_mode', vt('OMS'), icon='mdi:tune'),
                ],
            },
        },
        6: {
            64: {
                'device_config': dcfg(),
                'entities': [
                    sensor('handle', "{% set m = {0: 'closed', 1: 'open', 2: 'tilted', 3: 'unknown'} %}{{ m.get(value_json.HS | int, value_json.HS) }}"),
                    sensor('mechanics', "{% set m = {0: 'OK', 1: 'error'} %}{{ m.get(value_json.MEC | int, value_json.MEC) }}"),
                    sensor('lock', "{% set m = {0: 'unlocked', 1: 'locked', 2: 'unknown'} %}{{ m.get(value_json.LCK | int, value_json.LCK) }}"),
                    sensor('unlock_query', "{% set m = {0: 'not requested', 1: 'requested'} %}{{ m.get(value_json.ULQ | int, value_json.ULQ) }}"),
                    sensor('unlock_reply', "{% set m = {0: 'not allowed', 1: 'allowed'} %}{{ m.get(value_json.ULR | int, value_json.ULR) }}"),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('handle', "{% set m = {1: 'up', 2: 'down', 3: 'left', 4: 'right'} %}{{ m.get(value_json.HND | int, value_json.HND) }}"),
                    sensor('sash', "{% set m = {1: 'not tilted', 2: 'tilted'} %}{{ m.get(value_json.SASH | int, value_json.SASH) }}"),
                    temp_c(),
                    hum(),
                    sensor('illumination', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('battery', vt('BAT', 'round(1)'), device_class='battery', unit='%'),
                ],
            },
            80: {
                'device_config': dcfg(),
                'entities': [
                    sensor('hnd', vt('HND')),
                    sensor('battery', vt('BAT', 'round(1)'), device_class='battery', unit='%'),
                ],
            },
        },
        16: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    hum(),
                    sensor('fan_speed', vt('FS', 'round(1)'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('motion', "{% set m = {1: 'no movement', 2: 'movement', 3: 'locked'} %}{{ m.get(value_json.PIR | int, value_json.PIR) }}"),
                    sensor('window', "{% set m = {0: 'no change', 1: 'closed', 2: 'open'} %}{{ m.get(value_json.WOD | int, value_json.WOD) }}"),
                    sensor('battery_state', "{% set m = {1: 'good', 2: 'low', 3: 'critical'} %}{{ m.get(value_json.BS | int, value_json.BS) }}"),
                    sensor('mode', "{% set m = {0: 'comfort', 1: 'economy', 2: 'pre-comfort', 3: 'building protection'} %}{{ m.get(value_json.RCM | int, value_json.RCM) }}"),
                    sensor('setpoint_temp', vt('TSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    temp_c(),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('window', "{% set m = {0: 'no change', 1: 'closed', 2: 'open'} %}{{ m.get(value_json.WOD | int, value_json.WOD) }}"),
                    sensor('battery_state', "{% set m = {1: 'good', 2: 'low', 3: 'critical'} %}{{ m.get(value_json.BS | int, value_json.BS) }}"),
                    sensor('mode', "{% set m = {0: 'comfort', 1: 'economy', 2: 'pre-comfort', 3: 'building protection'} %}{{ m.get(value_json.RCM | int, value_json.RCM) }}"),
                    sensor('setpoint_temp', vt('TSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    temp_c(),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('motion', "{% set m = {1: 'no movement', 2: 'movement', 3: 'locked'} %}{{ m.get(value_json.PIR | int, value_json.PIR) }}"),
                    sensor('window', "{% set m = {0: 'no change', 1: 'closed', 2: 'open'} %}{{ m.get(value_json.WOD | int, value_json.WOD) }}"),
                    sensor('battery_state', "{% set m = {1: 'good', 2: 'low', 3: 'critical'} %}{{ m.get(value_json.BS | int, value_json.BS) }}"),
                    sensor('mode', "{% set m = {0: 'comfort', 1: 'economy', 2: 'pre-comfort', 3: 'building protection'} %}{{ m.get(value_json.RCM | int, value_json.RCM) }}"),
                    sensor('setpoint_temp', vt('TSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    temp_c(),
                ],
            },
        },
        17: {
            1: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            2: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            3: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            4: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            5: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            6: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            7: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
            8: {
                'device_config': dcfg(),
                'entities': room_panel(),
            },
        },
    },
}
