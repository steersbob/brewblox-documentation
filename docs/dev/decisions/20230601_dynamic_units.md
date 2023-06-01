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

## Migrations

- Block data stored in multiple places:
  - EEPROM protobuf
  - backups
  - widgets
  - layouts
  - exported files
- Assume temperature if not set otherwise

## Conclusions

- Unit type should be constant per block, as setting values cannot be converted
- Unit / unit type information should be encapsulated close to the value in JSON
- Firmware and UI can use same implementation for multiple interfaces -> primary issue is data presentation
- Weak spots: protobuf metadata, arbitrary data in JSON
