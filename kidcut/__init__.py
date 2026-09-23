from pathlib import Path


_SRC_PACKAGE = Path(__file__).resolve().parent.parent / "src" / "kidcut"
if str(_SRC_PACKAGE) not in __path__:
    __path__.append(str(_SRC_PACKAGE))
