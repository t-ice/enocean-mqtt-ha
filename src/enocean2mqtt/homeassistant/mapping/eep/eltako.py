"""Discovery MAPPING fragment: Eltako model catalog.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import dcfg_gw, entity
from enocean2mqtt.homeassistant.mapping._catalog import eltako_blind, eltako_dimmer, eltako_relay, pairing

MAPPING = {
    'eltako': {
        'fhd60sb': {
            'device_config': dcfg_gw('0xA5', '0x06', '0x01'),
            'entities': [
                entity('sensor', 'lux', state_topic='a5', value_template='{% if value_json._RAW_DATA_.split(":")[1]=="00" %}\n  {{ value_json._RAW_DATA_.split(":")[0]|int(base=16) }}\n{% else %}\n  {{ value_json.ILL2 | round(1) }}\n{% endif %}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
            ],
        },
        'fsb14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x3F', 'type': '0x7F', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_blind(),
        },
        'fsb61': {
            'device_config': [{'rorg': '0xA5', 'func': '0x3F', 'type': '0x7F', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_blind(),
        },
        'fsb61np': {
            'device_config': [{'rorg': '0xA5', 'func': '0x3F', 'type': '0x7F', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_blind(),
        },
        'fj62': {
            'device_config': [{'rorg': '0xA5', 'func': '0x3F', 'type': '0x7F', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': [
                entity('button', 'pairing', command_topic='a5/req', payload_press='{"raw_data":"FF:F8:0D:80","send":"clear+learn+raw_data"}', icon='mdi:connection'),
                entity('button', 'unlock_pairing', command_topic='a5/req', payload_press='{"raw_data":"00:00:00:28","send":"clear+raw_data"}', icon='mdi:connection'),
                entity('cover', 'cover', command_topic='a5/req', payload_open='{"DB3":"0","DB2":"0","DB1":"1","DB0":"8","send":"clear"}', payload_close='{"DB3":"0","DB2":"0","DB1":"2","DB0":"8","send":"clear"}', payload_stop='{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}', state_topic='+', state_stopped='0', state_opening='01', state_closing='02', state_open='70', state_closed='50', value_template='{% if value_json._RAW_DATA_.split(":")|length == 2 %}\n  {{ value_json._RAW_DATA_.split(":")[0] }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}', set_position_topic='a5/req', set_position_template='{% set shut_time_sec = state_attr(entity_id,\'shut_time\')|float(default=255.0) %} {% set cur_pos = state_attr(entity_id,"current_position")|int(default=0) %} {% set step = position - cur_pos %} {% if step == 0 %}{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}{% else %}{% set DB1 = iif(step < 0,2,1) %} {% set drive_time_100ms = [(((step|abs)*shut_time_sec/100)*10)|int, 1]|max %} {% set shut_time_msb = (drive_time_100ms/256)|int %} {% set shut_time_lsb = (drive_time_100ms%256)|int %} {"DB3":"{{shut_time_msb}}","DB2":"{{shut_time_lsb}}","DB1":"{{DB1}}","DB0":"10","send":"clear"}{% endif %}', position_topic='pos', position_template='{% if value_json.POS is defined %}{{ value_json.POS }}{% endif %}', json_attributes_topic='shut_time', json_attributes_template="{{ {'shut_time': value|float(255)} | tojson }}"),
                entity('binary_sensor', 'end_top', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="70","on","off") }}'),
                entity('binary_sensor', 'end_bottom', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="50","on","off") }}'),
                entity('binary_sensor', 'start_up', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="01","on","off") }}'),
                entity('binary_sensor', 'start_down', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="02","on","off") }}'),
            ],
        },
        'tf61j': {
            'device_config': [{'rorg': '0xA5', 'func': '0x3F', 'type': '0x7F', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': [
                entity('button', 'pairing', command_topic='a5/req', payload_press='{"raw_data":"FF:F8:0D:80","send":"clear+learn+raw_data"}', icon='mdi:connection'),
                entity('button', 'unlock_pairing', command_topic='a5/req', payload_press='{"raw_data":"00:00:00:28","send":"clear+raw_data"}', icon='mdi:connection'),
                entity('cover', 'cover', command_topic='a5/req', payload_open='{"DB3":"0","DB2":"0","DB1":"1","DB0":"8","send":"clear"}', payload_close='{"DB3":"0","DB2":"0","DB1":"2","DB0":"8","send":"clear"}', payload_stop='{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}', state_topic='+', state_stopped='0', state_opening='01', state_closing='02', state_open='70', state_closed='50', value_template='{% if value_json._RAW_DATA_.split(":")|length == 2 %}\n  {{ value_json._RAW_DATA_.split(":")[0] }}\n{% else %}\n  {{ states(entity_id)|int(default=0) }}\n{% endif %}', set_position_topic='a5/req', set_position_template='{% set shut_time_sec = state_attr(entity_id,\'shut_time\')|float(default=255.0) %} {% set cur_pos = state_attr(entity_id,"current_position")|int(default=0) %} {% set step = position - cur_pos %} {% if step == 0 %}{"DB3":"0","DB2":"0","DB1":"0","DB0":"8","send":"clear"}{% else %}{% set DB1 = iif(step < 0,2,1) %} {% set drive_time_100ms = [(((step|abs)*shut_time_sec/100)*10)|int, 1]|max %} {% set shut_time_msb = (drive_time_100ms/256)|int %} {% set shut_time_lsb = (drive_time_100ms%256)|int %} {"DB3":"{{shut_time_msb}}","DB2":"{{shut_time_lsb}}","DB1":"{{DB1}}","DB0":"10","send":"clear"}{% endif %}', position_topic='pos', position_template='{% if value_json.POS is defined %}{{ value_json.POS }}{% endif %}', json_attributes_topic='shut_time', json_attributes_template="{{ {'shut_time': value|float(255)} | tojson }}"),
                entity('binary_sensor', 'end_top', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="70","on","off") }}'),
                entity('binary_sensor', 'end_bottom', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="50","on","off") }}'),
                entity('binary_sensor', 'start_up', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="01","on","off") }}'),
                entity('binary_sensor', 'start_down', state_topic='f6', payload_on='on', payload_off='off', value_template='{{ iif(value_json._RAW_DATA_.split(":")[0]=="02","on","off") }}'),
            ],
        },
        'fsr14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'fsr61': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'tf61l': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': [
                pairing(),
                entity('button', 'unlock_pairing', command_topic='a5/req', payload_press='{"raw_data":"00:00:00:28","send":"clear+raw_data"}', icon='mdi:connection'),
                entity('button', 'enable_feedback', command_topic='a5/req', payload_press='{"raw_data":"00:00:00:08","send":"clear+raw_data"}', icon='mdi:connection'),
                entity('switch', 'switch', command_topic='a5/req', payload_on='{"raw_data":"01:00:00:09","send":"clear+raw_data"}', payload_off='{"raw_data":"01:00:00:08","send":"clear+raw_data"}', state_topic='f6', value_template='{% if value_json._RAW_DATA_.split(":")[0]=="70" %}ON{% elif value_json._RAW_DATA_.split(":")[0]=="50" %}OFF{% endif %}', enabled_by_default='false', device_class='outlet'),
                entity('light', 'light', schema='template', command_topic='a5/req', command_on_template='{"raw_data":"01:00:00:09","send":"clear+raw_data"}', command_off_template='{"raw_data":"01:00:00:08","send":"clear+raw_data"}', state_topic='f6', state_template='{% if value_json._RAW_DATA_.split(":")[0]=="70" %}on{% elif value_json._RAW_DATA_.split(":")[0]=="50" %}off{% endif %}'),
            ],
        },
        'fud14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
        'fud61': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
        'fdg14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
        'f4sr14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'ftn14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'fmz14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'fsg14': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
        'fl62': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_relay(),
        },
        'fd62': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
        'tf61d': {
            'device_config': [{'rorg': '0xA5', 'func': '0x38', 'type': '0x08', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}, {'rorg': '0xF6', 'func': '0x02', 'type': '0x01', 'command': '', 'channel': '', 'log_learn': '', 'direction': '', 'answer': ''}],
            'entities': eltako_dimmer(),
        },
    },
}
