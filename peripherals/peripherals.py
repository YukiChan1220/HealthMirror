import wiringpi
from .base import PeripheralsBase


class Peripherals(PeripheralsBase):
    def __init__(self) -> None:
        wiringpi.wiringPiSetup()
        