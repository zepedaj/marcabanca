import uuid
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

    def __init__(self, machine_configs_path, python_configs_path, references_path):

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

        # Get this machine's configurations and ensure they exist in data
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
                'python_config_id': self.python_machine_config.config_id,
                'test_node_id': test_node_id}

    def compare_runtime(self, test_node_id, runtime):
        reference_id = self.build_reference_id(test_node_id)

        if (reference := Reference.find(reference_id, self.data['references'])):
            exact = True
        elif (references := [_x for _x in self.data['references'] if _x.reference_id['test_node_id'] == test_node_id]):
            exact = False
            reference = references[0]
        else:
            return None

        return exact, reference.compare(runtime)

    def check_exists(self, test_node_id):
        reference_id = self.build_reference_id(test_node_id)
        return Reference.find(reference_id, self.data['reference_ids'])

    def create_reference(self, test_node_id, runtimes):
        reference_id = self.build_reference_id(test_node_id)
        posn, reference = Reference.find(reference_id, self.data['references'])
        if reference:
            reference.runtimes = runtimes
            reference.fit()
        else:
            reference = Reference(reference_id, runtimes)
            self.data['references'].append(reference)

    def write(self):
        with ExitStack() as stack:
            [stack.enter_context(FileLock(_x)) for _x in self.paths.values()]
            [self.serializer.dump(self.data[key], self.path[key]) for key in self.data]


class Reference:
    def __init__(self, reference_id, runtimes, model=None):
        self.reference_id = reference_id
        self.runtimes = np.require(runtimes, dtype='f').tolist()
        self.model = model

    def fit(self):
        self.model = _ProbModel('gamma')
        self.model.fit(self.runtimes)

    @classmethod
    def find(self, reference_id):
        """
        Same as :func:`find`, but ensures at most one reference exists. Returns a :class:`Reference` object, and not a list of objects.
        """
        if (reference := find(reference_id, self.data['references'], 'reference_id')[1]):
            return checked_get_single(
                reference,
                msg=f'Expected 1 but found {{count}} references matching id {reference_id}.')
        else:
            return None, None

    def compare(self, x):
        """
        Returns the rank of x in the cdf (i.e., percentage of samples lower than x as per the model).
        """
        return self.model.cdf(x)

    @classmethod
    def _as_serializable(self, obj):
        if self.model is None:
            raise Exception('Request to save a model that has not been fit.')
        return {
            'reference_id': self.reference_id,
            'runtimes': self.runtimes,
            'model': self.model}

    @classmethod
    def _from_serializable(cls, data):
        return cls(data['reference_id'], data['runtimes'], data['model'])


class _ProbModel(_AbstractTypeSerializer):
    _model_types = {'gamma': scipy_stats.gamma}

    def __init__(self, model_name):
        self.model_type = self._model_types[model_name]
        self.model_name = model_name
        self.model = None
        self.args = None
        self.kwargs = None

    def load(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        self.model = self.model_type(*args, **kwargs)

    def fit(self, runtimes):
        self.args = self.model_type.fit(runtimes)
        self.kwargs = {}
        self.model = self.model_type(*self.args)

    def cdf(self, x):
        if self.model is None:
            raise Exception('Cannot bcompute a cdf because a model has not been fitted.')
        return self.model.cdf(x)

    def __eq__(self, obj):
        if self.model is None or obj.model is None:
            raise Exception('Cannot compare models because one of the models has not been fitted.')
        return (
            self.model_name == obj.model_name and
            self.args == obj.args and
            self.kwargs == obj.kwargs)

    @classmethod
    def _as_serializable(cls, obj):
        if obj.args is None or obj.kwargs is None:
            raise Exception('The model cannot be serialized because it has not been fitted.')
        return {'model_name': obj.model_name,
                'args': obj.args,
                'kwargs': obj.kwargs}

    @classmethod
    def _from_serializable(cls, data):
        model = cls(data['model_name'])
        model.load(*data['args'], **data['kwargs'])
        return model


@dataclass
class _PythonModule(_AbstractTypeSerializer):
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


class _AbstractConfiguration(_AbstractTypeSerializer):
    @classmethod
    def _as_serializable(cls, obj):
        return {'config_id': obj.config_id, 'specs': obj.specs}

    @classmethod
    def _from_serializable(cls, data):
        return cls(config_id=data['config_id'], specs=data['specs'])

    @classmethod
    def _get_new_id(cls):
        return token_hex(16)


class PythonConfiguration(_AbstractConfiguration):
    def __init__(self, config_id=None, specs=None):
        self.config_id = config_id or self._get_new_id()
        self.specs = specs or self._get_specs()

    @classmethod
    def _get_specs(cls):
        return {'python': sys.version,
                'modules': [
                    _PythonModule(*re.split(r'\s+', _x))
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

    def __init__(self, config_id=None, specs=None):

        self.config_id = config_id or self._get_new_id()
        specs = specs or self._get_specs()
        self.specs = specs

    @classmethod
    def _get_specs(cls):
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
        return self.specs == other.specs


# Register type serializers
_Serializer.default_extension_types.extend([
    PythonConfiguration, MachineConfiguration, _PythonModule, _ProbModel, Reference])
