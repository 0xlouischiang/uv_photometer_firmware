# M5Stack Port Feasibility

Analysis of whether this firmware can run on M5Stack hardware.

**Verdict:** possible, but it's a port rather than a copy. The display and the numeric
core carry over unchanged; buttons and battery sensing must be rewritten, and on the
ESP32-based Cores you lose the CIRCUITPY drive.

Verified against CircuitPython source (`ports/espressif/boards/*`,
`shared-module/busdisplay/BusDisplay.c`, `ports/espressif/mpconfigport.mk`). Not
flashed to hardware.

## What carries over free

CircuitPython officially supports 24 M5Stack boards, including Core Basic, Core Fire,
Core2, CoreS3 and CoreS3 SE. All Core-family boards define `board.DISPLAY` (320x240,
16-bit) in firmware, so `splash_screen.py`, `measure_screen.py`, `menu_screen.py` and
`message_screen.py` work as-is — they already derive geometry from
`board.DISPLAY.width/height`.

`ulab`, `keypad`, `analogio`, `busio` and `displayio` are all in the espressif builds
(`CIRCUITPY_FULL_BUILD ?= 1` in `ports/espressif/mpconfigport.mk`). The AS7331 driver
is pure Python over `adafruit_bus_device`, so `light_sensor.py` and the whole
absorbance/calibration path are board-agnostic. Some boards freeze
`adafruit_display_text` and `adafruit_display_shapes` into firmware, saving `lib/`
space.

## What breaks

### Buttons — the hard part

`colorimeter.py:57` uses `keypad.ShiftRegisterKeys` with
`board.BUTTON_CLOCK/BUTTON_OUT/BUTTON_LATCH`. Those pins are a PyBadge/PyGamer thing;
no M5Stack board has them, so this raises `AttributeError` at construction. The
firmware needs 8 keys.

- Core Basic / Core Fire expose three physical buttons (`BTN_A/B/C` = GPIO39/38/37,
  active-low). Three for eight means modal remapping, or wiring external buttons to
  free M5-bus GPIOs and using `keypad.Keys` — mechanically the same event API, so
  `handle_button_press` barely changes.
- Core2 / CoreS3 have **no** physical buttons at all — capacitive touch only, which
  needs a touch driver and a rewritten input layer.

### Battery monitoring

`constants.py:14` is `board.A6`.

- Core Basic has no `A6` at all (analog pins are A0/A2/A12/A13/A15/A25/A26/A34/A35/A36),
  so `constants.py` fails at import.
- CoreS3 *does* define `A6`, but it's GPIO6 on the M5 bus — ADC-capable, so
  `battery_monitor.py` runs and silently reports a garbage voltage. That's the worse
  failure.

None of these boards route battery voltage to a bare ADC pin: Core Basic reads coarse
25% levels from the IP5306 PMIC, Core2 uses AXP192 (I2C 0x34), CoreS3 uses AXP2101.
Each needs its own I2C read.

### Display brightness

`colorimeter.py:48` sets `board.DISPLAY.brightness = 1.0`. Works on Core Basic and Core
Fire, which pass a real PWM backlight pin (GPIO32). Core2 and CoreS3 pass `NULL` for
the backlight and `NO_BRIGHTNESS_COMMAND` — `common_hal_busdisplay_busdisplay_set_brightness`
returns false and the binding raises `RuntimeError("Brightness not adjustable")`. One
line, but a hard crash on those two boards.

### I2C bus choice

`light_sensor.py:13` does `busio.I2C(board.SCL, board.SDA)`. On Core Basic that happens
to be the Grove Port A connector, so it works. On Core2 and CoreS3, `board.SCL/SDA` is
the *internal* bus (PMIC, IMU, touch) and Port A is separate — the sensor should use
`board.PORTA_I2C`.

### No CIRCUITPY drive on ESP32 boards

`ports/espressif/mpconfigport.mk` sets `CIRCUITPY_USB_DEVICE = 0` for
`IDF_TARGET=esp32`, which covers Core Basic, Core Fire and Core2. No USB mass storage
means `src/upload.bash` is dead; deploy over the Wi-Fi web workflow or serial instead.
Only the ESP32-S3 boards (CoreS3, CoreS3 SE) keep the drag-and-drop drive.

### Memory

Each screen allocates a full-screen `displayio.Bitmap` (`measure_screen.py:35`). At
320x240 with 8 palette entries that's ~38 KB per screen versus ~10 KB at the original
160x128. Core Fire/Core2/CoreS3 have 8 MB PSRAM, no problem. Core Basic has none.
Given commit 09b6dce ("Changed how screens work to reduce memory use"), better to swap
that bitmap for a 1x1 scaled tile grid than to fight it.

### Layout

The hardcoded spacings and `padding_right = 160` in `menu_screen.py:76` were tuned for
160x128. Nothing crashes, but text renders small and off-position on a 320x240 panel.

## Recommendation

**CoreS3 or CoreS3 SE**, if a touch UI is acceptable: native USB keeps the CIRCUITPY
workflow, 8 MB PSRAM removes the memory question, 16 MB flash, and Port A gives a clean
dedicated I2C bus for the AS7331.

**Core Fire** is the alternative if physical buttons matter more than USB — 3 buttons
plus PSRAM, and the other 5 can go on the M5 bus via `keypad.Keys`.

Effort: rewrite the input layer and battery monitor, guard the brightness line, switch
to `PORTA_I2C`, retune four screens' geometry. Roughly 4 files, plus a `board_config`
indirection to keep both the Feather and M5Stack targets in one tree. The measurement
science — blanking, absorbance, calibrations — doesn't move.

## Open items to confirm on hardware

- Memory headroom on a PSRAM-less Core Basic.
- Exact PMIC battery registers (IP5306 / AXP192 / AXP2101).

## References

- [CoreS3](https://circuitpython.org/board/m5stack_cores3/)
- [CoreS3 SE](https://circuitpython.org/board/m5stack_cores3_se/)
- [Core Basic](https://circuitpython.org/board/m5stack_core_basic/)
- [CircuitPython downloads](https://circuitpython.org/downloads)
