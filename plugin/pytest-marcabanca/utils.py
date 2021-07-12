import uuid
import subprocess as subp
from cpuinfo import get_cpu_info
import psutil
import re
from dataclasses import dataclass
import platform


@dataclass
class PythonModule:
    package: str
    version: str
    location: str = None


class PythonConfiguration:
    def __init__(self, specs):
        self.specs = specs or self._get_specs()

    @ classmethod
    def _get_specs(cls):
        return [PythonModule(*re.split(r'\s+', _x))
                for _x in subp.check_output(['pip', 'list']).split('\n')[2:]]

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

    def __eq__(self, other):
        return self.specs == other.specs
