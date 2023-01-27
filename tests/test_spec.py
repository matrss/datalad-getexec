import hypothesis as h
import pytest

from datalad_getexec.spec import Spec


@h.given(...)
def test_spec_dict_equality(spec: Spec) -> None:
    assert Spec.from_url(spec.to_url()) == spec


@h.given(...)
def test_spec_invalid_url_causes_value_error(url: str) -> None:
    h.assume(not url.startswith("getexec:v1-"))
    with pytest.raises(ValueError):
        Spec.from_url(url)
