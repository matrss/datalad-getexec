"""DataLad getexec command"""

__docformat__ = "restructuredtext"

import json
import logging
from typing import List, Literal, Optional

import utils
from datalad.distribution.dataset import (
    Dataset,
    EnsureDataset,
    datasetmethod,
    require_dataset,
)
from datalad.interface.base import Interface, build_doc, eval_results
from datalad.interface.results import get_status_dict
from datalad.support.annexrepo import AnnexRepo
from datalad.support.constraints import EnsureNone, EnsureStr
from datalad.support.param import Parameter

import datalad_getexec.remote

logger = logging.getLogger("datalad.getexec.getexec")


@build_doc
class GetExec(Interface):
    """Short description of the command

    Long description of arbitrary volume.
    """

    _params_ = dict(
        cmd=Parameter(
            args=("cmd",),
            nargs="+",
            metavar="COMMAND",
            doc="""the command to execute and register. The first argument is
            the program to execute, the following arguments are passed to this
            program. It is expected that the program takes a target filename
            as its last argument, which is appended to the full command in the
            special remote.""",
            constraints=EnsureStr(),
        ),
        path=Parameter(
            args=("-O", "--path"),
            doc="""target for the program execution. If the path is directory,
            then a string representation of the command will be used as the
            target filename. Otherwise this parameter is assumed to be the target
            filename. The target is always assumed to be relative to the dataset.""",
            constraints=EnsureStr(),
        ),
        inputs=Parameter(
            args=("-i", "--input"),
            dest="inputs",
            metavar="PATH",
            action="append",
            doc="""a dependency for the getexec command. These dependencies will be
            fetched by a :command:`datalad get` before executing the getexec command.
            The dependencies will be registered in git-annex in a way that they will be
            fetched on subsequent :command:`get`s on the file created by getexec.""",
        ),
        dataset=Parameter(
            args=("-d", "--dataset"),
            metavar="PATH",
            doc="""specify the dataset to execute and register the command in.
            If no dataset is given, an attempt is made to identify the dataset
            based on the current working directory. The newly created file will
            be saved in the dataset.""",
            constraints=EnsureDataset() | EnsureNone(),
        ),
        message=Parameter(
            args=("-m", "--message"),
            doc="""commit message to use. If no commit message is given the specified
            command will be used in a readable format.""",
            constraints=EnsureStr() | EnsureNone(),
        ),
    )

    @staticmethod
    @datasetmethod(name="getexec")
    @eval_results
    def __call__(
        cmd: str,
        path: str,
        dataset: Optional[Dataset] = None,
        inputs: Optional[List[str]] = None,
        message: Optional[str] = None,
    ):
        ds = require_dataset(
            dataset, check_installed=True, purpose="execute and register a command"
        )
        if inputs is None:
            inputs = []
        spec = {
            "inputs": inputs,
            "cmd": cmd,
        }
        logger.debug("spec is %s", spec)
        url = utils.spec_to_url(spec)
        logger.debug("url is %s", url)

        pathobj = ds.pathobj / path
        logger.debug("target path is %s", pathobj)

        ensure_special_remote_exists_and_is_enabled(ds.repo, "getexec")
        ds.repo.add_url_to_file(pathobj, url)
        msg = """\
[DATALAD GETEXEC] {}

=== Do not change lines below ===
{}
^^^ Do not change lines above ^^^
        """
        cmd_message_full = "'" + "' '".join(spec["cmd"]) + "'"
        cmd_message = (
            cmd_message_full
            if len(cmd_message_full) <= 40
            else cmd_message_full[:40] + " ..."
        )
        record = json.dumps(spec, indent=1, sort_keys=True)
        msg = msg.format(
            message if message is not None else cmd_message,
            record,
        )
        yield ds.save(pathobj, message=msg)
        yield get_status_dict(action="getexec", status="ok")


def ensure_special_remote_exists_and_is_enabled(
    repo: AnnexRepo, remote: Literal["getexec"]
) -> None:
    """Initialize and enable the getexec special remote, if it isn't already.

    Very similar to datalad.customremotes.base.ensure_datalad_remote.
    """
    uuids = {"getexec": datalad_getexec.remote.GETEXEC_REMOTE_UUID}
    uuid = uuids[remote]
    name = repo.get_special_remotes().get(uuid, {}).get("name")
    if not name:
        repo.init_remote(
            remote,
            [
                "encryption=none",
                "type=external",
                "autoenable=true",
                "externaltype={}".format(remote),
                "uuid={}".format(uuid),
            ],
        )
    elif repo.is_special_annex_remote(name, check_if_known=False):
        logger.debug("special remote %s is enabled", name)
    else:
        logger.debug("special remote %s found, enabling", name)
        repo.enable_remote(name)
