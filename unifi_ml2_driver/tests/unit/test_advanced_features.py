# Copyright 2024 StackHPC Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import asyncio
import threading
import time
import unittest
from unittest import mock

from neutron_lib import constants as n_const
from neutron_lib.plugins import directory
from neutron_lib.callbacks import resources
from neutron_lib.callbacks import events
from oslo_config import cfg

from unifi_ml2_driver import exceptions
from unifi_ml2_driver import unifi_mech


class TestUnifiPortMonitoring(unittest.TestCase):
    """Test cases for UniFi port monitoring functionality."""

    def setUp(self):
        """Set up test environment."""
        # Mock configuration
        self.mock_cfg = mock.patch.object(cfg, 'CONF')
        self.mock_cfg.start()

        # Set up configuration
        unifi_group = cfg.OptGroup(name='unifi')
        cfg.CONF.register_group(unifi_group)
        cfg.CONF.register_opts(unifi_mech.unifi_opts, group='unifi')
        cfg.CONF.set_override('controller', 'https://unifi.example.com', group='unifi')
        cfg.CONF.set_override('username', 'admin', group='unifi')
        cfg.CONF.set_override('password', 'password', group='unifi')
        cfg.CONF.set_override('verify_ssl', False, group='unifi')
        cfg.CONF.set_override('monitor_port_state', True, group='unifi')
        cfg.CONF.set_override('monitor_interval', 1, group='unifi')  # Short interval for tests

        # Create driver instance
        self.driver = unifi_mech.UnifiMechDriver()
        
        # Mock controller
        self.mock_controller = mock.MagicMock()
        self.mock_controller.__enter__.return_value = self.mock_controller
        
        # Mock devices for controller
        self.fake_switch = mock.MagicMock()
        self.fake_switch.mac = '78:45:58:ab:cd:ef'
        self.fake_switch.type = 'usw'
        self.fake_switch.port_table = [
            {'port_idx': 1, 'name': 'Port 1', 'up': True},
            {'port_idx': 2, 'name': 'Port 2', 'up': False},
            {'port_idx': 3, 'name': 'Port 3', 'up': True}
        ]
        
        self.mock_controller.devices.update.return_value = asyncio.Future()
        self.mock_controller.devices.update.return_value.set_result([self.fake_switch])
        
        # Patch get_controller method
        self.mock_get_controller = mock.patch.object(
            self.driver, '_get_controller', return_value=self.mock_controller)
        self.mock_get_controller.start()
        
        # Set up port mappings
        self.driver.port_mappings = {
            'port-1': {'switch_id': '78:45:58:ab:cd:ef', 'port_id': '1', 'vlan_id': 100},
            'port-2': {'switch_id': '78:45:58:ab:cd:ef', 'port_id': '2', 'vlan_id': 100},
            'port-3': {'switch_id': '78:45:58:ab:cd:ef', 'port_id': '3', 'vlan_id': 100}
        }
        
        # Mock threading
        self.mock_thread = mock.MagicMock()
        self.thread_patch = mock.patch('threading.Thread', return_value=self.mock_thread)
        self.mock_thread_class = self.thread_patch.start()
        
        # Mock directory
        self.mock_core_plugin = mock.MagicMock()
        self.directory_patch = mock.patch.object(
            directory, 'get_plugin', return_value=self.mock_core_plugin)
        self.mock_directory = self.directory_patch.start()
        
        # Mock time.sleep to avoid actual sleeping in tests
        self.sleep_patch = mock.patch('time.sleep')
        self.mock_sleep = self.sleep_patch.start()

    def tearDown(self):
        """Clean up test environment."""
        self.mock_cfg.stop()
        self.mock_get_controller.stop()
        self.thread_patch.stop()
        self.directory_patch.stop()
        self.sleep_patch.stop()
        
    def test_start_port_monitor(self):
        """Test starting port monitor thread."""
        self.driver.start_port_monitor()
        
        # Verify thread was created with correct arguments
        self.mock_thread_class.assert_called_once_with(
            target=self.driver._port_monitor_loop,
            daemon=True
        )
        
        # Verify thread was started
        self.mock_thread.start.assert_called_once()
        
    def test_start_port_monitor_disabled(self):
        """Test port monitor when disabled in configuration."""
        # Disable port monitoring
        cfg.CONF.set_override('monitor_port_state', False, group='unifi')
        
        # Call start_port_monitor
        self.driver.start_port_monitor()
        
        # Verify thread was not created
        self.mock_thread_class.assert_not_called()

    def test_port_monitor_loop(self):
        """Test port monitor loop."""
        # Set up mocks for first and second iteration
        self.mock_sleep.side_effect = [None, Exception("Stop loop")]  # Stop after second iteration
        
        # Patch _check_port_status to track calls
        mock_check = mock.patch.object(self.driver, '_check_port_status')
        check_patch = mock_check.start()
        
        # Call loop with expectation that it will exit after second iteration
        with self.assertRaises(Exception):
            self.driver._port_monitor_loop()
        
        # Verify _check_port_status was called twice
        self.assertEqual(check_patch.call_count, 2)
        
        # Verify sleep was called with correct interval
        self.mock_sleep.assert_called_with(1)
        
        mock_check.stop()
        
    def test_check_port_status(self):
        """Test checking port status."""
        # Call _check_port_status
        self.driver._check_port_status()
        
        # Verify devices were fetched
        self.mock_controller.devices.update.assert_called_once()
        
        # Patch _update_port_status_in_neutron to verify calls
        mock_update = mock.patch.object(self.driver, '_update_port_status_in_neutron')
        update_patch = mock_update.start()
        
        # Call _check_port_status again
        self.driver._check_port_status()
        
        # Verify _update_port_status_in_neutron was called with correct port status
        update_patch.assert_called_once()
        port_status_arg = update_patch.call_args[0][0]
        
        # Verify port status was correctly determined
        self.assertEqual(port_status_arg['port-1'], n_const.PORT_STATUS_ACTIVE)
        self.assertEqual(port_status_arg['port-2'], n_const.PORT_STATUS_DOWN)
        self.assertEqual(port_status_arg['port-3'], n_const.PORT_STATUS_ACTIVE)
        
        mock_update.stop()
        
    def test_update_port_status_in_neutron(self):
        """Test updating port status in Neutron."""
        # Set up mock port objects with current status
        self.mock_core_plugin.get_port.side_effect = lambda ctx, id: {
            'port-1': {'status': n_const.PORT_STATUS_ACTIVE},
            'port-2': {'status': n_const.PORT_STATUS_ACTIVE},  # Will be changed to DOWN
            'port-3': {'status': n_const.PORT_STATUS_ACTIVE}
        }[id]
        
        # Create port status map with one changed port
        port_status = {
            'port-1': n_const.PORT_STATUS_ACTIVE,
            'port-2': n_const.PORT_STATUS_DOWN,  # Changed from ACTIVE
            'port-3': n_const.PORT_STATUS_ACTIVE
        }
        
        # Call _update_port_status_in_neutron
        self.driver._update_port_status_in_neutron(port_status)
        
        # Verify update_port_status was called only for changed port
        self.mock_core_plugin.update_port_status.assert_called_once_with(
            mock.ANY, 'port-2', n_const.PORT_STATUS_DOWN)


