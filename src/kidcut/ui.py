from collections.abc import Callable
from typing import TypeVar

from rich.console import Console

T = TypeVar("T")


def run_with_spinner(console: Console, message: str, fn: Callable[[], T]) -> T:
    with console.status(message, spinner="dots"):
        return fn()
