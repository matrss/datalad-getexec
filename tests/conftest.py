import os

import hypothesis as h
from datalad.conftest import setup_package  # noqa: F401

h.settings.register_profile("fast", max_examples=50)
h.settings.register_profile("ci", max_examples=500)
h.settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "fast"))
