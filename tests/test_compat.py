import hypothesis as h

from datalad_getexec import compat


@h.given(...)
def test_removeprefix_removes_prefix(stem: str, prefix: str) -> None:
    assert compat.removeprefix(prefix + stem, prefix) == stem


@h.given(...)
def test_removeprefix_noop_if_no_prefix(stem: str, prefix: str) -> None:
    h.assume(not stem.startswith(prefix))
    assert compat.removeprefix(stem, prefix) == stem


@h.given(...)
def test_removesuffix_removes_suffix(stem: str, suffix: str) -> None:
    assert compat.removesuffix(stem + suffix, suffix) == stem


@h.given(...)
def test_removesuffix_noop_if_no_suffix(stem: str, suffix: str) -> None:
    h.assume(not stem.endswith(suffix))
    assert compat.removesuffix(stem, suffix) == stem
