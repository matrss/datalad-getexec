"""DataLad getexec command"""

__docformat__ = "restructuredtext"

from datalad.interface.base import Interface
from datalad.interface.base import build_doc
from datalad.distribution.dataset import datasetmethod
from datalad.interface.base import eval_results

from datalad.interface.results import get_status_dict

import logging

lgr = logging.getLogger("datalad.getexec.getexec")


@build_doc
class GetExec(Interface):
    """Short description of the command

    Long description of arbitrary volume.
    """

    _params_ = dict()

    @staticmethod
    @datasetmethod(name="getexec")
    @eval_results
    def __call__():
        raise NotImplementedError()

        yield get_status_dict(action="getexec", status="ok")
