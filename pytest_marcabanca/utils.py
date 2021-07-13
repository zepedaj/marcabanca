import uuid
import abc
from contextlib import ExitStack
from pglib.validation import checked_get_single
import numpy as np
import scipy.stats as scipy_stats
import warnings
from pglib.serializer.abstract_type_serializer import (
    AbstractTypeSerializer as _AbstractTypeSerializer)
from pglib.serializer import Serializer as _Serializer
from pglib.filelock import FileLock
from typing import Iterable, List, Union
import sys
import subprocess as subp
from cpuinfo import get_cpu_info
import psutil
import re
from dataclasses import dataclass
import platform
from secrets import token_hex


def find(obj_id, obj_list: List, id_attr_name):
    """
    Finds the object with the specified id in a list of objects.
    :return: Returns a list of 2-tuples containing the position in the list and object for all matching objects.
    """
    return [(_k, _obj) for _k, _obj in enumerate(obj_list)
            if getattr(_obj, id_attr_name) == obj_id]


class Manager:
    """
    Loads all data upon initialization and re-writes it with any updates upon calling :meth:`write`.
    """

    def __init__(self, machine_configs_path, python_configs_path, references_path, create=True):
        """
        Loads all machine configurations, python configurations and references from disk.

        :param *_path: Paths to json files containing the machine configurations, the python configurations and the references, respectively.
        :param create: If the paths do not exist, create them.
        """

        self.serializer = _Serializer()

        # Create the files if they do not exist.
        if create:
            with ExitStack() as stack:
                [stack.enter_context(open(_path, 'a')) for _path in
                 [machine_configs_path, python_configs_path, references_path]]

        # Load all data from the files.
        serializer = _Serializer()
        self.paths = {
            'machine_configs': machine_configs_path,
            'python_configs': python_configs_path,
            'references': references_path
        }
        self.data = {
            'machine_configs': serializer.load_safe(machine_configs_path)[0] or [],
            'python_configs': serializer.load_safe(python_configs_path)[0] or [],
            'references': serializer.load_safe(references_path)[0] or []}

        # Get this environment's configuration and ensure it exists in the data dictionary.
        this_machine_config = MachineConfiguration()
        this_python_config = PythonConfiguration()

        if this_machine_config not in self.data['machine_configs']:
            self.data['machine_configs'].append(this_machine_config)
        self.this_machine_config = checked_get_single(
            [_x for _x in self.data['machine_configs'] if _x == this_machine_config])

        if this_python_config not in self.data['python_configs']:
            self.data['python_configs'].append(this_python_config)
        self.this_python_config = checked_get_single(
            [_x for _x in self.data['python_configs'] if _x == this_python_config])

    def build_reference_id(self, test_node_id):
        return {'machine_config_id': self.this_machine_config.config_id,
                'python_config_id': self.this_python_config.config_id,
                'test_node_id': test_node_id}

    def rank_runtime(self, test_node_id, runtime):
        r"""
        Compares the runtime to the reference model for the specified model and current machine. If no reference model exists for the current machine, the first reference model for the ``test_node_id`` is used.

        :param test_node_id: The pytest test identifier (e.g., 'my.module::MyClass::my_method')
        :param runtime: The test duration as a positive float.
        :return: The rank :math:`\in [0,1]` (i.e., the CDF value evaluated at the given runtime) representing the percentage of the runtime population with a value that is lower than the specified runtime.
        """
        reference_id = self.build_reference_id(test_node_id)

        if (reference := ReferenceModel.find(reference_id, self.data['references'])):
            exact = True
        elif (references := [_x for _x in self.data['references'] if _x.reference_id['test_node_id'] == test_node_id]):
            exact = False
            reference = references[0]
        else:
            return None, None

        return exact, reference.compare(runtime)

    def check_exists(self, test_node_id):
        """
        Returns the found reference or None.
        """
        reference_id = self.build_reference_id(test_node_id)
        return ReferenceModel.find(reference_id, self.data['reference_ids'])

    def create_reference(self, test_node_id, runtimes, model_name='gamma'):
        """
        Creates a reference model for the specified test and the current environment.
        """
        #
        reference_id = self.build_reference_id(test_node_id)
        #
        reference = ReferenceModel(reference_id, model_name=model_name)
        reference.fit(runtimes)
        #
        posn_reference = ReferenceModel.find(reference_id, self.data['references'])
        if posn_reference:
            self.data['references'][posn_reference[0]] = reference
        else:
            self.data['references'].append(reference)

    def write(self):
        """
        Writes all machine configurations, python configurations and references to disk.
        """
        with ExitStack() as stack:
            [stack.enter_context(FileLock(_x)) for _x in self.paths.values()]
            [self.serializer.dump(self.data[key], self.paths[key]) for key in self.data]


