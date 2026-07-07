"""Discovery MAPPING fragment: D5 (1BS) contacts + bridge common/system entities.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import binary, dcfg, entity, vt

MAPPING = {
    213: {
        0: {
            1: {
                'device_config': dcfg(),
                'entities': [
                    binary('contact', vt('CO'), payload_on='0', payload_off='1'),
                ],
            },
        },
    },
    'common': {
        'rssi': [
            entity('sensor', 'rssi', state_topic='', value_template=vt('_RSSI_'), unit_of_measurement='dBm', device_class='signal_strength', state_class='measurement', entity_category='diagnostic'),
        ],
        'date': [
            entity('sensor', 'last_seen', state_topic='', value_template="{{ value_json._DATE_|regex_replace(find='\\..*$', replace='')|as_datetime()|as_local() }}", device_class='timestamp', entity_category='diagnostic'),
        ],
    },
    'system': {
        'delete': [
            {'system': 'True', 'component': 'button', 'name': 'delete', 'config': {'command_topic': '__system', 'payload_press': 'delete', 'icon': 'mdi:delete', 'entity_category': 'config'}},
        ],
        'learn': [
            {'system': 'True', 'component': 'switch', 'name': 'ENOCEAN_LEARN', 'config': {'state_topic': 'learn', 'command_topic': 'learn/req', 'icon': 'mdi:home-plus', 'entity_category': 'config'}},
        ],
    },
}
