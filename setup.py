#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import codecs
from setuptools import setup


def read(fname):
    file_path = os.path.join(os.path.dirname(__file__), fname)
    return codecs.open(file_path, encoding='utf-8').read()


setup(
    name='pytest-marcabanca', version='0.1.0', author='Joaquin Zepeda',
    author_email='jazs.pro@gmail.com', maintainer='Joaquin Zepeda',
    maintainer_email='jazs.pro@gmail.com', license='MIT',
    url='https://github.com/zepedaj/pytest-marcabanca',
    description='A pytest plugin for runtime benchmarking', long_description=read('README.rst'),
    py_modules=['pytest_marcabanca'],
    python_requires='>=3.5',
    install_requires=['pytest>=3.5.0', 'py-cpuinfo==8.0.0', 'psutil==5.8.0', 'scipy==1.7.0',
                      'jsondiff==1.3.0'],
    classifiers=['Development Status :: 4 - Beta', 'Framework :: Pytest',
                 'Intended Audience :: Developers', 'Topic :: Software Development :: Testing',
                 'Programming Language :: Python', 'Programming Language :: Python :: 3',
                 'Programming Language :: Python :: 3.5', 'Programming Language :: Python :: 3.6',
                 'Programming Language :: Python :: 3.7', 'Programming Language :: Python :: 3.8',
                 'Programming Language :: Python :: 3 :: Only',
                 'Programming Language :: Python :: Implementation :: CPython',
                 'Programming Language :: Python :: Implementation :: PyPy',
                 'Operating System :: OS Independent', 'License :: OSI Approved :: MIT License', ],
    entry_points={'pytest11': ['marcabanca = pytest_marcabanca.pytest_marcabanca', ], },)
