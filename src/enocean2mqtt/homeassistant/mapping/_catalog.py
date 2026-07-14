"""Named catalog for the discovery MAPPING: the recurring templates, entities and entity-groups,
each defined once. Factories return fresh objects. See mapping.py / _builders.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import (
    binary,
    dcfg,
    dcfg_gw,
    entity,
    enum_map_template,
    sensor,
    vt,
)

TMPL_ENERGY = '{% if value_json.UN == 0 %}\n  {{ (value_json.MV|int / 3600)|int }}\n{% elif value_json.UN == 1 %}\n  {{ value_json.MV }}\n{% elif value_json.UN == 2 %}\n  {{ value_json.MV|int * 1000 }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}'
TMPL_FAN_LABELS = "{% set v = value_json.FAN | int %}{{ ['Auto','Speed 0','Speed 1','Speed 2','Speed 3','Speed 4','Speed 5','Off'][v] if v < 8 else v }}"
TMPL_FAN_MODE = enum_map_template(0xD2, 0x11, 0x01, "FS")  # fan-mode labels from the D2-11-01 profile
TMPL_FAN_SPEED = '{% set v = value_json.FAN | int %}{% if v >= 210 %}Auto{% elif v >= 190 %}Speed 0{% elif v >= 165 %}Speed 1{% elif v >= 145 %}Speed 2{% else %}Speed 3{% endif %}'
TMPL_POWER = '{% if value_json.UN == 3 %}\n  {{ value_json.MV }}\n{% elif value_json.UN == 4 %}\n  {{ value_json.MV|int * 1000 }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}'
TMPL_SETPOINT_TYPE = enum_map_template(0xD2, 0x11, 0x01, "SPT")  # setpoint-type labels from the profile

def energy():
    return entity('sensor', 'energy', state_topic='CMD7', state_class='total_increasing', device_class='energy', unit_of_measurement='Wh', value_template=TMPL_ENERGY)

def hum():
    return sensor('hum', vt('HUM', 'round(1)'), device_class='humidity', state_class='measurement', unit='%')

def lc_contact():
    return entity('binary_sensor', 'LC', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.LC == 1 %}on{% else %}off{% endif %}')

def outlet_switch():
    return entity('switch', 'switch', state_topic='CMD4', state_on='100', state_off='0', value_template=vt('OV'), command_topic='req', payload_on='{"CMD":"1","DV":"0","IO":"0","OV":"100","send":"clear"}\n', payload_off='{"CMD":"1","DV":"0","IO":"0","OV":"0","send":"clear"}\n', device_class='outlet')

def pairing():
    return entity('button', 'pairing', command_topic='a5/req', payload_press='{"raw_data":"E0:40:0D:80","send":"clear+learn+raw_data"}', icon='mdi:connection')

def power():
    return entity('sensor', 'power', state_topic='CMD7', state_class='measurement', device_class='power', unit_of_measurement='W', value_template=TMPL_POWER)

def query_energy():
    return entity('button', 'query_energy', command_topic='req', payload_press='{"CMD":"6","qu":"0","IO":"30","send":"clear"}')

def query_power():
    return entity('button', 'query_power', command_topic='req', payload_press='{"CMD":"6","qu":"1","IO":"30","send":"clear"}')

def query_status():
    return entity('button', 'query_status', command_topic='req', payload_press='{"CMD":"3","IO":"30","send":"clear"}')

def reset_meas():
    return entity('switch', 'reset_meas', command_topic='__trash', icon='mdi:numeric-0-circle-outline')

def setpoint():
    return sensor('setpoint', vt('SP'), icon='mdi:target')

def svc():
    return sensor('svc', vt('SVC'), device_class='voltage', state_class='measurement', unit='V')

def t_raw():
    return sensor('t_raw', vt('TMP'), device_class='temperature', state_class='measurement', unit='°C', enabled_by_default='false')

def temp_c():
    return sensor('tempC', vt('TMP', 'round(1)'), device_class='temperature', state_class='measurement', unit='°C')

def cover_pair():
    return [
        entity('cover', 'cover', command_topic='req', payload_open='{"CMD":"1","POS":"0","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', payload_close='{"CMD":"1","POS":"100","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', payload_stop='{"CMD":"2","CHN":"0","send":"clear"}', position_topic='CMD4', position_template='{% if (value_json.POS <= 100) and (value_json.POS >= 0) %}\n  {{ value_json.POS }}\n{% else %}\n  {{ state_attr(entity_id,"current_position")|int(default=0) }}\n{% endif %}', set_position_topic='req', set_position_template='{"CMD":"1","POS":"{{ position }}","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', tilt_status_topic='CMD4', tilt_status_template='{% if (value_json.ANG <= 100) and (value_json.ANG >= 0) %}\n  {{ value_json.ANG }}\n{% else %}\n  {{ state_attr(entity_id,"current_tilt_position")|int(default=0) }}\n{% endif %}', tilt_command_topic='req', tilt_command_template='{"CMD":"1","POS":"127","ANG":"{{ tilt_position }}","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}'),
        entity('cover', 'cover2', command_topic='req', payload_open='{"CMD":"1","POS":"0","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', payload_close='{"CMD":"1","POS":"100","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', payload_stop='{"CMD":"2","CHN":"0","send":"clear"}', position_topic='CMD4', position_open=0, position_closed=100, position_template='{% if (value_json.POS <= 100) and (value_json.POS >= 0) %}\n  {{ value_json.POS }}\n{% else %}\n  {{ state_attr(entity_id,"current_position")|int(default=0) }}\n{% endif %}', set_position_topic='req', set_position_template='{"CMD":"1","POS":"{{ 100 - position }}","ANG":"127","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}', tilt_status_topic='CMD4', tilt_status_template='{% if (value_json.ANG <= 100) and (value_json.ANG >= 0) %}\n  {{ value_json.ANG }}\n{% else %}\n  {{ state_attr(entity_id,"current_tilt_position")|int(default=0) }}\n{% endif %}', tilt_command_topic='req', tilt_command_template='{"CMD":"1","POS":"127","ANG":"{{ tilt_position }}","REPO":"0","LOCK":"0","CHN":"0","send":"clear"}'),
    ]

def d2_metering():
    return [
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
        entity('binary_sensor', 'PF', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.PF == 1 %}on{% else %}off{% endif %}'),
        entity('binary_sensor', 'PFD', state_topic='CMD4', payload_on='on', payload_off='off', value_template='{% if value_json.PFD == 1 %}on{% else %}off{% endif %}'),
        lc_contact(),
    ]

def d2_switch_basic():
    return [
        outlet_switch(),
        query_status(),
        lc_contact(),
    ]

def eltako_blind():
    return [
        entity('button', 'pairing', command_topic='a5/req', payload_press='{"raw_data":"FF:F8:0D:80","send":"clear+learn+raw_data"}', icon='mdi:connection'),
        entity('cover', 'cover', command_topic='a5/req', payload_open='{"DB3":"0","DB2":"0","DB1":"1","DB0":"8","send":"clear"}', payload_close='{"DB3":"0","DB2":"0","DB1":"2","DB0":"8","send":"clear"}', payload_stop='{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}', state_topic='+', state_stopped='0', state_opening='01', state_closing='02', state_open='70', state_closed='50', value_template='{% if value_json._RAW_DATA_.split(":")|length == 2 %}\n  {{ value_json._RAW_DATA_.split(":")[0] }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}', set_position_topic='a5/req', set_position_template='{% set shut_time_sec = state_attr(entity_id,\'shut_time\')|float(default=255.0) %} {% set cur_pos = state_attr(entity_id,"current_position")|int(default=0) %} {% set step = position - cur_pos %} {% if step == 0 %}{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}{% else %}{% set DB1 = iif(step < 0,2,1) %} {% set drive_time_100ms = [(((step|abs)*shut_time_sec/100)*10)|int, 1]|max %} {% set shut_time_msb = (drive_time_100ms/256)|int %} {% set shut_time_lsb = (drive_time_100ms%256)|int %} {"DB3":"{{shut_time_msb}}","DB2":"{{shut_time_lsb}}","DB1":"{{DB1}}","DB0":"10","send":"clear"}{% endif %}', position_topic='+', position_template='{% if value_json.POS is defined %}{{ value_json.POS }}{% endif %}', json_attributes_topic='shut_time', json_attributes_template="{{ {'shut_time': value|float(255)} | tojson }}"),
        entity('binary_sensor', 'end_top', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="70","on","off") }}'),
        entity('binary_sensor', 'end_bottom', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="50","on","off") }}'),
        entity('binary_sensor', 'start_up', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="01","on","off") }}'),
        entity('binary_sensor', 'start_down', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="02","on","off") }}'),
    ]

def eltako_dimmer():
    return [
        pairing(),
        entity('number', 'speed', command_topic='a5/__trash', min='0', max='255', step='1', mode='slider', icon='mdi:speedometer'),
        entity('light', 'light', schema='template', command_topic='a5/req', command_on_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'speed$\',ignorecase=True) %}\n    {% set ns.dim_speed = \'%02x\' % (states(entity)|int(default=0)) %}\n  {% endif %}\n{% endfor %} {% if transition is defined %}\n  {% set ns.dim_speed = \'%02x\' % (transition|int(default=0)) %}\n{% endif %} {% set ns.dim_val = "FF" %} {% if brightness is defined %}\n  {% set ns.dim_val = \'%02x\' % (((brightness|int(default=255))*100/255)|int) %}\n{% endif %} {"raw_data":"02:{{ns.dim_val}}:{{ns.dim_speed}}:09","send":"clear+raw_data"}', command_off_template='{% set ns = namespace() %} {% for entity in device_entities(device_id(entity_id)) %}\n  {% if entity is search(\'speed$\',ignorecase=True) %}\n    {% set ns.dim_speed = \'%02x\' % (states(entity)|int(default=0)) %}\n  {% endif %}\n{% endfor %} {% if transition is defined %}\n  {% set ns.dim_speed = \'%02x\' % (transition|int(default=0)) %}\n{% endif %} {"raw_data":"02:00:{{ns.dim_speed}}:08","send":"clear+raw_data"}', state_topic='+', state_template='{% if value_json._RAW_DATA_.split(":")|length == 2 %}\n  {% if value_json._RAW_DATA_.split(":")[0]=="70" %}on{% elif value_json._RAW_DATA_.split(":")[0]=="50" %}off{% endif %}\n{% elif value_json._RAW_DATA_.split(":")|length == 5 %}\n  {% if value_json._RAW_DATA_.split(":")[3]=="09" %}on{% elif value_json._RAW_DATA_.split(":")[3]=="08" %}off{% endif %}\n{% endif %}', brightness_template='{% if value_json._RAW_DATA_.split(":")|length == 5 %}\n  {{ (value_json._RAW_DATA_.split(":")[1]|int(default=0,base=16)*255/100)|int }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}'),
    ]

def eltako_relay():
    return [
        pairing(),
        entity('switch', 'switch', command_topic='a5/req', payload_on='{"raw_data":"01:00:00:09","send":"clear+raw_data"}', payload_off='{"raw_data":"01:00:00:08","send":"clear+raw_data"}', state_topic='f6', value_template='{% if value_json._RAW_DATA_.split(":")[0]=="70" %}ON{% elif value_json._RAW_DATA_.split(":")[0]=="50" %}OFF{% endif %}', enabled_by_default='false', device_class='outlet'),
        entity('light', 'light', schema='template', command_topic='a5/req', command_on_template='{"raw_data":"01:00:00:09","send":"clear+raw_data"}', command_off_template='{"raw_data":"01:00:00:08","send":"clear+raw_data"}', state_topic='f6', state_template='{% if value_json._RAW_DATA_.split(":")[0]=="70" %}on{% elif value_json._RAW_DATA_.split(":")[0]=="50" %}off{% endif %}'),
    ]

def room_panel():
    return [
        sensor('setpoint_type', TMPL_SETPOINT_TYPE),
        temp_c(),
        hum(),
        sensor('sp', vt('SP')),
        sensor('ibs', vt('IBS')),
        sensor('fan_speed', TMPL_FAN_MODE),
        binary('occupancy', '{% if value_json.OS == 1 %}ON{% else %}OFF{% endif %}', device_class='occupancy'),
    ]

def temp_pair():
    return [
        t_raw(),
        temp_c(),
    ]
