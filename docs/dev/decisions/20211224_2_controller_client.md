# Controller as connection client

Date: 2021/12/24

## Context

Currently, Spark services discover and then connect to a Spark controller.
The connection is long-running: the stream is kept open, regardless of whether any messages are being sent.

We have previously discussed making Brewblox available as remotely hosted service, to reduce the configuration burden on users.
This cloud-hosted option would not be free, and always be more restrictive than a locally hosted solution where the user is in full control of their software and hardware.
Because of this, a hosted solution will have to remain optional.

On a technical level, creating and maintaining a hosted solution would be a major development effort.
The solution being optional only increases the workload, as it runs parallel to the self-hosted version.
For these reasons, the idea of having a centrally hosted Brewblox was put on the back burner, but not completely abandoned.

In a [separate development](./20211224_1_protobuf_commands.md), we are reworking the command serialization protocol to be more suitable for a non-streamed context.

## Desired changes

Immediate results:
- synchronized blocks
- robust / standardized connections

Setup for future features:
- multi-location control
- secure connections
- hosted control

## Pairing services and controllers

Discovery protocol:
- Spark publishes mDNS service (unchanged)
- CLI sends server address/port/credentials to Spark
- CLI sends Spark ID to service

Connection protocol:
- Spark connects to predefined eventbus address
- Spark publishes device info, service decides whether it can interact

Sharing protocol:
- predefined topic / block type
- controllers are publisher or subscriber

## Messaging

- message ID is included in protobuf messages
- message ID is 0 for unprompted messages from the controller
- periodic updates are pushed as retained message
- Handshake info is pushed as retained message
- topics:
  - brewcast/cbox/v1/device/{DEVICE_ID}
  - brewcast/cbox/v1/request/{DEVICE_ID}
  - brewcast/cbox/v1/response/{DEVICE_ID}
  - brewcast/cbox/v1/blocks/{DEVICE_ID}
  - brewcast/cbox/v1/sync/{SYNC_ID}

## SSL

- Set SSL key during discovery
- Not immediately important
- Not sure whether it fits on spark 2/3

## Challenges

- Does the Spark 3 have memory space for a MQTT library?
  - https://github.com/redboltz/mqtt_cpp (C++, uses std::string)
  - https://mosquitto.org/api/files/mosquitto-h.html
  - https://github.com/eclipse/paho.mqtt.c (C, also used by python services)
- Can MQTT be implemented over USB, possibly with a USB->TCP repeater?
- How to handle OTA updates?
- Do we support multiple services per controller?
  - How to share block names between services?
  - How to avoid msgid conflicts? (include client ID in topic?)
