import pytest_marcabanca.utils as mdl
from pglib.unittest.utils import swapattr
import scipy.stats as scipy_stats
import numpy.testing as npt
import numpy as np
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
        next(iter(pc1.specs['modules'])).version += '_different'
        self.assertNotEqual(pc1, pc2)


@contextmanager
def get_references_manager():
    with TemporaryDirectory() as temp_dir:
        rm = mdl.Manager(temp_dir)
        yield rm


class TestManager(TestCase):
    def test_create_write_reference(self):

        with get_references_manager() as mngr1:
            self.assertEqual(
                mngr1.data, empty_data := {
                    'machine_configs': [mdl.MachineConfiguration()],
                    'python_configs': [mdl.PythonConfiguration()],
                    'references': []})
            for model_name in ['gamma', 'gengamma', 'norm']:

                #
                mngr1.create_reference(
                    test_node_id := 'my.module::MyClass::my_method',
                    dist_domain := np.linspace(0, 1.0, 10),
                    model_name=model_name)

                # Check data has changed.
                [self.assertEqual(len(mngr1.data[_key]), 1) for _key in empty_data.keys()]
                self.assertEqual(mngr1.data['references'][0].reference_id,
                                 {'machine_config_id': mngr1.data['machine_configs'][0].config_id,
                                  'python_config_id': mngr1.data['python_configs'][0].config_id,
                                  'test_node_id': test_node_id})

                # Test check_exists
                self.assertTrue(mngr1.check_reference_exists(test_node_id))
                self.assertFalse(mngr1.check_reference_exists(test_node_id+'_missing'))

                # Check serialization
                mngr1.write()

                mngr2 = mdl.Manager(mngr1.root)

                self.assertEqual(
                    mngr1.data,
                    mngr2.data)

                # Check model distribs match specs.
                ref1 = mngr1.data['references'][0]
                npt.assert_array_equal(
                    getattr(scipy_stats, model_name)(*ref1.model_args).cdf(dist_domain),
                    ref1.model.cdf(dist_domain))

                # Check model distribs match between themselves
                ref2 = mngr2.data['references'][0]
                npt.assert_array_equal(
                    ref2.model.cdf(dist_domain),
                    ref1.model.cdf(dist_domain))

                # Check rank_runtime method.
                [npt.assert_array_equal(_x, _y) for _x, _y in zip(
                    (True, ref2.model.cdf(dist_domain)),
                    mngr2.rank_runtime(test_node_id, dist_domain)
                )]
                [npt.assert_array_equal(_x, _y) for _x, _y in zip(
                    mngr1.rank_runtime(test_node_id, dist_domain),
                    mngr2.rank_runtime(test_node_id, dist_domain)
                )]

    def test_find_exact_and_approx(self):
        with get_references_manager() as mngr1:
            existed, reference_id = mngr1.create_reference(
                test_node_id := 'my.module::MyClass::my_method',
                runtimes1 := np.linspace(0, 1.0, 10))
            self.assertFalse(existed)
            for _ref in [
                    mngr1.find_exact_reference_model(reference_id)[1],
                    mngr1.find_approx_reference_model(reference_id)[1],
                    mngr1.get_reference_model(reference_id['test_node_id'])[1]]:
                self.assertEqual(_ref.reference_id, reference_id)

            new_python_config = mdl.PythonConfiguration()
            next(iter(new_python_config.specs['modules'])).version += '_abc'

            new_machine_config = mdl.MachineConfiguration()
            new_machine_config.specs['cpuinfo'][
                mdl.MachineConfiguration.cpuinfo_keys[0]] += '_abc'

            # Check existing ref is overwritten
            self.assertEqual(len(mngr1.data['references']), 1)
            existed, reference_id__new = mngr1.create_reference(
                test_node_id := 'my.module::MyClass::my_method',
                runtimes2 := np.linspace(0, 1.0, 20))
            self.assertTrue(existed)
            self.assertEqual(reference_id__new, reference_id)
            npt.assert_array_equal(
                runtimes2, mngr1.find_exact_reference_model(reference_id)[1].runtimes)
            for _x in ['machine_config_id', 'test_node_id', 'python_config_id']:
                self.assertEqual(reference_id__new[_x], reference_id[_x])

            # Test find_approx.
            reference_id__new_py = dict(reference_id)
            reference_id__new_py['python_config_id'] = new_python_config.config_id
            self.assertNotEqual(reference_id__new_py, reference_id)
            self.assertIsNone(mngr1.find_exact_reference_model(reference_id__new_py))
            pos, approx_reference = mngr1.find_approx_reference_model(reference_id__new_py)
            self.assertEqual(approx_reference.reference_id, reference_id)
            self.assertEqual(
                approx_reference,
                mngr1.get_reference_model(reference_id['test_node_id'])[1])

            # Check new ref created when python config changes.
            with swapattr(mngr1, 'this_python_config', new_python_config):
                mngr1.data['python_configs'].append(new_python_config)
                existed, reference_id__new_py = mngr1.create_reference(
                    test_node_id := 'my.module::MyClass::my_method',
                    np.linspace(0, 1.0, 10))
                self.assertNotEqual(reference_id__new_py, reference_id)
                self.assertEqual(len(mngr1.data['references']), 2)
                self.assertFalse(existed)
                for _x in ['machine_config_id', 'test_node_id']:
                    self.assertEqual(reference_id__new_py[_x], reference_id[_x])
                for _x in ['python_config_id']:
                    self.assertNotEqual(reference_id__new_py[_x], reference_id[_x])

                for _ref in [
                        mngr1.find_exact_reference_model(reference_id__new_py)[1],
                        mngr1.find_approx_reference_model(reference_id__new_py)[1],
                        mngr1.get_reference_model(reference_id__new_py['test_node_id'])[1]]:
                    self.assertEqual(_ref.reference_id, reference_id__new_py)
