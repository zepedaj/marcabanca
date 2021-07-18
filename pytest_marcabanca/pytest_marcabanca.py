# -*- coding: utf-8 -*-
from pglib import humanize as pghm
import os
import os.path as osp
import numpy as np
from collections import namedtuple
from .utils import Manager
import py
import pglib.profiling as pgprof
from py.path import local
import pytest


class TestIsSlow(Exception):
    def __init__(self, rank, rltv):
        super().__init__(f'Avg. rank={rank}; Avg. rltv. runtime={rltv}')


def pytest_configure(config):
    """
    pytest_configure hook for marcabanca plugin
    """

    config.pluginmanager.register(PytestMarcabanca(config))


def pytest_addoption(parser):
    """
    Defines pytest options for marcabanca plugin.
    """
    group = parser.getgroup('marcabanca')
    group.addoption(
        '--mb', default='none', choices=['all', 'none', 'decorated'],
        help="['none'] Benchmark 'all' tests, only those 'decorated' with a @benchmark decorator, or 'none'. Tests decorated with @skip_benchmark are always ignored. If --mb-create-references='none' (the default), tests with no existing reference will be skipped.",)
    group.addoption(
        '--mb-num-test-runs', type=int, default=10,
        help="[10] Number of runs to carry out at test time to estimate average runtime.")
    group.addoption(
        '--mb-rank-thresh', type=float, default=float('inf'),
        help="[inf] Min threshold applied to average runtime rank (as a float in [0,1]  range or 'inf').")
    group.addoption(
        '--mb-rltv-thresh', type=float, default=1.5,
        help="[1.5] Error threshold applied to average relative runtime (e.g., use 1.3 to fail with tests 30% slower on avg. than the ref).")
    group.addoption(
        '--mb-create-references', default='none', choices=['none', 'overwrite', 'missing'],
        help="['none'] Creates references for the tests run (those satisfying the --mb option). Use 'missing' to create only missing references, 'overwrite' to further overwrite existing references, or 'none' to create no new references (the default).")
    group.addoption(
        '--mb-num-ref-runs', type=int, default=30,
        help="[30] Number of runs to carry out for each test when creating a reference model.")
    group.addoption(
        '--mb-root', default=None, type=local,
        help='[tests root] Directory where marcabanca reference models are stored (<tests root>/marcabanca/ by default).')
    group.addoption(
        '--mb-model-name', default='gamma',
        help="One of the models in scipy.stats.")


Result = namedtuple('Result', ('test_node_id', 'exact', 'rank',
                               'runtime', 'model_mean', 'empirical_mean'))


class PytestMarcabanca(object):

    def __init__(self, config):
        self.which_tests = config.getvalue('mb')
        self.root = config.getvalue('mb_root')
        self.create_references = config.getvalue('mb_create_references')
        self.num_ref_runs = config.getvalue('mb_num_ref_runs')
        self.num_test_runs = config.getvalue('mb_num_test_runs')
        self.model_name = config.getvalue('mb_model_name')
        self.data_manager = None
        self.rank_thresh = config.getvalue('mb_rank_thresh')
        self.rltv_thresh = config.getvalue('mb_rltv_thresh')
        self.results = []

    @classmethod
    def _default_root(cls, session):
        return session.config.rootdir.join('marcabanca/')

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
        if (self.create_references in ['overwrite', 'missing'] and
                self.data_manager.created_new_reference):
            self.data_manager.write()
        #
        if self.which_tests != 'none':
            self.print_results(session.config.rootdir)

    def print_results(self, rootdir):
        from rich.console import Console
        from rich.table import Table
        table = Table(title='Marcabanca benchmarking results')
        table.add_column('Test', justify='left')
        table.add_column('Rank', justify='right')
        table.add_column('Rltv', justify='right')
        table.add_column('Time', justify='right')
        # table.add_column('Model Mean', justify='right')
        # table.add_column('Emprc Mean', justify='right')
        results = sorted(self.results, key=lambda r: r.rank, reverse=True)

        rel_cwd = osp.relpath(rootdir, os.getcwd())
        for _result in results:
            table.add_row(
                osp.join(rel_cwd, _result.test_node_id),
                f'{_result.rank:.2%}',
                f'{_result.runtime / _result.model_mean:1.1f}X',
                pghm.secs(_result.runtime),
                # f'{_result.model_mean:.3g}',
                # f'{_result.empirical_mean:.3g}',
                style=('red' if
                       (_result.rank > self.rank_thresh or _result.runtime > self.rltv_thresh)
                       else 'green'))
        console = Console()
        console.print('\n', table)
        if len(results) == 0:
            console.print(
                "(No benchmark references found. You can create them using option '--mb-create-references=missing'.)")

    @pytest.hookimpl()
    def pytest_runtest_call(self, item):

        # The first run loads all modules, avoiding overhead when measuring run times.
        item.runtest()

        if self.which_tests != 'none':

            # Use the whole nodeid so you can copy/paste it to run the test
            test_node_id = item.nodeid

            # Test runs
            test_runtimes = []
            for k in range(self.num_test_runs):
                with pgprof.Time() as test_timer:
                    item.runtest()
                test_runtimes.append(test_timer.elapsed)
            mean_test_time = np.mean(test_runtimes)

            # Compute runtime rank
            if self.which_tests == 'all' or (
                    self.which_tests == 'decorated' and hasattr(item.function, 'marcabanca')):

                # Create reference
                if (self.create_references == 'overwrite' or
                    (self.create_references == 'missing' and
                     not self.data_manager.check_reference_exists(test_node_id))):

                    # Assemble ref_runtimes test
                    ref_runtimes = []
                    for k in range(self.num_ref_runs):
                        with pgprof.Time() as timer:
                            item.runtest()
                        ref_runtimes.append(timer.elapsed)

                    # Create reference model
                    self.data_manager.create_reference(test_node_id, ref_runtimes, self.model_name)

                # Compute runtime rank
                exact, ref_model = self.data_manager.get_reference_model(test_node_id)
                rank = np.mean([ref_model.rank_runtime(_runtime) for _runtime in test_runtimes])
                # rank = sum((1 for _runtime in test_runtimes for _x in ref_model.runtimes
                #             if _x <= _runtime)) / (len(ref_model.runtimes) * (len(test_runtimes)))

                if rank is not None:
                    self.results.append(Result(
                        test_node_id=test_node_id,
                        rank=rank,
                        exact=exact,
                        runtime=mean_test_time,
                        model_mean=ref_model.model.stats('m'),
                        empirical_mean=np.mean(ref_model.runtimes)))
