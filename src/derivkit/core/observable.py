"""Observable / Observer pattern for market data propagation."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class Observer(ABC):
    """Subscribes to observable changes and invalidates downstream caches."""

    @abstractmethod
    def update(self, observable: Observable, *args: Any, **kwargs: Any) -> None:
        """Called when the observed object changes."""


class Observable:
    """Base class for market observables with notify-on-update."""

    def __init__(self) -> None:
        self._observers: list[Observer] = []

    def attach(self, observer: Observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: Observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify(self, *args: Any, **kwargs: Any) -> None:
        for observer in self._observers:
            observer.update(self, *args, **kwargs)


class Quote(Observable):
    """Scalar market quote observable."""

    def __init__(self, value: float, instrument_id: str = "") -> None:
        super().__init__()
        self._value = float(value)
        self.instrument_id = instrument_id

    @property
    def value(self) -> float:
        return self._value

    @value.setter
    def value(self, new_value: float) -> None:
        if new_value != self._value:
            self._value = float(new_value)
            self.notify(value=self._value)
