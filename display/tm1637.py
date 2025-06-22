import threading
import time
import wiringpi
from wiringpi import GPIO

class TM1637:
    def __init__(self, data_pin, clk_pin):
        # A reentrant lock ensures multi-thread safety.
        self.lock = threading.RLock()
        self.data_pin = data_pin
        self.clk_pin = clk_pin
        wiringpi.pinMode(self.data_pin, GPIO.OUTPUT)
        wiringpi.pinMode(self.clk_pin, GPIO.OUTPUT)

    # Basic protocol operations
    def _start(self):
        """Send the start signal."""
        self._io_set_data(1)
        self._io_set_clk(1)
        self._io_delay()
        self._io_set_data(0)
        self._io_delay()
        self._io_set_clk(0)
        self._io_delay()

    def _stop(self):
        """Send the stop signal."""
        self._io_set_clk(0)
        self._io_delay()
        self._io_set_data(0)
        self._io_delay()
        self._io_set_clk(1)
        self._io_delay()
        self._io_set_data(1)
        self._io_delay()

    def _write_byte(self, byte):
        """Write a byte to the TM1637 device."""
        for i in range(8):
            self._io_set_clk(0)
            bit = (byte >> i) & 0x01
            self._io_set_data(bit)
            self._io_delay()
            self._io_set_clk(1)
            self._io_delay()
        # Wait for the acknowledgement
        self._io_set_clk(0)
        self._io_set_data(1)  # Release the data line for ACK
        self._io_delay()
        self._io_set_clk(1)
        self._io_delay()
        ack = self._io_read_data()  # User must define this to read actual ACK signal
        self._io_set_clk(0)
        return ack

    def display(self, digits):
        """
        Display digits on the 4-digit 7-segment display.
        `digits` should be an iterable of 4 integers (0-9). Non-digit values will be blank.
        """
        # A simple mapping from numbers to 7-segment codes
        segments = [0x3F, 0x06, 0x5B, 0x4F,
                    0x66, 0x6D, 0x7D, 0x07,
                    0x7F, 0x6F]
        # Prepare the data; if a digit is invalid, show a blank (0x00)
        data = [segments[d] if 0 <= d <= 9 else 0x00 for d in digits]

        # Use the lock to make the complete display update thread-safe.
        with self.lock:
            # Command to set auto-increment mode.
            self._start()
            self._write_byte(0x40)
            self._stop()

            # Set starting address at 0 and send data.
            self._start()
            self._write_byte(0xC0)
            for d in data:
                self._write_byte(d)
            self._stop()

            # Command to set display control (display on, brightness = 7/8).
            self._start()
            self._write_byte(0x88)
            self._stop()

    # --- I/O operation stubs ---
    def _io_set_data(self, value):
        """
        Set the data line to high (1) or low (0).
        Users should implement hardware-specific operations here.
        """
        if value == 1:
            wiringpi.digitalWrite(self.data_pin, GPIO.HIGH)
        elif value == 0:
            wiringpi.digitalWrite(self.data_pin, GPIO.LOW)
        pass

    def _io_set_clk(self, value):
        """
        Set the clock line to high (1) or low (0).
        Users should implement hardware-specific operations here.
        """
        if value == 1:
            wiringpi.digitalWrite(self.clk_pin, GPIO.HIGH)
        elif value == 0:
            wiringpi.digitalWrite(self.clk_pin, GPIO.LOW)
        pass

    def _io_read_data(self):
        """
        Read the state of the data line.
        Users should implement hardware-specific operations here.
        Returns 1 if the line is high, or 0 if it is low.
        """
        return wiringpi.digitalRead(self.data_pin)

    def _io_delay(self):
        """
        Delay for a short period to allow the hardware to settle.
        Users can adjust the delay time as per hardware requirements.
        """
        time.sleep(0.001)
