"""Discovery MAPPING fragment: F6 (RPS) rockers and handles.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import binary, dcfg, entity, sensor, vt

MAPPING = {
    246: {
        2: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    binary('pressed', vt('EB'), payload_on='1', payload_off='0'),
                    binary('AI_pressed', '{% if (value_json.EB and value_json.R1 == 0) or (value_json.SA and value_json.R2 == 0) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('AO_pressed', '{% if (value_json.EB and value_json.R1 == 1) or (value_json.SA and value_json.R2 == 1) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('BI_pressed', '{% if (value_json.EB and value_json.R1 == 2) or (value_json.SA and value_json.R2 == 2) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('BO_pressed', '{% if (value_json.EB and value_json.R1 == 3) or (value_json.SA and value_json.R2 == 3) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                ],
                'virtual': [
                    entity('select', 'action', options=['None', 'AO', 'AI', 'BO', 'BI', 'AO + BO', 'AO + BI', 'AI + BO', 'AI + BI', 'BO + AO', 'BO + AI', 'BI + AO', 'BI + AI'], command_topic='req', command_template='{% set R1, EB, R2, SA, T21, NU = 0, 0, 0, 0, 1, 0 %} {% set id = {"AI":"0","AO":"1","BI":"2","BO":"3"} %} {% set action = value.split(" + ") %} {% if value is not search(\'None\') %}{% set EB, NU, R1 = 1, 1, id[action[0]] %}{% endif %} {% if action|length==2 %}{% set SA, R2 = 1, id[action[1]] %}{% endif %} {"R1":{{R1}},"EB":{{EB}},"R2":{{R2}},"SA":{{SA}},"T21":{{T21}},"NU":{{NU}},"send":"clear"}'),
                    entity('switch', 'AI', command_topic='__trash'),
                    entity('switch', 'AO', command_topic='__trash'),
                    entity('switch', 'BI', command_topic='__trash'),
                    entity('switch', 'BO', command_topic='__trash'),
                    entity('button', 'send', command_topic='req', command_template='{% set ns = namespace(action=[]) %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'AI\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["0"] %}\n  {% elif entity is search(\'AO\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["1"] %}\n  {% elif entity is search(\'BI\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["2"] %}\n  {% elif entity is search(\'BO\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["3"] %}\n  {% endif %}\n{% endfor %} {% set R1, EB, R2, SA, T21, NU = 0, 0, 0, 0, 1, 0 %} {% if ns.action|length>0 %}{% set EB, NU, R1 = 1, 1, ns.action[0] %}{% endif %} {% if ns.action|length>1 %}{% set SA, R2 = 1, ns.action[1] %}{% endif %} {"R1":{{R1}},"EB":{{EB}},"R2":{{R2}},"SA":{{SA}},"T21":{{T21}},"NU":{{NU}},"send":"clear"}', icon='mdi:download'),
                    entity('button', 'AI (press)', command_topic='req', payload_press='{"R1":0,"EB":1,"R2":0,"SA":0,"T21":1,"NU":1,"send":"clear"}', icon='mdi:gesture-tap-button'),
                    entity('button', 'AO (press)', command_topic='req', payload_press='{"R1":1,"EB":1,"R2":0,"SA":0,"T21":1,"NU":1,"send":"clear"}', icon='mdi:gesture-tap-button'),
                    entity('button', 'BI (press)', command_topic='req', payload_press='{"R1":2,"EB":1,"R2":0,"SA":0,"T21":1,"NU":1,"send":"clear"}', icon='mdi:gesture-tap-button'),
                    entity('button', 'BO (press)', command_topic='req', payload_press='{"R1":3,"EB":1,"R2":0,"SA":0,"T21":1,"NU":1,"send":"clear"}', icon='mdi:gesture-tap-button'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    binary('pressed', vt('EB'), payload_on='1', payload_off='0'),
                    binary('AI_pressed', '{% if (value_json.EB and value_json.R1 == 0) or (value_json.SA and value_json.R2 == 0) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('AO_pressed', '{% if (value_json.EB and value_json.R1 == 1) or (value_json.SA and value_json.R2 == 1) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('BI_pressed', '{% if (value_json.EB and value_json.R1 == 2) or (value_json.SA and value_json.R2 == 2) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                    binary('BO_pressed', '{% if (value_json.EB and value_json.R1 == 3) or (value_json.SA and value_json.R2 == 3) %}on{% else %}off{% endif %}', payload_on='on', payload_off='off'),
                ],
                'virtual': [
                    entity('select', 'action', options=['None', 'AO', 'AI', 'BO', 'BI', 'AO + BO', 'AO + BI', 'AI + BO', 'AI + BI', 'BO + AO', 'BO + AI', 'BI + AO', 'BI + AI'], command_topic='req', command_template='{% set R1, EB, R2, SA, T21, NU = 0, 0, 0, 0, 1, 0 %} {% set id = {"AI":"0","AO":"1","BI":"2","BO":"3"} %} {% set action = value.split(" + ") %} {% if value is not search(\'None\') %}{% set EB, NU, R1 = 1, 1, id[action[0]] %}{% endif %} {% if action|length==2 %}{% set SA, R2 = 1, id[action[1]] %}{% endif %} {"R1":{{R1}},"EB":{{EB}},"R2":{{R2}},"SA":{{SA}},"T21":{{T21}},"NU":{{NU}},"send":"clear"}'),
                    entity('switch', 'AI', command_topic='__trash'),
                    entity('switch', 'AO', command_topic='__trash'),
                    entity('switch', 'BI', command_topic='__trash'),
                    entity('switch', 'BO', command_topic='__trash'),
                    entity('button', 'send', command_topic='req', command_template='{% set ns = namespace(action=[]) %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'AI\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["0"] %}\n  {% elif entity is search(\'AO\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["1"] %}\n  {% elif entity is search(\'BI\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["2"] %}\n  {% elif entity is search(\'BO\',ignorecase=True) and is_state(entity, "on") %}\n    {% set ns.action = ns.action+["3"] %}\n  {% endif %}\n{% endfor %} {% set R1, EB, R2, SA, T21, NU = 0, 0, 0, 0, 1, 0 %} {% if ns.action|length>0 %}{% set EB, NU, R1 = 1, 1, ns.action[0] %}{% endif %} {% if ns.action|length>1 %}{% set SA, R2 = 1, ns.action[1] %}{% endif %} {"R1":{{R1}},"EB":{{EB}},"R2":{{R2}},"SA":{{SA}},"T21":{{T21}},"NU":{{NU}},"send":"clear"}', icon='mdi:download'),
                ],
            },
            3: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ra', vt('RA'), state_class='measurement'),
                ],
            },
            4: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ebo', vt('EBO'), device_class='energy', state_class='total_increasing'),
                    sensor('bc', vt('BC'), state_class='measurement'),
                    sensor('rbi', vt('RBI'), state_class='measurement'),
                    sensor('rb0', vt('RB0'), state_class='measurement'),
                    sensor('rai', vt('RAI'), state_class='measurement'),
                    sensor('ra0', vt('RA0'), state_class='measurement'),
                ],
            },
        },
        4: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    binary('status', '{% if value_json.KC == 112 %}ON{% else %}OFF{% endif %}'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ebo', vt('EBO'), device_class='energy', state_class='total_increasing'),
                    sensor('bc', vt('BC'), state_class='measurement'),
                    sensor('soc', vt('SOC'), state_class='measurement'),
                ],
            },
        },
        5: {
            2: {
                'device_config': dcfg(),
                'entities': [
                    binary('alarm', '{% if value_json.SMO == 16 %}on{% else %}off{% endif %}', device_class='smoke', payload_on='on', payload_off='off'),
                    binary('battery', '{% if value_json.SMO == 48 %}on{% else %}off{% endif %}', device_class='battery', payload_on='on', payload_off='off'),
                ],
            },
            0: {
                'device_config': dcfg(),
                'entities': [
                    sensor('wnd', vt('WND'), state_class='measurement'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('was', vt('WAS'), state_class='measurement'),
                ],
            },
        },
        16: {
            0: {
                'device_config': dcfg(),
                'entities': [
                    binary('state_2p', '{% if value_json.WIN == 3 %}OFF{% else %}ON{% endif %}', device_class='window'),
                    sensor('state_3p', '{% if value_json.WIN == 3 %}off{% elif value_json.WIN == 1 %}tilt{% else %}on{% endif %}'),
                ],
            },
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('hc', vt('HC'), state_class='measurement'),
                    sensor('hvl', vt('HVL'), state_class='measurement'),
                ],
            },
        },
        1: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('pb', vt('PB'), state_class='measurement'),
                ],
            },
        },
        3: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    sensor('r1', vt('R1'), state_class='measurement'),
                    sensor('eb', vt('EB'), device_class='energy', state_class='total_increasing'),
                    sensor('r2', vt('R2'), state_class='measurement'),
                    sensor('sa', vt('SA'), state_class='measurement'),
                ],
            },
            2: {
                'device_config': dcfg(),
                'entities': [
                    sensor('r1', vt('R1'), state_class='measurement'),
                    sensor('eb', vt('EB'), device_class='energy', state_class='total_increasing'),
                    sensor('r2', vt('R2'), state_class='measurement'),
                    sensor('sa', vt('SA'), state_class='measurement'),
                ],
            },
        },
    },
}
