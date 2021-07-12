import uuid
from pglib.filelock import FileLock
from typing import Union, Dict
import json
import sys
import subprocess as subp
from cpuinfo import get_cpu_info
import psutil
import re
from dataclasses import dataclass
import platform
from secrets import token_hex


class ConfigurationManager:

    def __init__(self, machine_config_path, python_config_path):
        self.machine_config_path = machine_config_path
        self.python_config_path = python_config_path

    def get_conf_id(self):
        """
        Returns a JSON-serializable machine and python configuration identifier.
        """
        mach_conf_id = self._get_conf_id_helper('machine',
                                                MachineConfiguration(),
                                                self.machine_config_path)
        py_conf_id = self._get_conf_id_helper('python',
                                              PythonConfiguration(),
                                              self.python_config_path)
        return {'machine_conf_id': mach_conf_id,
                'python_conf_id': py_conf_id}

    def _get_conf_id_helper(self, type_name, this_conf, json_path):

        # Get the configuration identifier.
        file_lock = FileLock(json_path)
        with file_lock.with_acquire(create=True):
            with open(json_path, 'r') as fo:
                id_conf_pairs = [json.loads(ln) for ln in fo.readline()]

            match = [(_id, _conf) for _id, _conf in id_conf_pairs
                     if this_conf == _conf]
            if match:
                # This configuration was already in the file.
                conf_id = match[0][0]
            else:
                # This configuration was not in the file, add it.
                conf_id = token_hex(16)
                id_conf_pairs.append(
                    {f'{type_name}_conf_id': conf_id, f'{type_name}_conf': this_conf.specs})
                with open(json_path, 'w') as fo:
                    json.dump(id_conf_pairs, fo, indent=4)

        return conf_id

        # Get the py env identifier.


@dataclass
class _PythonModule:
    package: str
    version: str
    location: str = None


class PythonConfiguration:
    def __init__(self, specs):
        self.specs = specs or self._get_specs()

    @ classmethod
    def _get_specs(cls):
        return {'python': sys.version,
                'modules': [_PythonModule(*re.split(r'\s+', _x))
                            for _x in subp.check_output(['pip', 'list']).split('\n')[2:]]}

    def __eq__(self, other):
        return set(self.specs) == set(other.specs)


class MachineConfiguration:
    """
    Represents the machine's hardware configuration.
    """

    def __init__(self, specs=None, sudo=False):

        specs = specs or self._get_specs(sudo)
        self.specs = specs

    @ classmethod
    def _get_specs(cls):
        return {
            'host': platform.node(),
            'mac_address': cls.get_mac_address(),
            'cpuinfo': get_cpu_info(),
            'memory': psutil.virtual_memory()['total']
        }

    @ staticmethod
    def get_mac_address(sudo=True):
        return uuid.UUID(int=uuid.getnode())

    def __eq__(self, other: Union['MachineConfiguration', Dict]):
        return self.specs == getattr(other, 'specs', other)
