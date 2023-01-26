import base64
import json
import sys
import urllib.parse


def removeprefix(s: str, prefix: str) -> str:
    if sys.version_info >= (3, 9):
        return s.removeprefix(prefix)
    if s.startswith(prefix):
        return s[len(prefix) :]
    return s


def removesuffix(s: str, suffix: str) -> str:
    if sys.version_info >= (3, 9):
        return s.removesuffix(suffix)
    if s.endswith(suffix):
        return s[: -len(suffix)]
    return s


def spec_to_url(spec):
    json_spec = json.dumps(spec, separators=(",", ":"))
    url = "getexec:v1-" + urllib.parse.quote(
        base64.urlsafe_b64encode(json_spec.encode("utf-8"))
    )
    return url


def url_to_spec(url):
    if url.startswith("v1-"):
        spec = json.loads(
            base64.urlsafe_b64decode(
                urllib.parse.unquote(removeprefix(url, "v1-")).encode("utf-8")
            )
        )
        return spec
    raise ValueError("unsupported URL value encountered")
