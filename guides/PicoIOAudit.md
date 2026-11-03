# PicoIO hardware and integration audit

Investigation date: 2026-10-31. Planning only; no GPIO app or hardware tests
have been implemented by this audit.

## Confirmed device baseline

- User confirms a Raspberry Pi Pico 2 W in a PicoCalc, with no altered wiring.
- Keyboard/STM32 firmware has been updated, but its installed version and
  source are unknown. Do not identify it from the GungOS build version.
- Physical GPIO equipment is expected on Tuesday, 2026-11-03. Electrical
  verification is deferred until equipment is available.
- GungOS is built from this repository. Its current board declaration is
  `src/MicroPython/picoware/system/boards.py`; release builds select
  `RPI_PICO2_W` in `tools/build-gungos-release.sh`.

## Main finding

The stock side headers are not two banks of freely usable GPIO. Most of the
core header is connected to the PSRAM that GungOS actively uses. The other
header includes Pico UART, STM32 UART, and USB signals shared with onboard
circuitry. Initially allow only GP28 as a candidate for general-purpose
control, subject to physical verification. Describe the other connections
accurately and keep them unavailable for general control.

Earlier proposals for multiple free channels, an external bus scanner, and
immediate STM32 GPIO control were provisional. Stock wiring and the current
firmware do not establish those capabilities.

## Header map from the official V2.0 schematic

These are schematic connector pin numbers, not instructions for counting
contacts from the outside of the case. Physical orientation and the device's
connector labels still need checking before wiring.

### J703: core expansion header

| Contact | Schematic signal | GungOS use / proposed policy |
| --- | --- | --- |
| 1 | 3V3_OUT | Power, not a configurable signal |
| 2 | GP2 | PSRAM data 0: locked |
| 3 | GP3 | PSRAM data 1: locked |
| 4 | GP4 | PSRAM data 2: locked |
| 5 | GP5 | PSRAM data 3: locked |
| 6 | GP21 | PSRAM clock: locked |
| 7 | GP28 | Candidate digital input/output, pulls, PWM, or ADC2 |
| 8 | GND | Ground, not a configurable signal |

The Pico's default I2C pin pair GP4/GP5 is therefore unavailable. Do not
copy generic Pico I2C examples into PicoIO or temporarily steal PSRAM pins.

### J702: mixed communications / STM32 header

| Contact | Schematic signal | Connection / proposed policy |
| --- | --- | --- |
| 1 | MCU_3V3 | STM32-side power rail; not configurable |
| 2 | UART0_RX | Pico GP1; also connected to selectable onboard USB-UART path |
| 3 | UART0_TX | Pico GP0; also connected to selectable onboard USB-UART path |
| 4 | M_UART1_TX | STM32 PA9; shared with selectable onboard USB-UART path |
| 5 | M_UART1_RX | STM32 PA10; shared with selectable onboard USB-UART path |
| 6 | M_USB_DP | STM32 PA12; USB data path, not general-purpose GPIO |
| 7 | M_USB_DM | STM32 PA11; USB data path, not general-purpose GPIO |
| 8 | GND | Ground, not configurable |

The schematic's DEBUG block contains CH340C and WAS7227 switching, controlled
by SEL1/SEL2. These routes matter even when no external module has been added.
In particular, UART receive nets may have an onboard driver. Do not enable
arbitrary output modes on them based only on the Pico pin's capabilities.
Do not infer switch positions from firmware or assume the header name means
every signal belongs to the STM32.

## Internal resources to protect

| Core pins | Owner | Local source |
| --- | --- | --- |
| GP2-5, GP20-21 | PSRAM data, select, clock | `src/MicroPython/PicoCalc/picoware_psram/psram_qspi.h` |
| GP6-7 | STM32 keyboard/system I2C1 | `src/MicroPython/PicoCalc/picoware_keyboard/southbridge.h` |
| GP8-9 | Link to STM32 UART3 | Official schematic PICO/MCU blocks |
| GP10-15 | Display wiring | `src/MicroPython/PicoCalc/picoware_lcd/lcd.h` |
| GP16-19, GP22 | SD SPI0 and card detect | `src/MicroPython/sd/sd_config.h` |
| GP23-25, GP29 | Pico 2 W onboard wireless-related signals | `vendor/micropython/lib/pico-sdk/src/boards/include/boards/pico2_w.h` |
| GP26-27 | Audio PWM outputs | `src/MicroPython/pcm/pcm.c` |
| GP0-1 | Existing serial terminal and onboard USB-UART routing | `src/MicroPython/picoware/system/uart.py`, official DEBUG block |

Reserve resources as well as pins: hardware UART/SPI/I2C instances, PWM
slices/channels, and any future PIO/DMA resources. A free hardware peripheral
does not imply its externally accessible pins are free. The pinned SDK maps
GP28 to PWM slice 6, channel A (also mapped by GP12); audio on GP26/GP27 uses
slice 5. No current PWM owner for slice 6 was found in the inspected sources,
but the ownership service must reserve it explicitly before enabling GP28
PWM. Display use of GP12 is not itself PWM use.

## STM32 support boundary

GungOS currently contains the host-side keyboard/system driver, not the
STM32 firmware project used to update this particular device. Its native
extension exposes keyboard, battery, backlight, reset, and power-off
functions; it does not expose GPIO configuration or firmware version.

ClockworkPi's inspected upstream keyboard source defines a version register
at 0x01. Its request handler returns two bytes with BIOSVERSION in the second
byte. The inspected upstream constant is 0x16; this is NOT evidence that the
user's device has that version. Unknown/custom firmware may differ.

