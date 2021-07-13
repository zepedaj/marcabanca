import pytest_marcabanca.utils as mdl
import scipy.stats as scipy_stats
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
        paths = [osp.join(temp_dir, 'machines.json'),
                 osp.join(temp_dir, 'python.json'),
                 osp.join(temp_dir, 'references.json')]
        rm = mdl.Manager(*paths)
        yield rm


class TestReferencesManager(TestCase):
    def test_create_write_reference(self):

        with get_references_manager() as mngr:
            self.assertEqual(
                mngr.data, empty_data := {
                    'machine_configs': [mdl.MachineConfiguration()],
                    'python_configs': [mdl.PythonConfiguration()],
                    'references': []})
            for model_name in ['gamma', 'gengamma', 'norm']:

                #
                mngr.create_reference(
                    test_node_id := 'my.module::MyClass::my_method',
                    dist_domain := np.linspace(0, 1.0, 10),
                    model_name=model_name)

                # Check data has changed.
                [self.assertEqual(len(mngr.data[_key]), 1) for _key in empty_data.keys()]
                self.assertEqual(mngr.data['references'][0].reference_id,
                                 {'machine_config_id': mngr.data['machine_configs'][0].config_id,
                                  'python_config_id': mngr.data['python_configs'][0].config_id,
                                  'test_node_id': test_node_id})

                # Check serialization
                mngr.write()

                mngr2 = mdl.Manager(
                    machine_configs_path=mngr.paths['machine_configs'],
                    python_configs_path=mngr.paths['python_configs'],
                    references_path=mngr.paths['references'])

                self.assertEqual(
                    mngr.data,
                    mngr2.data)

                # Check model distribs match specs.
                ref = mngr.data['references'][0]
                npt.assert_array_equal(
                    getattr(scipy_stats, model_name)(*ref.model_args).cdf(dist_domain),
                    ref.model.cdf(dist_domain))

                # Check model distribs match between themselves
                ref2 = mngr.data['references'][0]
                npt.assert_array_equal(
                    ref2.model.cdf(dist_domain),
                    ref.model.cdf(dist_domain))
