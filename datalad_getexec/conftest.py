import os

import hypothesis as h
from datalad.conftest import setup_package

h.settings.register_profile("fast", max_examples=10)
h.settings.register_profile("ci", max_examples=1000)
h.settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "fast"))
