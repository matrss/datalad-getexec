import inspect
import logging
import subprocess
from typing import List

from annexremote import Master, RemoteError, SpecialRemote

from datalad_getexec.spec import Spec

logger = logging.getLogger("datalad.getexec.remote")

GETEXEC_REMOTE_UUID = "1da43985-0b3e-4123-89f0-90b88021ed34"


class HandleUrlError(Exception):
    pass


class GetExecRemote(SpecialRemote):
    # explicitly disable unsupported operations
    transfer_store = None
    remove = None

    def initremote(self) -> None:
        # setting the uuid here unfortunately does not work, initremote is
        # executed to late
        # self.annex.setconfig("uuid", GETEXEC_REMOTE_UUID)
        pass

    def prepare(self) -> None:
        pass

    def _execute_cmd(self, cmd: List[str]) -> None:
        logger.debug("executing %s", cmd)
        self.annex.info("executing {}".format(cmd))
        result = subprocess.run(cmd, stdout=subprocess.PIPE)
        logger.info(result.stdout)
        if result.returncode != 0:
            raise RemoteError("Failed to execute {}".format(cmd))

    def _handle_url(self, url: str, filename: str) -> None:
        import datalad.api as da
        from datalad.utils import swallow_outputs

        spec = Spec.from_url(url)
        inputs = spec.inputs
        if inputs:
            with swallow_outputs() as cm:
                logger.info("fetching inputs: %s", inputs)
                da.get(set(inputs))
                logger.info("datalad get output: %s", cm.out)
        cmd = spec.cmd
        cmd.append(filename)
        self._execute_cmd(cmd)

    def transfer_retrieve(self, key: str, filename: str) -> None:
        logger.debug(
            "%s called with key %s and filename %s",
            inspect.stack()[0][3],
            key,
            filename,
        )
        urls = self.annex.geturls(key, "getexec:")
        logger.debug("urls for this key: %s", urls)
        for url in urls:
            try:
                self._handle_url(url, filename)
                break
            except HandleUrlError:
                pass
        else:
            raise RemoteError("Failed to handle key {}".format(key))

    def checkpresent(self, key: str) -> bool:
        # We just assume that we can always handle the key
        return True

    def claimurl(self, url: str) -> bool:
        return url.startswith("getexec:")

    def checkurl(self, url: str) -> bool:
        return url.startswith("getexec:")


def main() -> None:
    master = Master()
    remote = GetExecRemote(master)
    master.LinkRemote(remote)
    logger.addHandler(master.LoggingHandler())
    master.Listen()
