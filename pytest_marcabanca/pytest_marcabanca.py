# -*- coding: utf-8 -*-
# from marcabanca import MarcabancaWrappedCallable
from jztools import humanize as pghm
import os
import os.path as osp
import numpy as np
from collections import namedtuple
from .utils import Manager
import py
import jztools.profiling as pgprof
from py.path import local
import pytest
from jztools.unittest.utils import is_skipped


class TestIsSlow(Exception):
    def __init__(self, rank, rltv):
        super().__init__(f"Avg. rank={rank}; Avg. rltv. runtime={rltv}")


def pytest_configure(config):
    """
    pytest_configure hook for marcabanca plugin
    """

    config.pluginmanager.register(PytestMarcabanca(config))


def pytest_addoption(parser):
    """
    Defines pytest options for marcabanca plugin.
    """
    group = parser.getgroup("marcabanca")
    group.addoption(
        "--mb",
        default="none",
        choices=["all", "none", "decorated"],
        help="['none'] Benchmark 'all' tests, only those 'decorated' with a @benchmark decorator, or 'none'. Tests decorated with @skip_benchmark are always ignored. If --mb-create-references='none' (the default), tests with no existing reference will be skipped.",
    )
    group.addoption(
        "--mb-num-test-runs",
        type=int,
        default=2,
        help="[2] Number of runs to carry out at test time to estimate average runtime.",
    )
    group.addoption(
        "--mb-rank-thresh",
        type=float,
        default=0.99,
        help="[0.99] Min threshold applied to average runtime rank (as a float in [0,1]  range or 'inf').",
    )
    group.addoption(
        "--mb-rltv-thresh",
        type=float,
        default=1.5,
        help="[1.5] Error threshold applied to average relative runtime (e.g., use 1.3 to fail with tests 30% slower on avg. than the ref).",
    )
    group.addoption(
        "--mb-create-references",
        default="none",
        choices=["none", "overwrite", "missing"],
        help="['none'] Creates references for the tests run (those satisfying the --mb option). Use 'missing' to create only missing references, 'overwrite' to further overwrite existing references, or 'none' to create no new references (the default).",
    )
    group.addoption(
        "--mb-num-ref-runs",
        type=int,
        default=10,
        help="[10] Number of runs to carry out for each test when creating a reference model.",
    )
    group.addoption(
        "--mb-root",
        default=None,
        type=local,
        help="[tests root] Directory where marcabanca reference models are stored (<tests root>/marcabanca/ by default).",
    )
    group.addoption(
        "--mb-model-name", default="gamma", help="One of the models in scipy.stats."
    )


Result = namedtuple(
    "Result",
    (
        "test_node_id",
        "exact",
        "rank",
        "runtime",
        "rltv_runtime",
        "model_mean",
        "empirical_mean",
        "ref_model",
    ),
)


