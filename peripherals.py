"""
  IO0 - IO21
  IO35 - IO48
  board_id -- bpi_leaf_s3
  NEOPIXEL -- board.IO48
  TX -- board.IO43
  RX -- board.IO44
  BUTTON -- board.IO0
  BOOT0 -- board.IO0
  SDA -- board.IO15
  SCL -- board.IO16
  MOSI -- board.IO35
  SCK -- board.IO36
  MISO -- board.IO37
  BATTERY -- board.BATTERY
  VBAT -- board.BATTERY
  VBAT_SENSE -- board.BATTERY
  VOLTAGE_MONITOR -- board.BATTERY
  I2C -- <function>
  STEMMA_I2C -- <function>
  SPI -- <function>
  UART -- <function>
"""

# Standard imports
import board
from analogio import AnalogIn

# Third party imports
import neopixel

# Local imports

# Globals

# TODO: Verify battery voltage conversion equation


class Peripherals():
    def __init__(self) -> None:
        # Neopixels
        self.neopixels = neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0.1)

        # Battery Voltage
        self._batt_monitor = AnalogIn(board.BATTERY)

    def deinit(self) -> None:
        """Call deinit on all resources to free them"""
        self.neopixels.deinit()
        self._batt_monitor.deinit()

    @property
    def battery(self) -> float:
        """Return the voltage of the battery"""
        return (self._batt_monitor.value / 65535.0) * 3.3 * 2
