from kidscan.ui import run_with_spinner
from rich.console import Console


def test_run_with_spinner_returns_function_result():
    console = Console()
    result = run_with_spinner(console, "Testing", lambda: 42)
    assert result == 42