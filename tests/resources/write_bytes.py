#!/usr/bin/env python3

import sys
from pathlib import Path


def main(args):
    content = eval(args[1])
    target_path = Path(args[2])
    with open(target_path, mode="wb") as f:
        f.write(content)


if __name__ == "__main__":
    main(sys.argv)
