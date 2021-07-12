# -*- coding: utf-8 -*-
import pytest
import os
import sys
from py.path import local
from pglib.filelock import FileLock
import pglib.validation as pgval
import pglib.profiling as pgprof
import py


# def pytest_addoption(parser):
#     group = parser.getgroup('marcabanca')
#     group.addoption(
#         '--foo',
#         action='store',
#         dest='dest_foo',
#         default='2021',
#         help='Set the value for the fixture "bar".'
#     )

#     parser.addini('HELLO', 'Dummy pytest.ini setting')


# @pytest.fixture
# def bar(request):
#     return request.config.option.dest_foo

def pytest_addoption(parser):
    group = parser.getgroup('marcabanca')
    group.addoption(
        '--mb-root', default=None, type=local,
        help='Directory where marcabanca benchmarking results are stored (<tests root>/marcabanca/ by default).'),
    group.addoption(
        '--mb-tests', default='all', choices=['all', 'decorated'],
        help="['all' | 'decorated'] Run benchmarking tests on 'all' tests or only those 'decorated' with an @marcabanca decorator.",)


class Profiling(object):
    """Profiling plugin for pytest."""
    svg = False
    svg_name = None
    profs = []
    combined = None

    def __init__(self, root, which_tests):
        self.root = root
        self.filelock = None
        self.which_tests = pgval.check_option('which_tests', which_tests, ['all', 'decorated'])

    # JSON file paths.
    @property
    def runtimes_path(self):
        return self.root.join('runtimes.json')

    @property
    def machines_path(self):
        return self.root.join('machines.json')

    @property
    def python_envs_path(self):
        return self.root.join('python_envs.json')

    @property
    def filelock_path(self):
        return self.machines_path

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

        # Create json files if necessary.
        self.filelock = FileLock(self.filelock_path)
        self.filelock.acquire(create=True)
        for path in [self.runtimes_path,
                     self.machines_path,
                     self.python_envs_path]:
            with open(path, 'a+'):
                pass

    def pytest_sessionfinish(self, session, exitstatus):
        self.filelock.release()

    def get_configuration(self):
        with open(self.machines_path, 'rt+') as fo:
            pass

    @pytest.hookimpl()
    def pytest_runtest_call(self, item):

        if self.which_tests == 'all' or (
                self.which_tests == 'decorated' and hasattr(item.function, 'marcabanca')):

            # Execute test.
            for k in range(10):
                with pgprof.Time() as timer:
                    item.runtest()

        else:
            item.runtest()


def pytest_configure(config):
    """pytest_configure hook for profiling plugin"""
    mb_root = config.getvalue('mb_root')

    # if profile_enable:
    # config.pluginmanager.register(Profiling(config.getvalue('profile_svg'),
    #                                        config.getvalue('pstats_dir')))
    config.pluginmanager.register(
        Profiling(config.getvalue('mb_root'), config.getvalue('mb_tests')))
