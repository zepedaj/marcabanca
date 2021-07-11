import uuid
import subprocess as subp
from cpuinfo import get_cpu_info
import psutil


class marcabanca:
    def __call__(self, fxn):
        pass


def register_identity():
    identity = get_specs()


def get_specs():
    {'mac_address': get_mac_address(),
     'cpuinfo': get_cpu_info(),
     'memory': psutil.virtual_memory()
     }


def get_mac_address(self, sudo=True):

    mac_address = uuid.UUID(int=uuid.getnode())

    cmd = (['sudo'] if sudo else []) + ['lshw', '-short']
    out = subp.check_output(cmd, text=True)
