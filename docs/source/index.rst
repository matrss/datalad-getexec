DataLad extension for code execution in get commands
****************************************************

This extension adds a new command called "getexec" which can be used to
register a command which should be executed on "get". This way it is possible
to programmatically create files when "get"ing them, transparently.

This functionality is achieved by using a git-annex special remote which
executes the registered command when retrieving data from it. The command
itself and it's dependencies are encoded in an URL with a custom scheme, which
is then associated with the generated file.


API
===

High-level API commands
-----------------------

.. currentmodule:: datalad.api
.. autosummary::
   :toctree: generated

   getexec


Command line reference
----------------------

.. toctree::
   :maxdepth: 1

   generated/man/datalad-getexec


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

.. |---| unicode:: U+02014 .. em dash
