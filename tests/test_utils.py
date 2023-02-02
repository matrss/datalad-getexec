from datalad_getexec import utils
import hypothesis as h


@h.given(...)
def test_removeprefix_removes_prefix(stem: str, prefix: str) -> None:
    assert utils.removeprefix(prefix + stem, prefix) == stem


@h.given(...)
def test_removeprefix_noop_if_no_prefix(stem: str, prefix: str) -> None:
    h.assume(not stem.startswith(prefix))
    assert utils.removeprefix(stem, prefix) == stem


@h.given(...)
def test_removesuffix_removes_suffix(stem: str, suffix: str) -> None:
    assert utils.removesuffix(stem + suffix, suffix) == stem


@h.given(...)
def test_removesuffix_noop_if_no_suffix(stem: str, suffix: str) -> None:
    h.assume(not stem.endswith(suffix))
    assert utils.removesuffix(stem, suffix) == stem
