from .main import main, root_arg, compute_root
from collections import namedtuple
from pglib import validation as pgval
import climax as clx
from pytest_marcabanca.utils import Manager, find
from rich.table import Table
from rich.console import Console
from rich.text import Text
from pglib.json import as_json_serializable
from logging import getLogger

CONSOLE = Console()

LOGGER = getLogger(__name__)


@main.group()
def info():
    """
    Data store management utilities.
    """
    pass


@clx.parent()
@clx.argument(
    "--diff",
    nargs="?",
    dest="do_diff",
    default=False,
    help="Display difference relative to the specified machine (or the current machine if not specified).",
)
def diff_arg():
    pass


@info.command(
    parents=[root_arg, diff_arg],
    help="Print a list of available machine configurations.",
)
def machines(root, do_diff):
    root = compute_root(root)
    mngr = Manager(root, add_this_env=False)
    print_summary(
        "machine config",
        mngr.this_machine_config,
        mngr.data["machine_configs"],
        do_diff,
    )


@info.command(
    parents=[root_arg, diff_arg],
    help="Print a list of available python configurations.",
)
def python(root, do_diff):
    root = compute_root(root)
    mngr = Manager(root, add_this_env=False)
    print_summary(
        "python config", mngr.this_python_config, mngr.data["python_configs"], do_diff
    )


def print_summary(config_type, this_config, configs_list, do_diff):

    # Get the matching config.
    matching_config = [_x for _x in configs_list if _x == this_config]
    if matching_config:
        matching_config = pgval.checked_get_single(matching_config)
    else:
        CONSOLE.print(
            f"Did not find a matching {config_type} for this environment!", style="red"
        )

    # Get diff reference config
    if do_diff is None:
        ref_config = this_config
    elif do_diff is not False:
        posn = [
            _k
            for _k, _ref in enumerate(configs_list)
            if _ref.config_id[: len(do_diff)] == do_diff
        ]
        if len(posn) > 1:
            LOGGER.error(
                f"Found more than one matching reference {config_type} for hash '{do_diff}': "
                f"{[configs_list[_k].config_id for _k in posn]}"
            )
            exit(-1)
        elif len(posn) == 0:
            LOGGER.error(
                f"Found no matching reference {config_type}s for hash '{do_diff}'."
            )
            exit(-1)
        ref_config = configs_list[posn[0]]

    #
    formatted_configs = [
        {
            "this": ("*" if _config == this_config else ""),
            "uuid": _config.config_id,
            "specs": ref_config.diff(_config)
            if (do_diff is not False)
            else _config.for_display(),
        }
        for _config in configs_list
    ]

    class ColumnSpec(namedtuple("ColumnSpec", ["key", "header", "kwargs"])):
        def get(self, _val):
            return getattr(_val, self.key)

    columns = [
        ColumnSpec("this", "", {"justify": "center"}),
        ColumnSpec("uuid", "UUID", {"justify": "center", "max_width": 8}),
        ColumnSpec("specs", "Specs", {"justify": "left"}),
    ]

    # Create table structure
    table = Table(title="Available {config_type}s")
    for _col in columns:
        table.add_column(_col.header, **_col.kwargs)

    # Add table content
    for _config in formatted_configs:
        table.add_row(*[_config[_col.key] for _col in columns])

    CONSOLE.print(table)