class TestUnifiTrunkPortConfiguration(unittest.TestCase):
    """Test cases for UniFi trunk port configuration."""

    def setUp(self):
        """Set up test environment."""
        # Mock configuration
        self.mock_cfg = mock.patch.object(cfg, 'CONF')
        self.mock_cfg.start()

        # Set up configuration
        unifi_group = cfg.OptGroup(name='unifi')
        cfg.CONF.register_group(unifi_group)
        cfg.CONF.register_opts(unifi_mech.unifi_opts, group='unifi')
        cfg.CONF.set_override('controller', 'https://unifi.example.com', group='unifi')
        cfg.CONF.set_override('username', 'admin', group='unifi')
        cfg.CONF.set_override('password', 'password', group='unifi')
        cfg.CONF.set_override('verify_ssl', False, group='unifi')
        cfg.CONF.set_override('use_all_networks_for_trunk', True, group='unifi')
        
        # Create driver instance
        self.driver = unifi_mech.UnifiMechDriver()
        
        # Mock controller
        self.mock_controller = mock.MagicMock()
        self.mock_controller.__enter__.return_value = self.mock_controller
        
        # Mock devices for controller
        self.fake_switch = mock.MagicMock()
        self.fake_switch.mac = '78:45:58:ab:cd:ef'
        self.fake_switch.type = 'usw'
        self.fake_switch.port_table = [
            {'port_idx': 1, 'name': 'Port 1'},
            {'port_idx': 2, 'name': 'Port 2'},
            {'port_idx': 3, 'name': 'Port 3'}
        ]
        
        self.mock_controller.devices.update.return_value = asyncio.Future()
        self.mock_controller.devices.update.return_value.set_result([self.fake_switch])
        
        # Patch get_controller method
        self.mock_get_controller = mock.patch.object(
            self.driver, '_get_controller', return_value=self.mock_controller)
        self.mock_get_controller.start()
        
        # Mock directory
        self.mock_core_plugin = mock.MagicMock()
        self.directory_patch = mock.patch.object(
            directory, 'get_plugin', return_value=self.mock_core_plugin)
        self.mock_directory = self.directory_patch.start()
        
        # Mock successful port configuration
        self.mock_controller.devices.async_set_port_conf.return_value = asyncio.Future()
        self.mock_controller.devices.async_set_port_conf.return_value.set_result(True)
        
        # Mock context
        self.mock_context = mock.MagicMock()
        self.context_patch = mock.patch('neutron_lib.context.get_admin_context',
                                      return_value=self.mock_context)
        self.mock_context_factory = self.context_patch.start()

    def tearDown(self):
        """Clean up test environment."""
        self.mock_cfg.stop()
        self.mock_get_controller.stop()
        self.directory_patch.stop()
        self.context_patch.stop()
        
    def test_configure_trunk_port(self):
        """Test trunk port configuration."""
        # Set up mock port and network
        port_obj = {
            'id': 'port-1',
            'network_id': 'network-1'
        }
        
        # Mock network to return native VLAN
        self.mock_core_plugin.get_network.return_value = {
            'provider:segmentation_id': 100
        }
        
        # Set up subports
        subports = [
            {'port_id': 'subport-1', 'segmentation_id': 200},
            {'port_id': 'subport-2', 'segmentation_id': 300}
        ]
        
        # Call _configure_trunk_port
        self.driver._configure_trunk_port('78:45:58:ab:cd:ef', '1', port_obj, subports)
        
        # Verify port configuration was called
        self.mock_controller.devices.async_set_port_conf.assert_called_once()
        
        # Verify the port configuration parameters
        args = self.mock_controller.devices.async_set_port_conf.call_args[0][0]
        self.assertEqual(args['mac'], '78:45:58:ab:cd:ef')
        self.assertEqual(args['port_idx'], 1)
        self.assertTrue(args['port_vlan_enabled'])
        self.assertEqual(args['port_vlan'], 100)  # Native VLAN
        self.assertEqual(args['vlan_mode'], 'all')  # All networks mode
        
    def test_configure_trunk_port_specific_vlans(self):
        """Test trunk port configuration with specific VLANs."""
        # Disable use_all_networks_for_trunk
        cfg.CONF.set_override('use_all_networks_for_trunk', False, group='unifi')
        
        # Set up mock port and network
        port_obj = {
            'id': 'port-1',
            'network_id': 'network-1'
        }
        
        # Mock network to return native VLAN
        self.mock_core_plugin.get_network.return_value = {
            'provider:segmentation_id': 100
        }
        
        # Set up subports
        subports = [
            {'port_id': 'subport-1', 'segmentation_id': 200},
            {'port_id': 'subport-2', 'segmentation_id': 300}
        ]
        
        # Call _configure_trunk_port
        self.driver._configure_trunk_port('78:45:58:ab:cd:ef', '1', port_obj, subports)
        
        # Verify port configuration was called
        self.mock_controller.devices.async_set_port_conf.assert_called_once()
        
        # Verify the port configuration parameters
        args = self.mock_controller.devices.async_set_port_conf.call_args[0][0]
        self.assertEqual(args['vlan_mode'], 'tagged')  # Tagged mode
        self.assertEqual(args['tagged_vlan'], [200, 300])  # Specific VLANs
        
    def test_add_subports_on_trunk(self):
        """Test adding subports to trunk port."""
        # Set up binding profile
        binding_profile = {
            'parent_port_id': 'parent-port-1',
            'local_link_information': [
                {
                    'switch_id': '78:45:58:ab:cd:ef',
                    'port_id': '1'
                }
            ]
        }
        
        # Set up subports
        subports = [
            {'port_id': 'subport-1', 'segmentation_id': 200},
            {'port_id': 'subport-2', 'segmentation_id': 300}
        ]
        
        # Mock parent port
        self.mock_core_plugin.get_port.return_value = {
            'id': 'parent-port-1',
            'network_id': 'network-1'
        }
        
        # Mock _configure_trunk_port
        mock_configure = mock.patch.object(self.driver, '_configure_trunk_port')
        configure_patch = mock_configure.start()
        
        # Call add_subports_on_trunk
        self.driver.add_subports_on_trunk(binding_profile, 'port-1', subports)
        
        # Verify _configure_trunk_port was called with correct parameters
        configure_patch.assert_called_once_with(
            '78:45:58:ab:cd:ef', '1', 
            {'id': 'parent-port-1', 'network_id': 'network-1'}, 
            subports
        )
        
        mock_configure.stop()
        
    def test_del_subports_from_trunk(self):
        """Test removing subports from trunk port."""
        # Set up binding profile
        binding_profile = {
            'parent_port_id': 'parent-port-1',
            'local_link_information': [
                {
                    'switch_id': '78:45:58:ab:cd:ef',
                    'port_id': '1'
                }
            ]
        }
        
        # Set up subports to remove
        subports = [
            {'port_id': 'subport-1', 'segmentation_id': 200}
        ]
        
        # Mock parent port
        self.mock_core_plugin.get_port.return_value = {
            'id': 'parent-port-1',
            'network_id': 'network-1'
        }
        
        # Mock _get_subports_for_trunk to return all subports
        mock_get_subports = mock.patch.object(
            self.driver, '_get_subports_for_trunk',
            return_value=[
                {'port_id': 'subport-1', 'segmentation_id': 200},
                {'port_id': 'subport-2', 'segmentation_id': 300}
            ]
        )
        get_subports_patch = mock_get_subports.start()
        
        # Mock _configure_trunk_port
        mock_configure = mock.patch.object(self.driver, '_configure_trunk_port')
        configure_patch = mock_configure.start()
        
        # Call del_subports_on_trunk
        self.driver.del_subports_on_trunk(binding_profile, 'port-1', subports)
        
        # Verify _configure_trunk_port was called with correct parameters (only remaining subport)
        configure_patch.assert_called_once()
        args = configure_patch.call_args[0]
        self.assertEqual(args[0], '78:45:58:ab:cd:ef')
        self.assertEqual(args[1], '1')
        self.assertEqual(args[3], [{'port_id': 'subport-2', 'segmentation_id': 300}])
        
        mock_get_subports.stop()
        mock_configure.stop()