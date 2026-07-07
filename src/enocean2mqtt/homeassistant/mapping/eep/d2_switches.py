"""Discovery MAPPING fragment: D2-01 switches, dimmers and metering.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import dcfg, entity, sensor, vt
from enocean2mqtt.homeassistant.mapping._catalog import d2_metering, d2_switch_basic, energy, lc_contact, outlet_switch, power, query_energy, query_power, query_status, reset_meas

MAPPING = {
    210: {
        1: {
            1: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            9: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': [
                    outlet_switch(),
                    energy(),
                    power(),
                    query_energy(),
                    query_power(),
                    query_status(),
                    reset_meas(),
                    entity('select', 'meas_type', options=['Query only - Energy in Ws', 'Query only - Energy in Wh', 'Query only - Energy in KWh', 'Query only - Power in W', 'Query only - Power in KW', 'Query & Auto - Energy in Ws', 'Query & Auto - Energy in Wh', 'Query & Auto - Energy in KWh', 'Query & Auto - Power in W', 'Query & Auto - Power in KW'], command_topic='__trash', icon='mdi:tune'),
                    entity('number', 'meas_MAT', command_topic='__trash', min='10', max='2550', step='10', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MIT', command_topic='__trash', min='1', max='255', step='1', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MD', command_topic='__trash', min='0', max='4095', step='1', mode='box', icon='mdi:equalizer'),
                    entity('button', 'set_meas', command_topic='req', command_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'meas_type\',ignorecase=True) %}\n    {% if states(entity) is search (\'only\') %}{% set ns.RM = 0 %}{% else %}{% set ns.RM = 1 %}{% endif %}\n    {% if states(entity) is search (\'Energy\') %}{% set ns.ep = 0 %}{% else %}{% set ns.ep = 1 %}{% endif %}\n    {% if states(entity) is search (\'KWh\') %}{% set ns.UN = 2 %}\n    {% elif states(entity) is search (\' KW\') %}{% set ns.UN = 4 %}\n    {% elif states(entity) is search (\' Wh\') %}{% set ns.UN = 1 %}\n    {% elif states(entity) is search (\' Ws\') %}{% set ns.UN = 0 %}\n    {% else %}{% set ns.UN = 3 %}\n    {% endif %}\n  {% elif entity is search(\'reset_meas\',ignorecase=True) %}\n    {% if is_state(entity, "on") %}{% set ns.RE = 1 %}{% else %}{% set ns.RE = 0 %}{% endif %}\n  {% elif entity is search(\'meas_mat\',ignorecase=True) %}\n    {% set ns.MAT = (states(entity)|int /10)|int(default=10) %}\n  {% elif entity is search(\'meas_mit\',ignorecase=True) %}\n    {% set ns.MIT = states(entity)|int(default=1) %}\n  {% elif entity is search(\'meas_md\',ignorecase=True) %}\n    {% set ns.MD_MSB = (states(entity)|int/16)|int(default=0) %}\n    {% set ns.MD_LSB = (states(entity)|int%16)|int(default=0) %}\n  {% endif %}\n{% endfor %} {"CMD":"5","RM":"{{ns.RM}}","RE":"{{ns.RE}}","ep":"{{ns.ep}}","IO":"0","MD_LSB":"{{ns.MD_LSB}}","UN":"{{ns.UN}}","MD_MSB":"{{ns.MD_MSB}}","MAT":"{{ns.MAT}}","MIT":"{{ns.MIT}}", "send":"clear"}', icon='mdi:download'),
                    entity('binary_sensor', 'OC', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.OC == 1 %}on{% else %}off{% endif %}'),
                    lc_contact(),
                ],
            },
            10: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': [
                    outlet_switch(),
                    query_status(),
                    entity('binary_sensor', 'PF', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.PF == 1 %}on{% else %}off{% endif %}'),
                    entity('binary_sensor', 'PFD', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.PFD == 1 %}on{% else %}off{% endif %}'),
                    lc_contact(),
                ],
            },
            11: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            12: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': [
                    entity('select', 'mode', options=['Off', 'Comfort', 'Eco', 'Anti-freeze', 'Comfort-1', 'Comfort-2'], command_topic='req', command_template='{% set modes = {"Off": "0", "Comfort": "1", "Eco": "2", "Anti-freeze": "3", "Comfort-1": "4", "Comfort-2": "5"} %} {"CMD":"8","PM":"{{modes[value]}}","send":"clear"}', state_topic='CMD10', value_template='{% set modes = {0: "Off", 1: "Comfort", 2: "Eco", 3: "Anti-freeze", 4: "Comfort-1", 5: "Comfort-2"} %} {{modes[value_json.PM]}}', icon='mdi:radiator'),
                    energy(),
                    power(),
                    entity('button', 'query_mode', command_topic='req', payload_press='{"CMD":"9","send":"clear"}'),
                    query_energy(),
                    query_power(),
                    query_status(),
                    reset_meas(),
                    entity('select', 'meas_type', options=['Query only - Energy in Ws', 'Query only - Energy in Wh', 'Query only - Energy in KWh', 'Query only - Power in W', 'Query only - Power in KW', 'Query & Auto - Energy in Ws', 'Query & Auto - Energy in Wh', 'Query & Auto - Energy in KWh', 'Query & Auto - Power in W', 'Query & Auto - Power in KW'], command_topic='__trash', icon='mdi:tune'),
                    entity('number', 'meas_MAT', command_topic='__trash', min='10', max='2550', step='10', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MIT', command_topic='__trash', min='1', max='255', step='1', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MD', command_topic='__trash', min='0', max='4095', step='1', mode='box', icon='mdi:equalizer'),
                    entity('button', 'set_meas', command_topic='req', command_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'meas_type\',ignorecase=True) %}\n    {% if states(entity) is search (\'only\') %}{% set ns.RM = 0 %}{% else %}{% set ns.RM = 1 %}{% endif %}\n    {% if states(entity) is search (\'Energy\') %}{% set ns.ep = 0 %}{% else %}{% set ns.ep = 1 %}{% endif %}\n    {% if states(entity) is search (\'KWh\') %}{% set ns.UN = 2 %}\n    {% elif states(entity) is search (\' KW\') %}{% set ns.UN = 4 %}\n    {% elif states(entity) is search (\' Wh\') %}{% set ns.UN = 1 %}\n    {% elif states(entity) is search (\' Ws\') %}{% set ns.UN = 0 %}\n    {% else %}{% set ns.UN = 3 %}\n    {% endif %}\n  {% elif entity is search(\'reset_meas\',ignorecase=True) %}\n    {% if is_state(entity, "on") %}{% set ns.RE = 1 %}{% else %}{% set ns.RE = 0 %}{% endif %}\n  {% elif entity is search(\'meas_mat\',ignorecase=True) %}\n    {% set ns.MAT = (states(entity)|int /10)|int(default=10) %}\n  {% elif entity is search(\'meas_mit\',ignorecase=True) %}\n    {% set ns.MIT = states(entity)|int(default=1) %}\n  {% elif entity is search(\'meas_md\',ignorecase=True) %}\n    {% set ns.MD_MSB = (states(entity)|int/16)|int(default=0) %}\n    {% set ns.MD_LSB = (states(entity)|int%16)|int(default=0) %}\n  {% endif %}\n{% endfor %} {"CMD":"5","RM":"{{ns.RM}}","RE":"{{ns.RE}}","ep":"{{ns.ep}}","IO":"0","MD_LSB":"{{ns.MD_LSB}}","UN":"{{ns.UN}}","MD_MSB":"{{ns.MD_MSB}}","MAT":"{{ns.MAT}}","MIT":"{{ns.MIT}}", "send":"clear"}', icon='mdi:download'),
                    entity('binary_sensor', 'OC', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.OC == 1 %}on{% else %}off{% endif %}'),
                    lc_contact(),
                ],
            },
            13: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            14: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': [
                    outlet_switch(),
                    energy(),
                    power(),
                    query_status(),
                    query_energy(),
                    query_power(),
                    reset_meas(),
                    entity('select', 'meas_type', options=['Query only - Energy in Ws', 'Query only - Energy in Wh', 'Query only - Energy in KWh', 'Query only - Power in W', 'Query only - Power in KW', 'Query & Auto - Energy in Ws', 'Query & Auto - Energy in Wh', 'Query & Auto - Energy in KWh', 'Query & Auto - Power in W', 'Query & Auto - Power in KW'], command_topic='__trash', icon='mdi:tune'),
                    entity('number', 'meas_MAT', command_topic='__trash', min='10', max='2550', step='10', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MIT', command_topic='__trash', min='1', max='255', step='1', mode='box', unit_of_measurement='s', icon='mdi:timer-refresh-outline'),
                    entity('number', 'meas_MD', command_topic='__trash', min='0', max='4095', step='1', mode='box', icon='mdi:equalizer'),
                    entity('button', 'set_meas', command_topic='req', command_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'meas_type\',ignorecase=True) %}\n    {% if states(entity) is search (\'only\') %}{% set ns.RM = 0 %}{% else %}{% set ns.RM = 1 %}{% endif %}\n    {% if states(entity) is search (\'Energy\') %}{% set ns.ep = 0 %}{% else %}{% set ns.ep = 1 %}{% endif %}\n    {% if states(entity) is search (\'KWh\') %}{% set ns.UN = 2 %}\n    {% elif states(entity) is search (\' KW\') %}{% set ns.UN = 4 %}\n    {% elif states(entity) is search (\' Wh\') %}{% set ns.UN = 1 %}\n    {% elif states(entity) is search (\' Ws\') %}{% set ns.UN = 0 %}\n    {% else %}{% set ns.UN = 3 %}\n    {% endif %}\n  {% elif entity is search(\'reset_meas\',ignorecase=True) %}\n    {% if is_state(entity, "on") %}{% set ns.RE = 1 %}{% else %}{% set ns.RE = 0 %}{% endif %}\n  {% elif entity is search(\'meas_mat\',ignorecase=True) %}\n    {% set ns.MAT = (states(entity)|int /10)|int(default=10) %}\n  {% elif entity is search(\'meas_mit\',ignorecase=True) %}\n    {% set ns.MIT = states(entity)|int(default=1) %}\n  {% elif entity is search(\'meas_md\',ignorecase=True) %}\n    {% set ns.MD_MSB = (states(entity)|int/16)|int(default=0) %}\n    {% set ns.MD_LSB = (states(entity)|int%16)|int(default=0) %}\n  {% endif %}\n{% endfor %} {"CMD":"5","RM":"{{ns.RM}}","RE":"{{ns.RE}}","ep":"{{ns.ep}}","IO":"0","MD_LSB":"{{ns.MD_LSB}}","UN":"{{ns.UN}}","MD_MSB":"{{ns.MD_MSB}}","MAT":"{{ns.MAT}}","MIT":"{{ns.MIT}}", "send":"clear"}', icon='mdi:download'),
                    lc_contact(),
                ],
            },
            15: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            17: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            18: {
                'device_config': dcfg(command='CMD', channel='IO/CMD'),
                'entities': [
                    entity('light', 'IO0', schema='template', state_topic='IO0/CMD4', state_template='{% if value_json.OV == 0 %}off{% else %}on{% endif %}', command_topic='req', command_on_template='{"CMD":"1","DV":"0","IO":"0","OV":"100","send":"clear"}', command_off_template='{"CMD":"1","DV":"0","IO":"0","OV":"0","send":"clear"}'),
                    entity('button', 'query_status_IO0', command_topic='req', payload_press='{"CMD":"3","IO":"0","send":"clear"}'),
                    entity('binary_sensor', 'IO0_LC', state_topic='IO0/CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.LC == 1 %}on{% else %}off{% endif %}'),
                    entity('light', 'IO1', schema='template', state_topic='IO1/CMD4', state_template='{% if value_json.OV == 0 %}off{% else %}on{% endif %}', command_topic='req', command_on_template='{"CMD":"1","DV":"0","IO":"1","OV":"100","send":"clear"}', command_off_template='{"CMD":"1","DV":"0","IO":"1","OV":"0","send":"clear"}'),
                    entity('button', 'query_status_IO1', command_topic='req', payload_press='{"CMD":"3","IO":"1","send":"clear"}'),
                    entity('binary_sensor', 'IO1_LC', state_topic='IO1/CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.LC == 1 %}on{% else %}off{% endif %}'),
                    entity('button', 'query_status_all', command_topic='req', payload_press='{"CMD":"3","IO":"30","send":"clear"}'),
                ],
            },
            8: {
                'device_config': dcfg(),
                'entities': [
                    sensor('cmd', vt('CMD'), state_class='measurement'),
                    sensor('dv', vt('DV'), state_class='measurement'),
                    sensor('io', vt('IO'), state_class='measurement'),
                    sensor('ov', vt('OV'), state_class='measurement'),
                    sensor('pf', vt('PF'), state_class='measurement'),
                    sensor('pfd', vt('PFD'), state_class='measurement'),
                    sensor('oc', vt('OC'), state_class='measurement'),
                    sensor('el', vt('EL'), state_class='measurement'),
                    sensor('lc', vt('LC'), state_class='measurement'),
                    sensor('rm', vt('RM'), state_class='measurement'),
                    sensor('re', vt('RE'), state_class='measurement'),
                    sensor('ep', vt('ep'), state_class='measurement'),
                    sensor('md_lsb', vt('MD_LSB'), state_class='measurement'),
                    sensor('un', vt('UN'), state_class='measurement'),
                    sensor('md_msb', vt('MD_MSB'), state_class='measurement'),
                    sensor('mat', vt('MAT'), state_class='measurement'),
                    sensor('mit', vt('MIT'), state_class='measurement'),
                    sensor('qu', vt('qu'), state_class='measurement'),
                    sensor('mv', vt('MV'), state_class='measurement'),
                ],
            },
            0: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            2: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            3: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            4: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            5: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            6: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            7: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            16: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_metering(),
            },
            19: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
            20: {
                'device_config': dcfg(command='CMD', channel='CMD'),
                'entities': d2_switch_basic(),
            },
        },
    },
}
