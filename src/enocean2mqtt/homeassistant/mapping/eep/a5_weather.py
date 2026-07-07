"""Discovery MAPPING fragment: A5-13 environmental / weather.

Merged into the full MAPPING by the package __init__. Recurring pieces come from _catalog.py,
scaffolding from _builders.py; one-offs are literals. Structural invariants are checked by tests/ha/test_mapping.py.
"""

# ruff: noqa
from enocean2mqtt.homeassistant.mapping._builders import dcfg, entity, sensor, vt

MAPPING = {
    165: {
        19: {
            1: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'lux_raw', state_topic='ID1', value_template=vt('DWS'), device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'lux', state_topic='ID1', value_template=vt('DWS', 'round(1)'), device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('sensor', 't_raw', state_topic='ID1', value_template=vt('TMP'), device_class='temperature', state_class='measurement', unit_of_measurement='°C', enabled_by_default='false'),
                    entity('sensor', 'temperature', state_topic='ID1', value_template=vt('TMP', 'round(1)'), device_class='temperature', state_class='measurement', unit_of_measurement='°C'),
                    entity('sensor', 'ws_raw', state_topic='ID1', value_template=vt('WND'), icon='mdi:weather-windy', unit_of_measurement='m/s', enabled_by_default='false'),
                    entity('sensor', 'windspeed', state_topic='ID1', value_template=vt('WND', 'round(1)'), icon='mdi:weather-windy', unit_of_measurement='m/s'),
                    entity('binary_sensor', 'day', state_topic='ID1', value_template="{% if value_json['D/N'] == 0 %}OFF{% else %}ON{% endif %}"),
                    entity('binary_sensor', 'rain', state_topic='ID1', value_template='{% if value_json.RAN == 0 %}OFF{% else %}ON{% endif %}'),
                    entity('sensor', 'snw_raw', state_topic='ID2', value_template='{{ value_json.SNW * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_west', state_topic='ID2', value_template='{{ value_json.SNW * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('sensor', 'sns_raw', state_topic='ID2', value_template='{{ value_json.SNS * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_south', state_topic='ID2', value_template='{{ value_json.SNS * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('sensor', 'sne_raw', state_topic='ID2', value_template='{{ value_json.SNE * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_east', state_topic='ID2', value_template='{{ value_json.SNE * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('binary_sensor', 'hem_north', state_topic='ID2', value_template='{% if value_json.HEM == 0 %}ON{% else %}OFF{% endif %}'),
                    entity('sensor', 'hemisphere', state_topic='ID2', value_template='{% if value_json.HEM == 0 %}North{% else %}South{% endif %}'),
                    entity('sensor', 'date', state_topic='ID3', enabled_by_default='false', value_template="{% set d=strptime((value_json.DY|int(default=0) ~ '-' ~ value_json.MTH|int(default=0) ~ '-' ~ value_json.YR|int(default=0)),'%d-%m-%Y') %} {{ d.date() }}", icon='mdi:calendar-range'),
                    entity('sensor', 'date_source', state_topic='ID3', enabled_by_default='false', value_template='{% if value_json.SRC == 0 %}Real Time Clock{% else %}Radio Waves{% endif %}'),
                    entity('sensor', 'weekday', state_topic='ID4', enabled_by_default='false', value_template='{% set map = {"1":"Monday","2":"Tuesday","3":"Wednesday","4":"Thursday","5":"Friday","6":"Saturday","7":"Sunday"} %} {{ map[value_json.WDY|string] }}', icon='mdi:calendar'),
                    entity('sensor', 'time', state_topic='ID4', enabled_by_default='false', value_template="{{ strptime((value_json.HR|int(default=0)~':'~value_json.MIN|int(default=0)~':'~value_json.SEC|int(default=0)),'%H:%M:%S').time() }}", icon='mdi:clock-outline'),
                    entity('sensor', 'am_pm', state_topic='ID4', enabled_by_default='false', value_template="{% if value_json['A/PM'] == 0 %}AM{% else %}PM{% endif %}", icon='mdi:radio-am'),
                    entity('sensor', 'time_format', state_topic='ID4', enabled_by_default='false', value_template='{% if value_json.TMF == 0 %}24{% else %}12{% endif %}'),
                    entity('sensor', 'time_source', state_topic='ID4', enabled_by_default='false', value_template='{% if value_json.SRC == 0 %}Real Time Clock{% else %}Radio Waves{% endif %}'),
                    entity('sensor', 'elevation', state_topic='ID5', enabled_by_default='false', value_template=vt('ELV'), unit_of_measurement='°', icon='mdi:elevation-rise'),
                    entity('sensor', 'azimuth', state_topic='ID5', enabled_by_default='false', value_template=vt('AZM'), unit_of_measurement='°', icon='mdi:sun-compass'),
                    entity('sensor', 'latitude', state_topic='ID6', enabled_by_default='false', value_template="{{ (value_json['LAT(MSB)']*256+value_json['LAT(LSB)'])*180/4095-90 }}", unit_of_measurement='°', icon='mdi:latitude'),
                    entity('sensor', 'longitude', state_topic='ID6', enabled_by_default='false', value_template="{{ (value_json['LOT(MSB)']*256+value_json['LOT(LSB)'])*360/4095-180 }}", unit_of_measurement='°', icon='mdi:longitude'),
                ],
            },
            2: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'snw_raw', state_topic='ID2', value_template='{{ value_json.SNW * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_west', state_topic='ID2', value_template='{{ value_json.SNW * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('sensor', 'sns_raw', state_topic='ID2', value_template='{{ value_json.SNS * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_south', state_topic='ID2', value_template='{{ value_json.SNS * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('sensor', 'sne_raw', state_topic='ID2', value_template='{{ value_json.SNE * 1000 }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx', enabled_by_default='false'),
                    entity('sensor', 'sun_east', state_topic='ID2', value_template='{{ value_json.SNE * 1000 | round(1) }}', device_class='illuminance', state_class='measurement', unit_of_measurement='lx'),
                    entity('binary_sensor', 'hem_north', state_topic='ID2', value_template='{% if value_json.HEM == 0 %}ON{% else %}OFF{% endif %}'),
                    entity('sensor', 'hemisphere', state_topic='ID2', value_template='{% if value_json.HEM == 0 %}North{% else %}South{% endif %}'),
                ],
            },
            3: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'date', state_topic='ID3', enabled_by_default='false', value_template="{% set d=strptime((value_json.DY|int(default=0) ~ '-' ~ value_json.MTH|int(default=0) ~ '-' ~ value_json.YR|int(default=0)),'%d-%m-%Y') %} {{ d.date() }}", icon='mdi:calendar-range'),
                    entity('sensor', 'date_source', state_topic='ID3', enabled_by_default='false', value_template='{% if value_json.SRC == 0 %}Real Time Clock{% else %}Radio Waves{% endif %}'),
                ],
            },
            4: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'weekday', state_topic='ID4', enabled_by_default='false', value_template='{% set map = {"1":"Monday","2":"Tuesday","3":"Wednesday","4":"Thursday","5":"Friday","6":"Saturday","7":"Sunday"} %} {{ map[value_json.WDY|string] }}', icon='mdi:calendar'),
                    entity('sensor', 'time', state_topic='ID4', enabled_by_default='false', value_template="{{ strptime((value_json.HR|int(default=0)~':'~value_json.MIN|int(default=0)~':'~value_json.SEC|int(default=0)),'%H:%M:%S').time() }}", icon='mdi:clock-outline'),
                    entity('sensor', 'am_pm', state_topic='ID4', enabled_by_default='false', value_template="{% if value_json['A/PM'] == 0 %}AM{% else %}PM{% endif %}", icon='mdi:radio-am'),
                    entity('sensor', 'time_format', state_topic='ID4', enabled_by_default='false', value_template='{% if value_json.TMF == 0 %}24{% else %}12{% endif %}'),
                    entity('sensor', 'time_source', state_topic='ID4', enabled_by_default='false', value_template='{% if value_json.SRC == 0 %}Real Time Clock{% else %}Radio Waves{% endif %}'),
                ],
            },
            5: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'elevation', state_topic='ID5', enabled_by_default='false', value_template=vt('ELV'), unit_of_measurement='°', icon='mdi:elevation-rise'),
                    entity('sensor', 'azimuth', state_topic='ID5', enabled_by_default='false', value_template=vt('AZM'), unit_of_measurement='°', icon='mdi:sun-compass'),
                ],
            },
            6: {
                'device_config': dcfg(command='ID', channel='ID'),
                'entities': [
                    entity('sensor', 'latitude', state_topic='ID6', enabled_by_default='false', value_template="{{ (value_json['LAT(MSB)']*256+value_json['LAT(LSB)'])*180/4095-90 }}", unit_of_measurement='°', icon='mdi:latitude'),
                    entity('sensor', 'longitude', state_topic='ID6', enabled_by_default='false', value_template="{{ (value_json['LOT(MSB)']*256+value_json['LOT(LSB)'])*360/4095-180 }}", unit_of_measurement='°', icon='mdi:longitude'),
                ],
            },
            7: {
                'device_config': dcfg(),
                'entities': [
                    sensor('wd', vt('WD'), state_class='measurement'),
                    sensor('aws', vt('AWS'), state_class='measurement', unit='mph'),
                    sensor('mws', vt('MWS'), state_class='measurement', unit='mph'),
                    sensor('bs', vt('BS'), device_class='battery', state_class='measurement'),
                ],
            },
            8: {
                'device_config': dcfg(),
                'entities': [
                    sensor('ras', vt('RAS'), state_class='measurement'),
                    sensor('rfa', vt('RFA'), state_class='measurement'),
                    sensor('rfc', vt('RFC'), state_class='measurement'),
                    sensor('bs', vt('BS'), device_class='battery', state_class='measurement'),
                ],
            },
            16: {
                'device_config': dcfg(),
                'entities': [
                    sensor('d_n', "{{ value_json['D/N'] }}", state_class='measurement'),
                    sensor('sne', vt('SNE'), state_class='measurement', unit='°'),
                    sensor('sna', vt('SNA'), state_class='measurement', unit='°'),
                    sensor('sra__msb', "{{ value_json['SRA (MSB)'] }}", state_class='measurement'),
                    sensor('sra__lsb', "{{ value_json['SRA (LSB)'] }}", state_class='measurement', unit='W/m2'),
                    sensor('id', vt('ID'), state_class='measurement'),
                ],
            },
        },
    },
}
