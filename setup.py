#!/usr/bin/env python

import sys

sys.path.insert(0, "")

from setuptools import setup  # noqa: E402

import versioneer  # noqa: E402
from _datalad_buildsupport.setup import BuildManPage  # noqa: E402

cmdclass = versioneer.get_cmdclass()
cmdclass.update(build_manpage=BuildManPage)

if __name__ == "__main__":
    setup(
        name="datalad-getexec",
        version=versioneer.get_version(),
        cmdclass=cmdclass,
    )
