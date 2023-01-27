import sys


def removeprefix(s: str, prefix: str) -> str:
    if sys.version_info >= (3, 9):
        return s.removeprefix(prefix)
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def removesuffix(s: str, suffix: str) -> str:
    if sys.version_info >= (3, 9):
        return s.removesuffix(suffix)
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s
