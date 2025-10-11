from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PPGSample:
    timestamp: float
    red: Optional[int]
    ir: Optional[int]
    green: Optional[int]


class PPGBase(ABC):
    @abstractmethod
    def enable(self) -> None:
        """Power on the sensor and make it ready to stream data."""

    @abstractmethod
    def disable(self) -> None:
        """Put the sensor into low-power mode."""

    @abstractmethod
    def read_sample(self) -> PPGSample:
        """Return the next available sample from the device FIFO."""

    def close(self) -> None:
        self.disable()