class PytestMarcabanca(object):
    def __init__(self, config):
        self.which_tests = config.getvalue("mb")
        self.root = config.getvalue("mb_root")
        self.create_references = config.getvalue("mb_create_references")
        self.num_ref_runs = config.getvalue("mb_num_ref_runs")
        self.num_test_runs = config.getvalue("mb_num_test_runs")
        self.model_name = config.getvalue("mb_model_name")
        self.data_manager = None
        self.rank_thresh = config.getvalue("mb_rank_thresh")
        self.rltv_thresh = config.getvalue("mb_rltv_thresh")
        self.results = []
        self.missing_references = []

    @classmethod
    def _default_root(cls, session):
        return session.config.rootdir.join(".marcabanca/")

    # Hooks
    def pytest_sessionstart(self, session):

        # Create root directory if necessary.
        self.root = self.root or self._default_root(session)
        try:
            self.root.mkdir()
        except py.error.EEXIST:
            pass

        # Initialize data manager.
        self.data_manager = Manager(self.root)

    def pytest_sessionfinish(self, session, exitstatus):
        #
        if (
            self.create_references in ["overwrite", "missing"]
            and self.data_manager.created_new_reference
        ):
            self.data_manager.write()
        #
        if self.which_tests != "none":
            self.print_results(session.config.rootdir)

    def print_results(self, rootdir):
        from rich.console import Console
        from rich.table import Table
        from rich.text import Text

        # Specify table structure
        class ColumnSpec(
            namedtuple(
                "ColumnSpec",
                ["header", "justify", "get_value", "apply_format", "summary"],
            )
        ):
            def get_formatted(self, _result):
                return self.apply_format(self.get_value(_result))

        rel_cwd = osp.relpath(rootdir, os.getcwd())
        columns = [
            ColumnSpec(
                "Test",
                "left",
                lambda _result: _result.test_node_id,
                lambda _value: osp.join(rel_cwd, _value),
                np.mean,
            ),
            ColumnSpec(
                "Rank",
                "right",
                lambda _result: _result.rank,
                lambda _value: f"{_value:.2%}",
                np.mean,
            ),
            ColumnSpec(
                "Rltv",
                "right",
                lambda _result: _result.rltv_runtime,
                lambda _value: f"{_value:1.1f}X",
                np.mean,
            ),
            ColumnSpec(
                "Abs",
                "right",
                lambda _result: _result.runtime,
                lambda _value: pghm.secs(_value, align=True),
                np.mean,
            ),
            ColumnSpec(
                "Machine",
                "right",
                lambda _result: _result.ref_model.reference_id["machine_config_id"],
                clip_id := (lambda _value: _value[:7]),
                lambda _x: "",
            ),
            ColumnSpec(
                "Python",
                "right",
                lambda _result: _result.ref_model.reference_id["python_config_id"],
                clip_id,
                lambda _x: "",
            ),
        ]

        def row_style(_result):
            return (
                "red"
                if _result.rank > self.rank_thresh
                or _result.rltv_runtime > self.rltv_thresh
                else "green"
            )

        # Create table structure
        table = Table(title="Marcabanca benchmarking results")
        for _col in columns:
            table.add_column(_col.header, justify=_col.justify)

        # Add table content
        results = sorted(self.results, key=lambda r: r.rank, reverse=True)
        for _result in results:
            table.add_row(
                *[_col.get_formatted(_result) for _col in columns],
                style=row_style(_result),
            )

        # Add averages row
        table.add_row(
            "(Averages)",
            *[
                _col.apply_format(
                    _col.summary([_col.get_value(_result) for _result in results])
                )
                for _col in columns[1:]
            ],
        )

        # Print table
        console = Console()
        console.print("\n")
        if results:
            console.print(table)

        # Print warnings
        if self.missing_references:
            console.print(
                f"MARCABANCA: {len(self.missing_references)} marcabanca benchmark references were missing. You can create them using option '--mb-create-references=missing'.",
                style="red",
            )
        elif not results:
            console.print(
                "MARCABANCA: Found no marcabanca benchmarking tests matching the request.",
                style="red",
            )

        inexact = sum(not _x.exact for _x in results)
        if inexact:
            console.print(
                f"MARCABANCA: {inexact}/{len(results)} tests ran with a mis-matched reference.",
                style="red",
            )

    def pytest_runtest_call(self, item):
        """
        .. todo:: Ensure that the reference generation is skipped when using either unittest and pytest skip decorators.
        """
        if is_skipped(item):
            return
        orig_runtest = item.runtest
        item.runtest = lambda: self._item_runtest_wrapper(item, orig_runtest)

    def _item_runtest_wrapper(self, item, item_runtest):

        # The first run loads all modules, avoiding overhead when measuring run times.
        # TODO: Convert this into an option.
        item_runtest()

        is_decorated = hasattr(item.function, "_marcabanca")
        do_benchmark = is_decorated and item.function._marcabanca["benchmark"]
        if (self.which_tests == "all" and (not is_decorated or do_benchmark)) or (
            self.which_tests == "decorated" and do_benchmark
        ):

            # Use the whole nodeid so you can copy/paste it to run the test
            test_node_id = item.nodeid

            # Create reference
            if self.create_references == "overwrite" or (
                self.create_references == "missing"
                and not self.data_manager.check_reference_exists(test_node_id)
            ):

                # Assemble ref_runtimes test
                ref_runtimes = []
                for k in range(self.num_ref_runs):
                    with pgprof.Time() as timer:
                        item_runtest()
                    ref_runtimes.append(timer.elapsed)

                # Create reference model
                self.data_manager.create_reference(
                    test_node_id, ref_runtimes, self.model_name
                )

            elif self.data_manager.get_reference_model(test_node_id) == (None, None):
                # A reference did not exist and was not created.
                self.missing_references.append(test_node_id)
                return

            # Capture test run times
            test_runtimes = []
            for k in range(self.num_test_runs):
                with pgprof.Time() as test_timer:
                    item_runtest()
                test_runtimes.append(test_timer.elapsed)
            mean_test_time = np.mean(test_runtimes)

            # Compute results
            exact, ref_model = self.data_manager.get_reference_model(test_node_id)

            if ref_model is not None:
                rank = np.mean(
                    [ref_model.rank_runtime(_runtime) for _runtime in test_runtimes]
                )
                self.results.append(
                    Result(
                        test_node_id=test_node_id,
                        rank=rank,
                        exact=exact,
                        runtime=mean_test_time,
                        rltv_runtime=(mean_test_time / ref_model.model.stats("m")),
                        model_mean=ref_model.model.stats("m"),
                        empirical_mean=np.mean(ref_model.runtimes),
                        ref_model=ref_model,
                    )
                )
