import climax as clx
import subprocess as subp
from pathlib import Path
import os
import os.path as osp
from logging import getLogger

LOGGER = getLogger(__name__)


ROOT_ENV_VAR = "MARCABANCA_ROOT"


@clx.group()
def main():
    pass


@clx.parent()
@clx.argument(
    "root",
    type=Path,
    nargs="?",
    help=f"Marcabanca data root folder (usually '<test folder>/.marcabana'.). If not specified, will attempt to read env var {ROOT_ENV_VAR}.",
)
def root_arg(root):
    pass


def compute_root(root):
    if root:
        out = root
    elif root := os.getenv(ROOT_ENV_VAR):
        out = root
    else:
        LOGGER.error(
            f"Marcabanca root folder root not specified. Pass it in as an argument or set it using env var {ROOT_ENV_VAR}."
        )
        exit(1)

    if not osp.isdir(out):
        LOGGER.error(
            f"The specified root directory \n\t'{out}' \nis not a valid directory."
        )
        exit(1)

    return out
