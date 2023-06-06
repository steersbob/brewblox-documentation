# Dynamic computation units

## Context

- Now: temperature support only
- Desired: pressure, flow, voltage, and generic ADC
- Units are static notations in proto metadata
- Unit conversion is handled in service

## Firmware

- Must check for unit compatibility in input/output block
- Can infer unit type from input
- Value range is a concern for 24-bit CNL
- Implementation can remain unitless for setpoint, PID, profile, driver
- Can use non-SI units to keep values within 24-bit range

## Service

- Must convert between user units and system units for same unit type
- Convertion plumbing is in place
- Protobuf options metadata is problematic:
  - complexity
  - order-dependent properties
  - lack of third party support

## UI

- Very localized rendering: units should be encapsulated with value
- Unitless values are undesirable if user unit != system unit
- Non-zero defaults for temperatures
- Default values are converted to user units at point of use
- Unit group metadata desirable if not known from context
- (Partial) block data stored in widget/layout database
- If unit info is encapsulated, view components can be reused

## History

- Units must remain postfixed to force new fields on change

## API

- Settings can't be converted between groups. Invalid block data after changing dynamic unit.
- Unit group is a block level setting, but not for all blocks. Undesirable to make it a required field.

## Migrations

- Block data stored in multiple places:
  - EEPROM protobuf
  - backups
  - widgets
  - layouts
  - exported files
- Assume temperature if not set otherwise

## Constraints

- If a single field in `block.data` is changed to valid value, the block must remain valid in its entirety.
- If `block.type` is changed, the block does not have to remain valid.

## Conclusions

- Unit group should be constant per block, as setting values cannot be converted
- Unit / unit type information should be encapsulated close to the value in JSON
- Firmware and UI can use same implementation for multiple interfaces -> primary issue is data presentation
- Weak spots: protobuf metadata, arbitrary data in JSON
- Unit group should not be a field in `block.data`
- Unit group should not be a separate (required) field in `block`.

## Implementation

- Unit groups values are predefined.
- Any support for custom unit use will be downrendered to some variation of "Custom" in actual types.
- Unit group is a separate field in proto, defined in payload.
- The 0-value for unit group is Temperature
  - Temperature is relevant to most use cases
  - Existing values automatically being considered Temperature simplifies migration
  - Proto strips default values, making it most efficient to encode
- Unit group is part of the type string in JSON.
- Same proto block message is used for all values of unit group.
- Encoding of type string is `{BaseType}:{UnitGroup}`.
  - `Pid:Temperature`
  - `Setpoint:Pressure`
- `Pid` is considered equal to `Pid:Temperature`
- Existing block types that refer to unit groups (*TempSensorOneWire*, *TempSensorExternal*, etc) are valid but automatically migrated to a generic new name.

## Side notes

- Pid will be refactored to use percentage output instead of unitless
- Setpoint Driver will have a new implementation that receives percentage input, and has a range setting to convert percentage to delta quantities.
