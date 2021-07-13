import pytest_marcabanca.utils as mdl
import numpy.testing as npt
import numpy as np
import os.path as osp
from unittest import TestCase
from pglib.serializer import Serializer
from tempfile import TemporaryDirectory
from contextlib import contextmanager


class TestMachineConfiguration(TestCase):

    serializer = Serializer()

    def test_serialize(self):

        mc = mdl.MachineConfiguration()
        self.assertEqual(
            self.serializer.deserialize(self.serializer.serialize(mc)),
            mc)

    def test_eq(self):
        mc1 = mdl.MachineConfiguration()
        mc2 = mdl.MachineConfiguration()
        self.assertEqual(mc1, mc2)
        mc1.specs['cpuinfo']['arch'] = mc1.specs['cpuinfo']['arch'] + '_different'
        self.assertNotEqual(mc1, mc2)


class TestPythonConfiguration(TestCase):

    serializer = Serializer()

    def test_serialize(self):

        mc = mdl.PythonConfiguration()
        self.assertEqual(
            self.serializer.deserialize(self.serializer.serialize(mc)),
            mc)

    def test_eq(self):
        pc1 = mdl.PythonConfiguration()
        pc2 = mdl.PythonConfiguration()
        self.assertEqual(pc1, pc2)
        pc1.specs['modules'][0].version = pc1.specs['modules'][0].version+'_different'
        self.assertNotEqual(pc1, pc2)


@contextmanager
def get_references_manager():
    with TemporaryDirectory() as temp_dir:
        rm = mdl.ReferencesManager(osp.join(temp_dir, 'machines.json'),
                                   osp.join(temp_dir, 'python.json'),
                                   osp.join(temp_dir, 'references.json'))
        yield rm


class TestReferencesManager(TestCase):
    def test_retrieve_or_store_this_env_config_id(self):
        with get_references_manager() as rm:
            env_id = rm.retrieve_or_store_this_env_config_id()
            [self.assertTrue(
                isinstance(env_id[_conf_type], str) and len(env_id[_conf_type]) == 32)
             for _conf_type in ['machine_config_id', 'python_config_id']]

            self.assertEqual(
                mdl.MachineConfiguration(),
                rm._retrieve_config_from_id('machine', env_id['machine_config_id']))

            self.assertEqual(
                mdl.PythonConfiguration(),
                rm._retrieve_config_from_id('python', env_id['python_config_id']))

    def test_create_write_reference(self):
        with get_references_manager() as rm:
            self.assertEqual(rm.get_retrieved_references(), [])
            rm.create_reference('my.module::MyClass::my_meth', np.linspace(0, 1.0, 10))
            self.assertNotEqual(rm.get_retrieved_references(), [])
            rm.write_references()

            rm2 = mdl.ReferencesManager(
                machine_configs_path=rm.config_paths['machine'],
                python_configs_path=rm.config_paths['python'],
                references_path=rm.config_paths['references'])

            self.assertEqual(
                rm.get_retrieved_references(),
                rm2.get_retrieved_references())


class Test_ProbModel(TestCase):
    def test_serialize(self):
        runtimes = np.linspace(0, 1.0, 10)
        pm = mdl._ProbModel('gamma')
        pm.fit(runtimes)
        cdf = pm.cdf(runtimes)

        serializer = Serializer()
        npt.assert_array_equal(
            serializer.deserialize(serializer.serialize(pm)).cdf(runtimes),
            cdf)
