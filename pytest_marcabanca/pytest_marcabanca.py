# -*- coding: utf-8 -*-
from collections import namedtuple
from .utils import Manager
import py
import pglib.profiling as pgprof
from py.path import local
import pytest


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
        '--mb-root', default=None, type=local,
        help='Directory where marcabanca reference models are stored (<tests root>/marcabanca/ by default).'),
    group.addoption(
        '--mb-which-tests', default='all', choices=['all', 'none', 'decorated'],
        help="[Default 'all'] Benchmark 'all' tests, only those 'decorated' with a @benchmark decorator, or 'none'. Tests decorated with @skip_benchmark are always ignored. If --mb-create-references='none', tests with no existing reference will be skipped.",)
    group.addoption(
        '--mb-create-references', default='none', choices=['none', 'overwrite', 'missing'],
        help="[Default 'none'] Creates references for the tests run (and satisfying the --mb-tests option). Use 'missing' to create only missing references, 'overwrite' to further overwrite existing references, or 'none' to create no new references.")
    group.addoption(
        '--mb-num-runs', type=int, default=10,
        help="Number of runs to carry out for each test to create a reference model.")
    group.addoption(
        '--mb-model-name', default='gamma',
        help="One of the models in scipy.stats.")


Result = namedtuple('Result', ('test_node_id', 'rank'))


class PytestMarcabanca(object):

    def __init__(self, config):
        self.root = config.getvalue('mb_root')
        self.which_tests = config.getvalue('mb_which_tests')
        self.create_references = config.getvalue('mb_create_references')
        self.num_runs = config.getvalue('mb_num_runs')
        self.model_name = config.getvalue('mb_model_name')
        self.data_manager = None
        self.results = []

    # JSON file paths.
    @property
    def references_path(self):
        return self.root.join('references.json')

    @property
    def machine_configs_path(self):
        return self.root.join('machine_configs.json')

    @property
    def python_configs_path(self):
        return self.root.join('python_configs.json')

    @property
    def filelock_path(self):
        return self.machine_configs_path

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
        self.data_manager = Manager(
            machine_configs_path=self.machine_configs_path,
            python_configs_path=self.python_configs_path,
            references_path=self.references_path)

    def pytest_sessionfinish(self, session, exitstatus):
        if (self.create_references in ['overwrite', 'missing'] and
                self.data_manager.created_new_reference):
            self.data_manager.write()

    @pytest.hookimpl()
    def pytest_runtest_call(self, item):

        # Run test
        with pgprof.Time() as test_timer:
            item.runtest()

        # Compute runtime rank
        if self.which_tests == 'all' or (
                self.which_tests == 'decorated' and hasattr(item.function, 'marcabanca')):

            # Create reference
            if (self.create_references == 'overwrite' or
                (self.create_references == 'missing' and
                 not self.data_manager.check_reference_exists(item.nodeid))):

                # Assemble runtimes test
                runtimes = []
                for k in range(self.num_runs):
                    with pgprof.Time() as timer:
                        item.runtest()
                    runtimes.append(timer.elapsed)

                # Create reference model
                self.data_manager.create_reference(item.nodeid, runtimes, self.model_name)

            # Compute runtime rank
            rank = self.data_manager.rank_runtime(item.nodeid, test_timer.elapsed)
            self.results.append(Result(
                test_node_id=item.nodeid,
                rank=rank))
