import threading
import time
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple, Union

from smbus2 import SMBus

from .base import PPGBase, PPGSample


@dataclass(frozen=True)
class MAX30101Config:
    sample_rate_hz: int = 1600
    led_mode: int = 3
    adc_range: int = 16384
    pulse_width: int = 411
    sample_average: int = 1
    fifo_rollover: bool = True
    led_currents: Tuple[int, int, int] = (0xE0, 0xE0, 0xE0)


class MAX30101(PPGBase):
    DEFAULT_ADDRESS = 0x57
    PART_ID_EXPECTED = 0x15

    _REG_INT_STATUS_1 = 0x00
    _REG_INT_ENABLE_1 = 0x02
    _REG_FIFO_WR_PTR = 0x04
    _REG_FIFO_OVF_COUNTER = 0x05
    _REG_FIFO_RD_PTR = 0x06
    _REG_FIFO_DATA = 0x07
    _REG_FIFO_CONFIG = 0x08
    _REG_MODE_CONFIG = 0x09
    _REG_SPO2_CONFIG = 0x0A
    _REG_LED1_PA = 0x0C
    _REG_LED2_PA = 0x0D
    _REG_LED3_PA = 0x0E
    _REG_MULTI_LED_CTRL1 = 0x11
    _REG_MULTI_LED_CTRL2 = 0x12
    _REG_TEMP_INT = 0x1F
    _REG_TEMP_FRAC = 0x20
    _REG_TEMP_CONFIG = 0x21
    _REG_PART_ID = 0xFF

    _LED_MODE_MAP = {1: 0x02, 2: 0x03, 3: 0x07}
    _SAMPLE_RATE_MAP = {50: 0x00, 100: 0x04, 200: 0x08, 400: 0x0C, 800: 0x10, 1000: 0x14, 1600: 0x18, 3200: 0x1C}
    _PULSE_WIDTH_MAP = {69: 0x00, 118: 0x01, 215: 0x02, 411: 0x03}
    _ADC_RANGE_MAP = {2048: 0x00, 4096: 0x20, 8192: 0x40, 16384: 0x60}
    _SAMPLE_AVERAGE_MAP = {1: 0x00, 2: 0x20, 4: 0x40, 8: 0x60, 16: 0x80, 32: 0xA0}

    def __init__(
        self,
        bus: Union[int, SMBus] = 4,
        address: int = DEFAULT_ADDRESS,
        config: Optional[MAX30101Config] = None,
        auto_start: bool = False,
    ) -> None:
        self.address = address
        if isinstance(bus, SMBus):
            self._bus = bus
            self._own_bus = False
        else:
            self._bus = SMBus(bus)
            self._own_bus = True
        self.config = config or MAX30101Config()
        self._enabled = False
        self._validate_part()
        self.configure(self.config)
        if auto_start:
            self.enable()

    def __enter__(self) -> "MAX30101":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    def close(self) -> None:
        super().close()
        if getattr(self, "_own_bus", False):
            self._bus.close()

    def enable(self) -> None:
        self._write_reg(self._REG_MODE_CONFIG, self._LED_MODE_MAP[self.config.led_mode])
        self._clear_fifo()
        self._enabled = True

    def disable(self) -> None:
        if not self._enabled:
            return
        mode = self._read_reg(self._REG_MODE_CONFIG)
        self._write_reg(self._REG_MODE_CONFIG, mode | 0x80)
        self._enabled = False

    def reset(self) -> None:
        self._write_reg(self._REG_MODE_CONFIG, 0x40)
        time.sleep(0.01)

    def configure(self, config: MAX30101Config) -> None:
        if config.led_mode not in self._LED_MODE_MAP:
            raise ValueError("Unsupported LED mode")
        if config.sample_rate_hz not in self._SAMPLE_RATE_MAP:
            raise ValueError("Unsupported sample rate")
        if config.pulse_width not in self._PULSE_WIDTH_MAP:
            raise ValueError("Unsupported pulse width")
        if config.adc_range not in self._ADC_RANGE_MAP:
            raise ValueError("Unsupported ADC range")
        if config.sample_average not in self._SAMPLE_AVERAGE_MAP:
            raise ValueError("Unsupported sample average")

        self.config = config
        self.disable()
        self._write_reg(self._REG_FIFO_CONFIG, self._SAMPLE_AVERAGE_MAP[config.sample_average] | (0x10 if config.fifo_rollover else 0x00) | 0x0F)
        self._write_reg(
            self._REG_SPO2_CONFIG,
            self._ADC_RANGE_MAP[config.adc_range] | self._SAMPLE_RATE_MAP[config.sample_rate_hz] | self._PULSE_WIDTH_MAP[config.pulse_width],
        )
        self._write_reg(self._REG_LED1_PA, min(config.led_currents[0], 0xFF))
        self._write_reg(self._REG_LED2_PA, min(config.led_currents[1], 0xFF))
        self._write_reg(self._REG_LED3_PA, min(config.led_currents[2], 0xFF))
        if config.led_mode == 3:
            self._write_reg(self._REG_MULTI_LED_CTRL1, 0x21)
            self._write_reg(self._REG_MULTI_LED_CTRL2, 0x03)
        else:
            self._write_reg(self._REG_MULTI_LED_CTRL1, 0x21)
            self._write_reg(self._REG_MULTI_LED_CTRL2, 0x00)
        self._clear_fifo()
        if self._enabled:
            self.enable()

    def read_sample(self) -> PPGSample:
        if not self._enabled:
            raise RuntimeError("Sensor is not enabled")
        sample = self._read_fifo()
        return PPGSample(time.time(), *sample)

    def read_samples(self, count: int) -> Iterable[PPGSample]:
        for _ in range(count):
            yield self.read_sample()

    def temperature(self) -> float:
        self._write_reg(self._REG_TEMP_CONFIG, 0x01)
        time.sleep(0.01)
        integer = self._read_reg(self._REG_TEMP_INT)
        fraction = self._read_reg(self._REG_TEMP_FRAC)
        return integer + (fraction * 0.0625)

    def _read_fifo(self) -> Tuple[Optional[int], Optional[int], Optional[int]]:
        led_count = self.config.led_mode if self.config.led_mode <= 3 else 3
        sample_size = led_count * 3
        data = self._read_block(self._REG_FIFO_DATA, sample_size)
        values = []
        for i in range(0, sample_size, 3):
            raw = ((data[i] << 16) | (data[i + 1] << 8) | data[i + 2])
            values.append(raw & 0x3FFFF)
        while len(values) < 3:
            values.append(None)
        return values[0], values[1], values[2]

    def _clear_fifo(self) -> None:
        self._write_reg(self._REG_FIFO_WR_PTR, 0x00)
        self._write_reg(self._REG_FIFO_OVF_COUNTER, 0x00)
        self._write_reg(self._REG_FIFO_RD_PTR, 0x00)
        self._read_reg(self._REG_INT_STATUS_1)

    def _validate_part(self) -> None:
        part_id = self._read_reg(self._REG_PART_ID)
        if part_id != self.PART_ID_EXPECTED:
            raise RuntimeError(f"Unexpected part id: 0x{part_id:02X}")

    def _write_reg(self, register: int, value: int) -> None:
        self._bus.write_byte_data(self.address, register & 0xFF, value & 0xFF)

    def _read_reg(self, register: int) -> int:
        return self._bus.read_byte_data(self.address, register & 0xFF) & 0xFF

    def _read_block(self, register: int, length: int) -> List[int]:
        data = self._bus.read_i2c_block_data(self.address, register & 0xFF, length)
        return [value & 0xFF for value in data]
