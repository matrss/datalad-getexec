import base64
import inspect
import json
import logging
import subprocess
import urllib.parse

from annexremote import Master, RemoteError, SpecialRemote

logger = logging.getLogger("datalad.getexec.remote")

GETEXEC_REMOTE_UUID = "1da43985-0b3e-4123-89f0-90b88021ed34"


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

    def transfer_retrieve(self, key: str, filename: str) -> None:
        logger.debug(
            "%s called with key %s and filename %s",
            inspect.stack()[0][3],
            key,
            filename,
        )

        def _execute_cmd(cmd):
            logger.debug("executing %s", cmd)
            self.annex.info("executing {}".format(cmd))
            result = subprocess.run(cmd, stdout=subprocess.PIPE)
            logger.info(result.stdout)
            if result.returncode != 0:
                raise RemoteError("Failed to execute {}".format(cmd))

        urls = self.annex.geturls(key, "getexec:")
        logger.debug("urls for this key: %s", urls)
        # always use the first url if multiple are defined
        url = urls[0].removeprefix("getexec:")
        if url.startswith("v1-"):
            spec = json.loads(
                base64.urlsafe_b64decode(
                    urllib.parse.unquote(url.removeprefix("v1-")).encode("utf-8")
                )
            )

            inputs = spec["inputs"]
            if inputs:
                import datalad.api as da
                from datalad.utils import swallow_outputs

                with swallow_outputs() as cm:
                    logger.info("fetching inputs: %s", inputs)
                    # NOTE: this might be more efficient if we collect transitive
                    # dependencies and aggregate them in one get call
                    da.get(inputs)
                    logger.info("datalad get output: %s", cm.out)

            cmd = spec["cmd"]
            cmd.append(filename)
            _execute_cmd(cmd)
        else:
            raise RemoteError("Failed to handle key {}".format(key))

    def checkpresent(self, key: str) -> bool:
        # We just assume that we can always handle the key
        return True

    def claimurl(self, url: str) -> bool:
        return url.startswith("getexec:")

    def checkurl(self, url: str) -> bool:
        return url.startswith("getexec:")


def main():
    master = Master()
    remote = GetExecRemote(master)
    master.LinkRemote(remote)
    logger.addHandler(master.LoggingHandler())
    master.Listen()
