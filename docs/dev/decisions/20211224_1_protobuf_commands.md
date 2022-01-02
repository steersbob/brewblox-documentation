# Protobuf-based commands

Date: 2021/12/24

## Context

At the time of writing, the Spark service communicates with the Spark controller using a serial stream.
For the Spark 2/3, this is either USB or TCP. For the Spark 4, only TCP is supported, with ethernet replacing USB as the wired option.

Commands are transmitted using the custom *[Controlbox](https://github.com/BrewBlox/brewblox-documentation/blob/40f290f0026acc15088607e7df44984e1a9b41af/docs/dev/reference/controlbox_spark_protocol.md)* protocol.
This protocol fulfills three major requirements:
- it has very little overhead.
- it supports interleavened event messages.
- messages are deliminated, and can be streamed.

Payload data is split between metadata (block ID, type, groups) which is sent using Controlbox, and block data, which is first encoded using Protobuf, and then appended as bytes.

## Desired changes

There are three changes we want to make to the communication protocol:
- Messages must be suitable for a non-streamed / message-based transport.
- Reduce or remove custom protocol components.
- Support stored procedure calls.

Technically, the current implementation already satisfies the first requirement, but right now this is coincidental.
Going forward, we want this behavior to be explicit.

## Protobuf

While protobuf is not a perfect fit (we do significant pre- and post-processing of values), we see no clearly superior alternative.
If we want to use a single protocol for wire messages, then the obvious choice is to replace controlbox with protobuf.

## Generic + specific messages

Protobuf messages are not self-identifying. The decoder must be told explicitly which message descriptor should be used.
We can replace the controlbox protocol with a standard protobuf message,
but messages would remain partially dynamic. For example, the *List Objects* command (read all blocks on controller), should then be typed as a list of a union of every block type.
Technically, this can be done by declaring a OneOf protobuf field, but having a OneOf with every single block type is incredibly ugly.

This can be resolved in much the same way as it is now: payloads are expressed using two fields: an descriptor identifier, and a `bytes` field that contains a protobuf-encoded submessage.

We want to group stored procedures by block type, and support multiple procedures per type.
This means that the current descriptor identifier as used in the controlbox spec is no longer sufficient: we need more fine-grained specification.

To avoid polluting the `BlockType` protobuf enum type, we'd rather store the extra information in an additional field.
The message descriptor lookup is then done using `objtype` + `subtype`.

In pseudo-code, this would look like:
```python
encoded = proto_encode({
  "objtype": 1234,
  "subtype": 2,
  "payload": proto_encode(block_data),
})
```

## Implementation

To implement fully qualified message type descriptors, we extend the existing `BrewbloxMessageOptions` with a `subtype` field:

```protobuf
message BrewbloxMessageOptions {
  option (nanopb_msgopt).skip_message = true;
  optional BrewbloxTypes.BlockType objtype = 3;
  repeated BrewbloxTypes.BlockType impl = 9 [ (nanopb).max_count = 5 ];
  optional uint32 subtype = 11 [ (nanopb).int_size = IS_16 ];
}

extend google.protobuf.MessageOptions { BrewbloxMessageOptions brewblox_msg = 50001 [ (nanopb).type = FT_IGNORE ]; }
```

We define basic messages for requests and response. The Spark parses all incoming messages using the request descriptor, and the service parses all incoming messages using the response descriptor.

The payload for responses can be repeated (eg. list objects), but there are no repeated payloads for requests.

Note that the payload message no longer includes `groups`. This was a deprecated field in the controlbox spec.

```protobuf
message ControlboxPayload {
  optional uint32 blockId = 1;
  optional BrewbloxTypes.BlockType objtype = 2;
  optional uint32 subtype = 3 [ (nanopb).int_size = IS_16 ];
  optional bytes data = 4;
}

message ControlboxRequest {
  optional uint32 msgId = 1;
  optional ControlboxTypes.Opcode opcode = 2;
  optional ControlboxPayload payload = 3;
}

message ControlboxResponse {
  optional uint32 msgId = 1;
  optional ControlboxTypes.ErrorCode error = 2;
  repeated ControlboxPayload payload = 3;
}
```

Example implementation:

```protobuf
syntax = "proto3";

import "brewblox.proto";
import "nanopb.proto";

package blox.SetpointSensorPair;

enum FilterChoice {
  FILTER_NONE = 0;
  FILTER_15s = 1;
  FILTER_45s = 2;
  FILTER_90s = 3;
  FILTER_3m = 4;
  FILTER_10m = 5;
  FILTER_30m = 6;
}

message SetpointSensorPair {
  option (brewblox_msg).objtype = SetpointSensorPair;
  option (brewblox_msg).impl = ProcessValueInterface;
  option (brewblox_msg).impl = SetpointSensorPairInterface;

  uint32 sensorId = 2 [ (brewblox).objtype = TempSensorInterface, (nanopb).int_size = IS_16 ];

  sint32 setting = 5 [ (brewblox).logged = true, (brewblox).unit = Celsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32, (brewblox).readonly = true ];
  sint32 value = 6 [ (brewblox).logged = true, (brewblox).unit = Celsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32, (brewblox).readonly = true ];
  bool settingEnabled = 7;
  sint32 storedSetting = 8 [ (brewblox).logged = false, (brewblox).unit = Celsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32 ];

  FilterChoice filter = 9;
  sint32 filterThreshold = 10 [ (brewblox).unit = DeltaCelsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32 ];

  sint32 valueUnfiltered = 11 [ (brewblox).logged = true, (brewblox).unit = Celsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32, (brewblox).readonly = true ];
  bool resetFilter = 12;

  repeated uint32 strippedFields = 99 [ (brewblox).readonly = true, (nanopb).int_size = IS_16, (nanopb).max_count = 3 ];
}

message Setting {
  option (brewblox_msg).objtype = SetpointSensorPair;
  option (brewblox_msg).subtype = 2;

  sint32 storedSetting = 8 [ (brewblox).logged = false, (brewblox).unit = Celsius, (brewblox).scale = 4096, (nanopb).int_size = IS_32 ];
}

```

With this implementation, we do not need a separate opcode for stored procedures, but can declare a submessage per procedure, and use the `WRITE_OBJECT` opcode.

In the service API, message types are converted to `.`-separated names.
To remain backwards compatible, the second group can be omitted for the default block.

Using the above `SetpointSensorPair` implementation, you can write the entire block using:
```json
{
  "id": "setting",
  "type": "SetpointSensorPair",
  "serviceId": "spark-one",
  "data": {
    ... // all block fields
  }
}
```

Apart from the removal of the `groups` field, this is unchanged from the current API.

The `Setting` procedure can be called by writing
```json
{
  "id": "setting",
  "type": "SetpointSensorPair.Setting",
  "serviceId": "spark-one",
  "data": {
    "storedSetting": {...}
  }
}
```