The inspected upstream I2C command handler has no general-purpose GPIO mode,
read, or write commands. `port.ino` contains internal GPIO helper functions;
those functions do not constitute a host-accessible GPIO protocol. Upstream
also initializes Serial1 on PA10/PA9 at 115200 for diagnostic messages.

First implementation should offer a version-read diagnostic through the
existing native southbridge path, with bounded errors and the same bus
coordination used by keyboard polling. Do not create/reconfigure a second
Python I2C instance on GP6/GP7. A version value alone is insufficient to
enable GPIO features; require a known protocol/capability contract. STM32
GPIO control remains unavailable until that contract is established.

## GungOS integration findings

- Proposed location: Comms > GPIO; the app/title can be PicoIO. No PicoLAB
  launcher entry is needed.
- `src/MicroPython/picoware/applications/library.py` owns the Comms category
  and launch routes. Currently Comms contains Bluetooth, USB, and WiFi.
- Serial Terminal currently lives under Utils and uses GP0/GP1 via
  `view_manager.uart`. Avoid an unrelated menu reorganization in the first pass.
- The UART object is created lazily and retained by ViewManager. Closing
  Serial Terminal restores its callback and drops the app's reference, but
  does not release the retained hardware UART. Ownership cannot be inferred
  merely from which page is visible.
- Implement shared ownership before allowing PicoIO and Serial to configure
  overlapping resources. Registration of board-owned resources must precede
  any editable pin selection.
- Verify simulator route metadata and firmware packaging when adding the app.

## Revised first-version scope

1. Show both schematic headers, their functions, owners, and locked reasons.
   Use a list/details layout initially; do not invent a physical orientation.
2. Support GP28 digital input with pulls, digital output, PWM, and ADC as
   mutually exclusive modes after the corresponding hardware checks.
3. Start disarmed, require an explicit Apply/Run action to drive a pin, and
   save profiles without automatically driving outputs on load.
4. Stop PWM and release only app-owned resources on Stop, normal exit, and
   handled failures. Initial release policy: input with no pull. External
   circuits requiring a defined state need suitable external biasing; this
   is not an emergency-stop guarantee during crashes or power loss.
5. Show live readings and clear error/unavailable states. ADC voltage display
   is an estimate based on the reference assumption, not a calibrated meter.
6. Provide an STM32 version diagnostic; keep unsupported STM32 GPIO disabled.

Defer external I2C/SPI tools, multi-channel capture, sequences, and STM32 GPIO
control until there is a verified electrical/protocol path. An external
controller or deliberate hardware/firmware changes could expand this later.

## Validation when equipment arrives

Before physical work, simulator checks should cover locked-pin refusal,
resource conflicts, disarmed profile loading, mode changes, bounded device
errors, and cleanup. Simulated readings are not electrical validation.

Physical sequence:

1. Check connector orientation, labels, switch positions, and board revision.
2. Establish the STM32 firmware version through the diagnostic, if supported.
3. With power removed, check the expected header connections where practical;
   then measure the power rail and idle GP28 behavior after powering up.
4. Test GP28 output with an LED and series resistor, then input with a button.
5. Check Stop/exit/mode changes, then PWM with suitable measurement equipment.
   A basic multimeter/LED does not verify pulse timing or frequency accuracy.
6. Test ADC with a potentiometer between the verified 3.3 V rail and ground,
   comparing the wiper reading with the multimeter. Keep signals within the
   core's permitted voltage range; do not apply a 5 V signal to GP28.
7. Repeat while display, SD, audio, and wireless activity run to expose shared
   resource problems. Check GP0/GP1 and bridge routing separately before any
   later general GPIO reuse.

Useful equipment: breadboard, jumper leads matching the actual header
connectors, LEDs, 330 ohm-1 kohm series resistors, a pushbutton, a 10 kohm
potentiometer, and a multimeter. Timing qualification needs a scope or logic
analyzer later; it is not necessary for the initial static tests.

## Evidence and limits

Local code inspected at HEAD `d015beb2`, with existing unrelated working-tree
changes present. This audit adds documentation only and does not validate a
flashed image or identify the installed STM32 firmware.

Public upstream revision observed: `fdcfe2c87a56b6dbcd540e91de1161d483872af9`.
The public files were fetched from master during this investigation; the
revision links below provide the recorded reference for subsequent review.

- [Official mainboard V2.0 schematic](https://github.com/clockworkpi/PicoCalc/blob/fdcfe2c87a56b6dbcd540e91de1161d483872af9/clockwork_Mainboard_V2.0_Schematic.pdf): visually inspected full page and enlarged MCU/DEBUG/header regions.
- [STM32 keyboard command handling](https://github.com/clockworkpi/PicoCalc/blob/fdcfe2c87a56b6dbcd540e91de1161d483872af9/Code/picocalc_keyboard/picocalc_keyboard.ino).
- [STM32 register definitions](https://github.com/clockworkpi/PicoCalc/blob/fdcfe2c87a56b6dbcd540e91de1161d483872af9/Code/picocalc_keyboard/reg.h).
- [Upstream firmware constants](https://github.com/clockworkpi/PicoCalc/blob/fdcfe2c87a56b6dbcd540e91de1161d483872af9/Code/picocalc_keyboard/conf_app.h).
- [Internal STM32 GPIO helpers](https://github.com/clockworkpi/PicoCalc/blob/fdcfe2c87a56b6dbcd540e91de1161d483872af9/Code/picocalc_keyboard/port.ino).

Mainboard revision, header orientation, switch positions, electrical behavior,
and the installed keyboard firmware remain physical-device checks.
