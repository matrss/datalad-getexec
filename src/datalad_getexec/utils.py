import sys


def removeprefix(s: str, prefix: str) -> str:
    if sys.version_info >= (3, 9):  # pragma: py-gte-39
        return s.removeprefix(prefix)
    else:  # pragma: py-lt-39
        if s.startswith(prefix):
            return s[len(prefix) :]
        return s


def removesuffix(s: str, suffix: str) -> str:
    if sys.version_info >= (3, 9):  # pragma: py-gte-39
        return s.removesuffix(suffix)
    else:  # pragma: py-lt-39
        if s.endswith(suffix):
            return s[: -len(suffix)]
        return s
