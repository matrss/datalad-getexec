def test_register() -> None:
    import datalad.api as da

    assert hasattr(da, "getexec")
