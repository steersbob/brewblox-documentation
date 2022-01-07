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

Changes can be grouped in two categories: changes we want to implement now,
and changes we want to make easier to implement at a future date.

As an immediate result, we want the following:
- Controllers can directly synchronize block values, without the intervention of Spark services.
- Controllers use a standardized connection protocol.

The immediate changes should make it easier to implement:
- Controllers can simultaneously communicate with multiple services.
- The controller-service connection is encrypted and authenticated.
- Controllers are compatible with cloud-hosted services.

In practical terms, we are looking to implement this by having the controller connect to the existing MQTT eventbus.
This way, there only needs to be a single public point of entry for multiple controllers.
The pub/sub nature of MQTT allows for networked communication between controllers and services,
where no additional connections are required for inter-controller communication.

## Pairing services and controllers

With the inversion of client and server in the controller-service connection,
we also need to invert the discovery and pairing routines.

With this change, the two will become more distinct: discovery is no longer an inherent part of pairing.
We'll first look at LAN connections (ethernet or Wifi), and then determine what additional steps must
be taken to also support USB.

The first step is discovery. If the controller is to be a client, it must be aware of the server's address.
This server address can be set by brewblox-ctl using a REST endpoint on the controller.
To do this, brewblox-ctl must be aware of the controller address, and the server address.
We can discover the controller address in the same way as we do now (mDNS),
and make a best effort guess for the server address.

We can set the server address in three possible ways, all of them having their own drawbacks:
- IP addresses can and will change regularly as DHCP leases expire.
- host names may not be resolved by the local network, and it is not unlikely for there to be multiple `raspberrypi` devices.
- mDNS services may also not always be resolved, and require an unique identifier to support multiple independent Brewblox systems.

This can partially be resolved by supplying the controller with a list of addresses.
The controller will attempt to connect to them in order, and use the first viable.

For the controller connection, references to the service are not required.
The controller always connects to the eventbus, and will respond to any requests on the appropriate topic.

Controller-service pairing can be handled exclusively by the service.
The service discovers controllers by subscribing to an MQTT topic that contains device information.
This device information is a direct replacement for the current handshake, containing device ID and firmware versions.

## USB support

USB connections will require a server-side USB-TCP bridge.
The bridge will connect to the Brewblox eventbus, and forward messages between the eventbus and the controller.
Given the public accessibility of the eventbus, the bridge does not have to be on the same server as the Brewblox installation.

Service-side, there is no functional difference between direct (TCP), and bridged (USB) connections.
Controller-side, there are two possible implementations:
- The controller implements the MQTT protocol in a transport-agnostic way, utilizing either USB or TCP.
  - The bridge does not modify traffic in any way, but only shuffles data between streams.
- The controller implements a custom USB-specific message protocol.
  - The bridge converts messages between this protocol and MQTT.

The first option is conceptually more elegant, but may end up being more complicated.
It requires the MQTT implementation to be transport-agnostic, while most common MQTT libraries assume TCP,
and will create and maintain their own socket based on host + port arguments.

The second implementation benefits from being straightforward, but does require a separate wire protocol for USB messages.
This can be as simple as `{TOPIC},{PAYLOAD}\n`, but this would have to be extended
if we implement dynamic values for qos, user data, ttl, or any other MQTT properties.

## Inter-controller synchronization

When synchronizing blocks, it would be very fragile to rely on block names, as they are stored in the database.
Instead, we can add a new *Synchronization* block, where data contains a list of shared objects.
Each shared object has the following properties:
- Local block
- Shared type or interface
- Sharing ID
- mode (publisher, subscriber)

For published blocks, the data is periodically published to a predetermined MQTT topic using the sharing ID.
For subcribed blocks, the *Synchronization* block watches the MQTT topic, and updates local values whenever a message is published.

Either a constant or a configurable Time To Live (TTL) should be associated with each shared object.
The *Synchronization* block should disable or otherwise invalidate subscribed blocks if no update has been published during the TTL period.

This system works best with a single publisher and zero or more subscribers,
but will not immediately fail if there are multiple publishers.
Whether this is desirable (no hard errors, and graceful fallback) or not (no immediate feedback on configuration errors) is not immediately clear.

## Messaging

For communication, five separate categories can be identified, which are easily mapped to MQTT topics:
- brewcast/cbox/v1/device/{DEVICE_ID}
- brewcast/cbox/v1/request/{DEVICE_ID}
- brewcast/cbox/v1/response/{DEVICE_ID}
- brewcast/cbox/v1/notification/{DEVICE_ID}
- brewcast/cbox/v1/sync/{SYNC_ID}/{PROTO_VERSION}

**Handshake messages: brewcast/cbox/v1/device/{DEVICE_ID}**
Retained plaintext messages describing the controller device ID and firmware versions.
This is a direct replacement to the current controlbox handshake.
Device messages should be retained, but removed on disconnect.

**Service requests: brewcast/cbox/v1/request/{DEVICE_ID}**
Requests from the service to the controller.
All messages on this topic will be encoded `ControlboxRequest` protobuf messages.

**Controller responses: brewcast/cbox/v1/response/{DEVICE_ID}**
Responses from the controller to earlier requests.
All messages on this topic will be encoded `ControlboxResponse` protobuf messages.

Responses are matched to requests by having the same `msgId` field.

**Controller state: brewcast/cbox/v1/notification/{DEVICE_ID}**
Unprompted event messages from the controller.
These can be used for error notifications, and when new hardware is connected or disconnected.
At the time of writing, it is not yet decided whether this should be plaintext or encoded protobuf.
This would depend on how many types of notification we want to support.

**Synchronized blocks: brewcast/cbox/v1/sync/{SYNC_ID}/{PROTO_VERSION}**
Updates to synchronized blocks, as described above.
All messages on this topic will be encoded `ControlboxSynchronization` protobuf messages.

The proto version is included to ensure synchronization only happens between compatible firmware versions.

## Challenges

- Does the Spark 3 have memory space for a MQTT library?
  - https://github.com/redboltz/mqtt_cpp (C++, uses std::string)
  - https://mosquitto.org/api/files/mosquitto-h.html
  - https://github.com/eclipse/paho.mqtt.c (C, also used by python services)
- Can MQTT be implemented using USB transport?
- How to handle OTA updates?
- Do we support multiple services per controller?
  - How to share block names between services?
  - How to avoid msgid conflicts? (include client ID in topic?)
  - Add a separate topic for periodic LIST_OBJECTS output?
