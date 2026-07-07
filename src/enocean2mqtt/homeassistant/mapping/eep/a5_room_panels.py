"""Discovery MAPPING fragment: A5-10 room operating panels.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import binary, dcfg, entity, sensor, vt
from enocean2mqtt.homeassistant.mapping._catalog import TMPL_FAN_LABELS, TMPL_FAN_SPEED, hum, setpoint, t_raw, temp_c

MAPPING = {
    165: {
        16: {
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('setpoint', vt('SP')),
                    sensor('setpoint_c', '{{ (value_json.SP | float * 40 / 255) | round(1) }}', device_class='temperature', state_class='measurement', unit='°C'),
                    t_raw(),
                    sensor('tempC', vt('TMP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                ],
            },
            5: {
                'device_config': dcfg(),
                'entities': [
                    sensor('setpoint', vt('SP')),
                    sensor('setpoint_c', '{{ (value_json.SP | float * 40 / 255) | round(1) }}', device_class='temperature', state_class='measurement', unit='°C'),
                    t_raw(),
                    temp_c(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            6: {
                'device_config': dcfg(),
                'entities': [
                    sensor('setpoint', vt('SP')),
                    sensor('setpoint_c', '{{ (value_json.SP | float * 40 / 255) | round(1) }}', device_class='temperature', state_class='measurement', unit='°C'),
                    t_raw(),
                    temp_c(),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
                'virtual': [
                    entity('number', 'setpoint', command_topic='__trash', min='0', max='255', step='1', mode='box'),
                    entity('number', 'temperature', command_topic='__trash', min='0', max='40', step='0.1', mode='box', unit_of_measurement='°C', icon='mdi:thermometer'),
                    entity('switch', 'slide_switch', command_topic='__trash'),
                    entity('button', 'send', command_topic='req', command_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'slide_switch\',ignorecase=True) %}\n    {% if is_state(entity, "on") %}{% set ns.SLSW = 1 %}{% else %}{% set ns.SLSW = 0 %}{% endif %}\n  {% elif entity is search(\'setpoint\',ignorecase=True) %}\n    {% set ns.SP = (states(entity)|int)|int(default=128) %}\n  {% elif entity is search(\'temperature\',ignorecase=True) %}\n    {% set ns.TMP = (40-(states(entity)|float(default=20))*255/40)|int %}\n  {% endif %}\n{% endfor %} {"SP":"{{ns.SP}}","TMP":"{{ns.TMP}}","SLSW":"{{ns.SLSW}}","send":"clear"}', icon='mdi:send'),
                ],
            },
            16: {
                'device_config': dcfg(),
                'entities': [
                    sensor('setpoint', vt('SP')),
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            18: {
                'device_config': dcfg(),
                'entities': [
                    sensor('setpoint', vt('SP')),
                    sensor('h_raw', vt('HUM'), device_class='humidity', state_class='measurement', unit='%', enabled_by_default='false'),
                    hum(),
                    t_raw(),
                    temp_c(),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                ],
            },
            7: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                ],
            },
            8: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            9: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            10: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    binary('contact', '{% if value_json.CTST == 1 %}ON{% else %}OFF{% endif %}', device_class='opening'),
                ],
            },
            11: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    binary('contact', '{% if value_json.CTST == 1 %}ON{% else %}OFF{% endif %}', device_class='opening'),
                ],
            },
            12: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            13: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            17: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    setpoint(),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            19: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            20: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    binary('nightmode', '{% if value_json.SLSW == 1 %}OFF{% else %}ON{% endif %}'),
                ],
            },
            21: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                ],
            },
            22: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            23: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
            24: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('setpoint_temp', vt('TMPSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('illumination', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            25: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    sensor('setpoint_temp', vt('TMPSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            26: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('setpoint_temp', vt('TMPSP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C'),
                    sensor('voltage', vt('SV', 'round(1)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            27: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('illumination', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('voltage', vt('SV', 'round(1)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            28: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('setpoint_ill', vt('ILLSP', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('illumination', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            29: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    sensor('setpoint_hum', vt('HUMSP', 'round(1)'), device_class='humidity', state_class='measurement', unit='%'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            30: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    sensor('illumination', vt('ILL', 'round(1)'), device_class='illuminance', state_class='measurement', unit='lx'),
                    sensor('voltage', vt('SV', 'round(1)'), device_class='voltage', state_class='measurement', unit='V'),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OB == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('occ_enabled', '{% if value_json.OED == 0 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            31: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_SPEED, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                    binary('unoccupied', '{% if value_json.UNOCC == 1 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            32: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    setpoint(),
                    sensor('setpoint_mode', "{% set v = value_json.SPM | int %}{{ ['room set point','frost protection','automatic','reserved'][v] if v < 4 else v }}", icon='mdi:tune'),
                    binary('activity', '{% if value_json.ACT == 1 %}ON{% else %}OFF{% endif %}'),
                    binary('battery_low', '{% if value_json.BATT == 1 %}ON{% else %}OFF{% endif %}', device_class='battery'),
                ],
            },
            33: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    setpoint(),
                    sensor('setpoint_mode', "{% set v = value_json.SPM | int %}{{ ['room set point','frost protection','automatic','reserved'][v] if v < 4 else v }}", icon='mdi:tune'),
                    binary('activity', '{% if value_json.ACT == 1 %}ON{% else %}OFF{% endif %}'),
                    binary('battery_low', '{% if value_json.BATT == 1 %}ON{% else %}OFF{% endif %}', device_class='battery'),
                ],
            },
            34: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                ],
            },
            35: {
                'device_config': dcfg(),
                'entities': [
                    temp_c(),
                    hum(),
                    setpoint(),
                    sensor('fan_speed', TMPL_FAN_LABELS, icon='mdi:fan'),
                    binary('occ', '{% if value_json.OCC == 0 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
                ],
            },
        },
    },
}