class ReferenceModel(_AbstractTypeSerializer):
    """
    Represents runtimes together with a probabilistic model fitted to those runtimes.
    """

    def __init__(self, reference_id, model_name='gamma'):
        """
        :param reference_id: An arbitrary identifier.
        :param model_name: Any of the distributions in :mod:`scipy.stats` (e.g., 'gamma', 'norm', 'gengamma'). (The default is 'gamma'.)
        """
        #
        self.reference_id = reference_id
        self.model_type = getattr(scipy_stats, model_name)
        self.model_name = model_name
        #
        self.runtimes = None
        #
        self.model = None
        self.model_args = None

    def fit(self, runtimes):
        self.runtimes = runtimes
        self.model_args = self.model_type.fit(runtimes)
        self.model = self.model_type(*self.model_args)

    @classmethod
    def find(self, reference_id, reference_list):
        """
        Same as :func:`find`, but ensures at most one reference exists. Returns a :class:`Reference` object and its position.

        :return: (reference, position) or None
        """
        if (reference := find(reference_id, reference_list, 'reference_id')):
            return checked_get_single(
                reference,
                msg=f'Expected 1 but found {{count}} references matching id {reference_id}.')
        else:
            return None

    def compare(self, x):
        """
        Returns the rank of x in the fitted distribution (i.e., the percentage of the population with a value lower than x as per the fitted distribution).
        """

        if self.model is None:
            raise Exception('Cannot compute a cdf because a model has not been fitted.')
        return self.model.cdf(x)

    def __eq__(self, obj):
        if self.model is None or obj.model is None:
            raise Exception('Cannot compare models because one of the models has not been fitted.')
        return (
            self.model_name == obj.model_name and
            self.model_args == obj.model_args)

    @classmethod
    def _as_serializable(cls, obj):
        if obj.model is None:
            raise Exception('The model cannot be serialized because it has not been fitted.')
        return {
            'reference_id': obj.reference_id,
            'model_name': obj.model_name,
            'runtimes': obj.runtimes,
            'model_args': obj.model_args}

    @classmethod
    def _from_serializable(cls, data):
        obj = cls(data['reference_id'], data['model_name'])
        obj.runtimes = data['runtimes']
        obj.model = obj.model_type(*data['model_args'])
        obj.model_args = data['model_args']
        return obj


@dataclass
class PythonModule(_AbstractTypeSerializer):
    _keys = ['package', 'version', 'location']
    package: str
    version: str
    location: str = None

    def __eq__(self, pm):
        return (
            self.package == pm.package and
            self.version == pm.version)

    def __hash__(self):
        return hash((self.package, self.version))

    @classmethod
    def _as_serializable(cls, obj):
        return {key: getattr(obj, key) for key in cls._keys}

    @classmethod
    def _from_serializable(cls, data):
        return cls(**data)


class _AbstractConfiguration(_AbstractTypeSerializer, abc.ABC):
    def __init__(self, config_id=None, specs=None):
        """
        :param config_id: An arbitrary identifier. If none is provided, a random 32-char hash will be generated internally.
        :param specs: The configuration parameters. If None is provided, these will be extracted automatically.
        """
        self.config_id = config_id or self._generate_new_id()
        self.specs = specs or self._get_this_specs()

    @abc.abstractmethod
    def _get_this_specs(self):
        """
        Returns the specifications for this environment.
        """

    @classmethod
    def _as_serializable(cls, obj):
        return {'config_id': obj.config_id, 'specs': obj.specs}

    @classmethod
    def _from_serializable(cls, data):
        return cls(config_id=data['config_id'], specs=data['specs'])

    @classmethod
    def _generate_new_id(cls):
        return token_hex(16)


class PythonConfiguration(_AbstractConfiguration):

    @classmethod
    def _get_this_specs(cls):
        return {'python': sys.version,
                'modules': [
                    PythonModule(*re.split(r'\s+', _x))
                    for _x in subp.check_output(
                        ['pip', 'list'], text=True).strip().split('\n')[2:]]}

    def __eq__(self, other: 'PythonConfiguration'):
        return (
            self.specs['python'] == other.specs['python'] and
            set(self.specs['modules']) == set(other.specs['modules']))


class MachineConfiguration(_AbstractConfiguration):
    """
    Represents the machine's hardware configuration.
    """

    @classmethod
    def _get_this_specs(cls):
        return {
            'host': platform.node(),
            'mac_address': cls.get_mac_address(),
            'cpuinfo': get_cpu_info(),
            'memory': psutil.virtual_memory().total
        }

    @staticmethod
    def get_mac_address():
        return str(uuid.UUID(int=uuid.getnode()))

    def __eq__(self, other: 'MachineConfiguration'):
        """
        Ignores the config_id value.
        """
        if not isinstance(other, type(self)):
            return NotImplemented
        return self.specs == other.specs


# Register type serializers
_Serializer.default_extension_types.extend([
    PythonConfiguration, MachineConfiguration, PythonModule, ReferenceModel])
