# Serial Frame Debugging

Use this guide when debugging Pace BMS serial data.

## Required Order

Decode values only after frame validity is confirmed.

1. Capture the raw frame.
2. Confirm the frame start byte.
3. Confirm frame termination.
4. Confirm frame length fields.
5. Confirm length checksum where present.
6. Confirm BMS address / pack address fields where present.
7. Confirm command type.
8. Confirm payload length.
9. Confirm checksum.
10. Decode values only after the frame is valid.

Never publish values from invalid frames.

## Pace ASCII Notes

The current supported protocol is Pace RS232/UART ASCII framing.

Do not assume Modbus RTU addressing or CRC behavior unless a future RS485 sprint proves from raw logs that the battery is using Modbus RTU.

If RS485 is investigated later, first identify whether traffic is still Pace ASCII (`0x7e` / `~` style frame start) or actual Modbus RTU.

## Invalid Frames

Reject:

- incomplete frames
- corrupt frames
- checksum-invalid frames
- frames with impossible length/payload mismatch
- frames that cannot be parsed without guessing

Log rejected frames only when debug output is high enough for troubleshooting. Do not spam normal logs.

## Current Code Pointers

- `bms_monitor.py`
  - checksum helpers
  - `bms_parse_response`
  - request/response transport
- `tests/test_core_behaviour.py`
  - valid frame parse test
  - bad checksum rejection test

