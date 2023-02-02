from __future__ import annotations

import base64
import json
import urllib.parse
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

from datalad_getexec import compat


@dataclass
class Spec:
    cmd: List[str]
    inputs: Optional[List[str]]

    @classmethod
    def from_dict(cls, dict: Dict[str, Any]) -> Spec:
        return cls(**dict)

    @classmethod
    def from_json(cls, s: str) -> Spec:
        return cls.from_dict(json.loads(s))

    @classmethod
    def from_url(cls, url: str) -> Spec:
        if url.startswith("getexec:v1-"):
            spec = cls.from_json(
                base64.urlsafe_b64decode(
                    urllib.parse.unquote(
                        compat.removeprefix(url, "getexec:v1-")
                    ).encode("utf-8")
                ).decode("utf-8")
            )
            return spec
        raise ValueError("unsupported URL value encountered")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), separators=(",", ":"))

    def to_url(self) -> str:
        json_spec = self.to_json()
        url = "getexec:v1-" + urllib.parse.quote(
            base64.urlsafe_b64encode(json_spec.encode("utf-8"))
        )
        return url
