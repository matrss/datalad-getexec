import hypothesis as h

from datalad_getexec.spec import Spec


@h.given(...)
def test_spec_dict_equality(spec: Spec) -> None:
    assert Spec.from_url(spec.to_url()) == spec
