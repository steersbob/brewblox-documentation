"""
Code example for publishing data to the Brewblox eventbus

Dependencies:
- paho-mqtt
"""

import json
from random import random
from ssl import CERT_NONE
from time import sleep

from paho.mqtt import client as mqtt

# 172.17.0.1 is the default IP address for the host running the Docker container
# Change this value if Brewblox is installed on a different computer
HOST = '172.17.0.1'

# This is a constant value. You never need to change it.
TOPIC = 'brewcast/history'

# Create a websocket MQTT client
client = mqtt.Client(transport='websockets')
client.ws_set_options(path='/eventbus')
client.tls_set(cert_reqs=CERT_NONE)
client.tls_insecure_set(True)

try:
    client.connect_async(host=HOST, port=443)
    client.loop_start()

    value = 20

    while True:
        # https://brewblox.netlify.app/dev/reference/event_logging.html
        value += ((random() - 0.5) * 10)
        message = {
            'key': 'pubscript',
            'data': {'value[degC]': value}
        }

        client.publish(TOPIC, json.dumps(message))
        print(f'sent {message}')
        sleep(5)

finally:
    client.loop_stop()