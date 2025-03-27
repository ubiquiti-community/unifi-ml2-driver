# Copyright 2015 Mirantis, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""
UniFi ML2 Driver for OpenStack Neutron

This driver implements network operations for UniFi switches
managed through a UniFi Network controller.
"""

import asyncio
from contextlib import contextmanager
import time

from neutron.db import provisioning_blocks
from neutron_lib.api.definitions import portbindings
from neutron_lib import constants as n_const
from neutron_lib.callbacks import resources
from neutron_lib.plugins.ml2 import api
from oslo_config import cfg
from oslo_log import log as logging

from unifi_ml2_driver import exceptions
from unifi_ml2_driver.unifi_api import get_unifi_api
from unifi_ml2_driver import trunk_driver

LOG = logging.getLogger(__name__)
CONF = cfg.CONF

# Additional UniFi specific configuration options
unifi_opts = [
    cfg.StrOpt('controller',
               help='URL of the UniFi Network controller'),
    cfg.StrOpt('username',
               help='Username for UniFi controller authentication'),
    cfg.StrOpt('password',
               secret=True,
               help='Password for UniFi controller authentication'),
    cfg.StrOpt('site',
               default='default',
               help='UniFi site name to manage'),
    cfg.BoolOpt('verify_ssl',
                default=True,
                help='Verify SSL certificates for UniFi controller connection'),
    cfg.StrOpt('port_name_format',
               default='openstack-port-{port_id}',
               help='Format string for port names. Available variables: '
                    '{port_id}, {network_id}, {segmentation_id}'),
    cfg.StrOpt('port_description_format',
               default='OpenStack port {port_id}',
               help='Format string for port descriptions'),
    cfg.IntOpt('api_retry_count',
               default=3,
               help='Number of times to retry API calls'),
    cfg.IntOpt('port_setup_retry_count',
               default=3,
               help='Number of times to retry port setup operations'),
    cfg.IntOpt('port_setup_retry_interval',
               default=1,
               help='Interval between port setup retries in seconds'),
    cfg.BoolOpt('sync_startup',
                default=True,
                help='Sync networks and ports on startup'),
    cfg.BoolOpt('use_all_networks_for_trunk',
                default=True,
                help='Use "All Networks" option for trunk ports instead of '
                     'explicitly listing tagged VLANs'),
    cfg.BoolOpt('enable_port_security',
                default=True,
                help='Enable port security features like MAC address filtering'),
    cfg.BoolOpt('enable_qos',
                default=False,
                help='Enable QoS features on ports'),
    cfg.IntOpt('default_bandwidth_limit',
                default=0,
                help='Default bandwidth limit in Kbps (0 means unlimited)'),
    cfg.BoolOpt('enable_storm_control',
                default=False,
                help='Enable storm control on ports'),
    cfg.IntOpt('storm_control_broadcasting',
                default=0,
                help='Storm control threshold for broadcast traffic (0-100%)'),
    cfg.IntOpt('storm_control_multicasting',
                default=0,
                help='Storm control threshold for multicast traffic (0-100%)'),
    cfg.IntOpt('storm_control_unknown_unicast',
                default=0,
                help='Storm control threshold for unknown unicast traffic (0-100%)'),
    cfg.BoolOpt('monitor_port_state',
                default=True,
                help='Monitor port state and update OpenStack port status'),
    cfg.IntOpt('monitor_interval',
                default=60,
                help='Interval in seconds to monitor port state'),
]

CONF.register_opts(unifi_opts, "unifi")


class UnifiMechDriver(api.MechanismDriver):
    """UniFi Mechanism Driver for ML2 plugin.

    This driver manages VLANs and port configurations on UniFi switches
    through a UniFi Network controller.
    """

    def __init__(self):
        self.controller = None
        self.switches = {}
        self.port_mappings = {}
        self.vif_details = {portbindings.VIF_DETAILS_CONNECTIVITY:
                            portbindings.CONNECTIVITY_L2}
        self.trunk_driver = None
        self._controllers = {}

    @property
    def connectivity(self):
        return portbindings.CONNECTIVITY_L2

    def initialize(self):
        """Perform driver initialization.

        Called after all drivers have been loaded and the database has
        been initialized. No abstract methods defined below will be
        called prior to this method being called.
        """
        LOG.info("Initializing UniFi ML2 driver")

        # Initialize trunk driver if available
        self.trunk_driver = trunk_driver.UnifiTrunkDriver.create(self)

        # Verify we have required configuration
        if not CONF.unifi.controller:
            LOG.warning("UniFi controller URL not configured. Driver disabled.")
            return

        if not CONF.unifi.username or not CONF.unifi.password:
            LOG.warning("UniFi credentials not configured. Driver disabled.")
            return

        # Test connection to controller
        try:
            with self._get_controller() as controller:
                LOG.info("Successfully connected to UniFi controller at %s",
                         CONF.unifi.controller)
                
                # Import threading here to avoid circular imports
                import threading
                
                # Start port monitoring if enabled
                if CONF.unifi.monitor_port_state:
                    self.start_port_monitor()
                
                # Sync networks if needed
                if CONF.unifi.sync_startup:
                    self._sync_networks()
        except Exception as e:
            LOG.error("Failed to connect to UniFi controller: %s", e)
            # Don't raise - let the driver remain initialized but inactive

    def _get_controller(self):
        """Get or create a UniFi controller connection.
        
        Returns:
            A context manager that yields a controller client
        """
        if CONF.unifi.controller not in self._controllers:
            # Empty dict for config since we're using CONF directly in get_unifi_api
            self._controllers[CONF.unifi.controller] = {}
        
        return self._get_api(CONF.unifi.controller)

    @contextmanager
    def _get_api(self, controller_id):
        """Get a UniFi API client using the async helper.
        
        Args:
            controller_id: Controller identifier (usually URL)
            
        Returns:
            A UniFi controller client
        """
        config = self._controllers[controller_id]
        
        # Set up event loop for async calls
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            controller = loop.run_until_complete(get_unifi_api(config))
            yield controller
        finally:
            # Clean up
            loop.close()

    def _sync_networks(self):
        """Sync networks from OpenStack to UniFi controller."""
        LOG.info("Syncing networks to UniFi controller")
        # Implementation would require access to the Neutron DB
        # Skipped for this example, but would involve:
        # 1. Getting all networks with segmentation_id (VLAN ID)
        # 2. Ensuring those VLANs exist in the UniFi controller
        pass

    def create_network_precommit(self, context):
        """Allocate resources for a new network.

        :param context: NetworkContext instance describing the new
        network.

        Create a new network, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        # Nothing to do for network precommit
        pass

    def create_network_postcommit(self, context):
        """Create a network.

        :param context: NetworkContext instance describing the new
        network.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        network = context.current
        # Only handle networks with segmentation ID (VLANs)
        network_id = network['id']
        
        # Skip non-VLAN networks or external networks
        if network.get('provider:network_type') != 'vlan' or network.get('router:external'):
            return
            
        segmentation_id = network.get('provider:segmentation_id')
        if not segmentation_id:
            return
            
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Check if network exists
                networks = loop.run_until_complete(controller.sites.networks.update())
                network_exists = any(
                    net.vlan == segmentation_id for net in networks if hasattr(net, 'vlan')
                )
                
                if not network_exists:
                    # Create VLAN in UniFi controller
                    vlan_data = {
                        "name": f"OpenStack-{network_id}-VLAN{segmentation_id}",
                        "purpose": "corporate",
                        "vlan": segmentation_id,
                        "enabled": True
                    }
                    
                    loop.run_until_complete(
                        controller.sites.networks.async_create_network(vlan_data)
                    )
                    
                    LOG.info('Network %s (VLAN %s) has been created in UniFi controller',
                             network_id, segmentation_id)
                else:
                    LOG.debug('Network %s (VLAN %s) already exists in UniFi controller',
                             network_id, segmentation_id)
                    
        except Exception as e:
            LOG.error('Failed to create network %s (VLAN %s) in UniFi controller: %s',
                     network_id, segmentation_id, e)
            raise

    def update_network_precommit(self, context):
        """Update resources of a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Update values of a network, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_network_precommit is called for all changes to the
        network state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        # Nothing to do for network update precommit
        pass

    def update_network_postcommit(self, context):
        """Update a network.

        :param context: NetworkContext instance describing the new
        state of the network, as well as the original state prior
        to the update_network call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_network_postcommit is called for all changes to the
        network state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        # Check if segmentation_id has changed
        network = context.current
        original_network = context.original
        
        if (network.get('provider:network_type') != 'vlan' or 
                original_network.get('provider:network_type') != 'vlan'):
            return
            
        new_segmentation_id = network.get('provider:segmentation_id')
        old_segmentation_id = original_network.get('provider:segmentation_id')
        
        # If VLAN ID hasn't changed, nothing to do
        if new_segmentation_id == old_segmentation_id:
            return
            
        network_id = network['id']
        
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Find the network with the old VLAN ID
                networks = loop.run_until_complete(controller.sites.networks.update())
                old_network = next(
                    (net for net in networks 
                     if hasattr(net, 'vlan') and net.vlan == old_segmentation_id), 
                    None
                )
                
                if old_network:
                    # Delete old network
                    loop.run_until_complete(
                        controller.sites.networks.async_delete_network(old_network.id)
                    )
                
                # Create new network with updated VLAN ID
                vlan_data = {
                    "name": f"OpenStack-{network_id}-VLAN{new_segmentation_id}",
                    "purpose": "corporate",
                    "vlan": new_segmentation_id,
                    "enabled": True
                }
                
                loop.run_until_complete(
                    controller.sites.networks.async_create_network(vlan_data)
                )
                
                LOG.info('Network %s updated from VLAN %s to VLAN %s in UniFi controller',
                         network_id, old_segmentation_id, new_segmentation_id)
                
        except Exception as e:
            LOG.error('Failed to update network %s from VLAN %s to VLAN %s: %s',
                     network_id, old_segmentation_id, new_segmentation_id, e)
            raise

    def delete_network_precommit(self, context):
        """Delete resources for a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Delete network resources previously allocated by this
        mechanism driver for a network. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        # Nothing to do for network delete precommit
        pass

    def delete_network_postcommit(self, context):
        """Delete a network.

        :param context: NetworkContext instance describing the current
        state of the network, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        network = context.current
        
        # Only handle networks with segmentation ID (VLANs)
        if network.get('provider:network_type') != 'vlan':
            return
            
        segmentation_id = network.get('provider:segmentation_id')
        if not segmentation_id:
            return
            
        network_id = network['id']
        
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Find the network with this VLAN ID
                networks = loop.run_until_complete(controller.sites.networks.update())
                target_network = next(
                    (net for net in networks 
                     if hasattr(net, 'vlan') and net.vlan == segmentation_id), 
                    None
                )
                
                if target_network:
                    # Delete network in UniFi controller
                    loop.run_until_complete(
                        controller.sites.networks.async_delete_network(target_network.id)
                    )
                    LOG.info('Network %s (VLAN %s) has been deleted from UniFi controller',
                             network_id, segmentation_id)
                else:
                    LOG.debug('Network %s (VLAN %s) not found in UniFi controller',
                             network_id, segmentation_id)
                    
        except Exception as e:
            # Log but don't raise to prevent network deletion from failing
            LOG.error('Failed to delete network %s (VLAN %s) from UniFi controller: %s',
                     network_id, segmentation_id, e)

    def create_subnet_precommit(self, context):
        """Allocate resources for a new subnet.

        :param context: SubnetContext instance describing the new
            subnet.

        rt = context.current
        device_id = port['device_id']
        device_owner = port['device_owner']
        Create a new subnet, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        pass

    def create_subnet_postcommit(self, context):
        """Create a subnet.

        :param context: SubnetContext instance describing the new
            subnet.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.
        """
        pass

    def update_subnet_precommit(self, context):
        """Update resources of a subnet.

        :param context: SubnetContext instance describing the new
            state of the subnet, as well as the original state prior
            to the update_subnet call.

        Update values of a subnet, updating the associated resources
        in the database. Called inside transaction context on session.
        Raising an exception will result in rollback of the
        transaction.

        update_subnet_precommit is called for all changes to the
        subnet state. It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def update_subnet_postcommit(self, context):
        """Update a subnet.

        :param context: SubnetContext instance describing the new
            state of the subnet, as well as the original state prior
            to the update_subnet call.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_subnet_postcommit is called for all changes to the
        subnet state.  It is up to the mechanism driver to ignore
        state or state changes that it does not know or care about.
        """
        pass

    def delete_subnet_precommit(self, context):
        """Delete resources for a subnet.

        :param context: SubnetContext instance describing the current
            state of the subnet, prior to the call to delete it.

        Delete subnet resources previously allocated by this
        mechanism driver for a subnet. Called inside transaction
        context on session. Runtime errors are not expected, but
        raising an exception will result in rollback of the
        transaction.
        """
        pass

    def delete_subnet_postcommit(self, context):
        """Delete a subnet.

        :param context: SubnetContext instance describing the current
            state of the subnet, prior to the call to delete it.

        Called after the transaction commits. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        pass

    def create_port_precommit(self, context):
        """Allocate resources for a new port.

        :param context: PortContext instance describing the port.

        Create a new port, allocating resources as necessary in the
        database. Called inside transaction context on session. Call
        cannot block.  Raising an exception will result in a rollback
        of the current transaction.
        """
        # Nothing to do for port precommit
        pass

    def create_port_postcommit(self, context):
        """Create a port.

        :param context: PortContext instance describing the port.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        result in the deletion of the resource.
        """
        port = context.current
        network = context.network.current
        segments = context.segments_to_bind
        
        # Skip ports that don't have binding:profile
        if not port.get('binding:profile'):
            return
            
        # Only process ports with local_link_information
        local_link_info = port['binding:profile'].get('local_link_information')
        if not local_link_info or not isinstance(local_link_info, list):
            return
            
        # Only handle networks with segmentation ID (VLANs)
        if network.get('provider:network_type') != 'vlan':
            return
            
        segmentation_id = network.get('provider:segmentation_id')
        if not segmentation_id:
            return
            
        port_id = port['id']
        
        # Process each link (switch port)
        for link in local_link_info:
            switch_id = link.get('switch_id')
            port_id_on_switch = link.get('port_id')
            
            if not switch_id or not port_id_on_switch:
                continue
                
            # Try to find and configure the switch port
            try:
                self._configure_port(switch_id, port_id_on_switch, 
                                    port_id, segmentation_id)
                
                # Store port mapping for later use
                self.port_mappings[port_id] = {
                    'switch_id': switch_id,
                    'port_id': port_id_on_switch,
                    'vlan_id': segmentation_id
                }
                
            except Exception as e:
                LOG.error('Failed to configure port %s on switch %s: %s',
                         port_id_on_switch, switch_id, e)
                raise

    def update_port_precommit(self, context):
        """Update resources of a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called inside transaction context on session to complete a
        port update as defined by this mechanism driver. Raising an
        exception will result in rollback of the transaction.

        update_port_precommit is called for all port updates. It is up
        to the mechanism driver to ignore state or state changes that
        it does not know or care about.
        """
        # Nothing to do for port update precommit
        pass

    def update_port_postcommit(self, context):
        """Update a port.

        :param context: PortContext instance describing the new
        state of the port, as well as the original state prior
        to the update_port call.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Raising an exception will
        cause the deletion of the resource.

        update_port_postcommit is called for all port updates. It is up
        to the mechanism driver to ignore state or state changes that
        it does not know or care about.
        """
        port = context.current
        original_port = context.original
        network = context.network.current
        
        # Skip ports that don't have binding:profile
        if not port.get('binding:profile'):
            return
            
        # Only process ports with local_link_information
        local_link_info = port['binding:profile'].get('local_link_information')
        if not local_link_info or not isinstance(local_link_info, list):
            return
            
        # Skip if network hasn't changed
        if port['network_id'] == original_port['network_id']:
            # Check if binding profile has changed
            old_link_info = original_port.get('binding:profile', {}).get('local_link_information', [])
            if local_link_info == old_link_info:
                return
            
        # Only handle networks with segmentation ID (VLANs)
        if network.get('provider:network_type') != 'vlan':
            return
            
        segmentation_id = network.get('provider:segmentation_id')
        if not segmentation_id:
            return
            
        port_id = port['id']
        
        # Process each link (switch port)
        for link in local_link_info:
            switch_id = link.get('switch_id')
            port_id_on_switch = link.get('port_id')
            
            if not switch_id or not port_id_on_switch:
                continue
                
            # Try to find and configure the switch port
            try:
                # Check if we need to unconfigure the old port
                old_mapping = self.port_mappings.get(port_id)
                if old_mapping and (old_mapping['switch_id'] != switch_id or 
                                    old_mapping['port_id'] != port_id_on_switch):
                    self._unconfigure_port(old_mapping['switch_id'], 
                                         old_mapping['port_id'])
                
                self._configure_port(switch_id, port_id_on_switch, 
                                   port_id, segmentation_id)
                
                # Update port mapping
                self.port_mappings[port_id] = {
                    'switch_id': switch_id,
                    'port_id': port_id_on_switch,
                    'vlan_id': segmentation_id
                }
                
            except Exception as e:
                LOG.error('Failed to update port %s on switch %s: %s',
                         port_id_on_switch, switch_id, e)
                raise

    def delete_port_precommit(self, context):
        """Delete resources of a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called inside transaction context on session. Call cannot
        block.  Raising an exception will result in rollback of the
        transaction.
        """
        # Nothing to do for port delete precommit
        pass

    def delete_port_postcommit(self, context):
        """Delete a port.

        :param context: PortContext instance describing the current
        state of the port, prior to the call to delete it.

        Called after the transaction completes. Call can block, though
        will block the entire process so care should be taken to not
        drastically affect performance. Runtime errors are not
        expected, and will not prevent the resource from being
        deleted.
        """
        port = context.current
        port_id = port['id']
        
        # Check if we have a mapping for this port
        mapping = self.port_mappings.get(port_id)
        if not mapping:
            return
            
        # Try to unconfigure the port
        try:
            self._unconfigure_port(mapping['switch_id'], mapping['port_id'])
            # Remove mapping
            del self.port_mappings[port_id]
        except Exception as e:
            # Log but don't raise to avoid preventing port deletion
            LOG.error('Failed to unconfigure port %s on switch %s: %s',
                     mapping['port_id'], mapping['switch_id'], e)

    def bind_port(self, context):
        """Attempt to bind a port.

        :param context: PortContext instance describing the port

        This method is called outside any transaction to attempt to
        establish a port binding using this mechanism driver. Bindings
        may be created at each of multiple levels of a hierarchical
        network, and are established from the top level downward. At
        each level, the mechanism driver determines whether it can
        bind to any segment in the segments_to_bind for a given level.
        If at least one binding is successful, it continues up the
        hierarchy, first binding to the top level segment before
        proceeding downward to the next level.

        """
        # Check if this is a port we should try to bind
        port = context.current
        binding_profile = port.get('binding:profile', {})
        local_link_info = binding_profile.get('local_link_information')
        
        # If no local_link_information, we can't bind
        if not local_link_info:
            return
            
        # Get segments to try binding
        segments_to_bind = context.segments_to_bind
        if not segments_to_bind:
            LOG.debug("No segments to bind for port %s", port['id'])
            return
            
        for segment in segments_to_bind:
            # We only support binding VLAN segments
            if segment[api.NETWORK_TYPE] != 'vlan':
                continue
                
            # Check if we can find this switch
            for link in local_link_info:
                switch_id = link.get('switch_id')
                port_id_on_switch = link.get('port_id')
                
                # Verify we can handle this switch
                if not self._is_switch_supported(switch_id):
                    continue
                    
                # We can bind this segment
                context.set_binding(
                    segment[api.ID],
                    portbindings.VIF_TYPE_OTHER,
                    self.vif_details,
                    status=n_const.PORT_STATUS_ACTIVE
                )
                
                LOG.debug("Bound port %s to segment %s on switch %s, port %s",
                         port['id'], segment[api.ID], switch_id, port_id_on_switch)
                return True
                
        return False
                
    def _is_switch_supported(self, switch_id):
        """Check if a switch is supported by this driver.
        
        Args:
            switch_id: The MAC address of the switch
            
        Returns:
            True if the switch is supported
        """
        # Try to find this switch in the UniFi controller
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Fetch devices and look for this switch
                devices = loop.run_until_complete(controller.devices.update())
                for device in devices:
                    if hasattr(device, 'mac') and device.mac == switch_id:
                        if hasattr(device, 'type') and device.type == 'usw':
                            # Found a UniFi switch with this ID
                            return True
                            
                return False
                
        except Exception as e:
            LOG.error("Failed to check if switch %s is supported: %s", switch_id, e)
            return False

    def _configure_port(self, switch_id, port_id, neutron_port_id, vlan_id):
        """Configure a port with the specified VLAN.
        
        Args:
            switch_id: The MAC address of the switch
            port_id: The port ID on the switch
            neutron_port_id: The Neutron port ID
            vlan_id: The VLAN ID to set
            
        Returns:
            True if successful
        """
        LOG.debug("Configuring port %s on switch %s with VLAN %s",
                 port_id, switch_id, vlan_id)
                 
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Find this switch
                devices = loop.run_until_complete(controller.devices.update())
                switch = next((d for d in devices if hasattr(d, 'mac') and d.mac == switch_id), None)
                
                if not switch:
                    raise exceptions.CannotConnect(
                        f"Switch {switch_id} not found in UniFi controller")
                
                # Get port_idx from port_id (could be a name or number)
                try:
                    port_idx = int(port_id)
                except ValueError:
                    # Try to find port by name
                    port = next((p for p in switch.port_table 
                               if hasattr(p, 'name') and p.name == port_id), None)
                    if port:
                        port_idx = port.port_idx
                    else:
                        raise exceptions.UnifiException(
                            f"Port {port_id} not found on switch {switch_id}")
                
                # Set port configuration
                port_conf = {
                    "mac": switch_id,
                    "port_idx": port_idx,
                    "name": CONF.unifi.port_name_format.format(
                        port_id=neutron_port_id,
                        network_id=vlan_id,  # Using VLAN ID as network ID
                        segmentation_id=vlan_id
                    ),
                    "port_vlan_enabled": True,
                    "port_vlan": vlan_id
                }
                
                # Add QoS configuration if enabled
                if CONF.unifi.enable_qos:
                    port_conf["tx_rate_limit_enabled"] = True
                    port_conf["tx_rate_limit_kbps_cfg"] = CONF.unifi.default_bandwidth_limit
                    
                # Add storm control if enabled
                if CONF.unifi.enable_storm_control:
                    if CONF.unifi.storm_control_broadcasting > 0:
                        port_conf["stormctrl_bcast_enabled"] = True
                        port_conf["stormctrl_bcast_rate"] = CONF.unifi.storm_control_broadcasting
                    if CONF.unifi.storm_control_multicasting > 0:
                        port_conf["stormctrl_mcast_enabled"] = True
                        port_conf["stormctrl_mcast_rate"] = CONF.unifi.storm_control_multicasting
                    if CONF.unifi.storm_control_unknown_unicast > 0:
                        port_conf["stormctrl_ucast_enabled"] = True
                        port_conf["stormctrl_ucast_rate"] = CONF.unifi.storm_control_unknown_unicast
                
                # Add port security if enabled
                if CONF.unifi.enable_port_security:
                    port_conf["dot1x_ctrl"] = "force_authorized"
                    port_conf["stp_port_fast"] = True
                    port_conf["stp_bpdu_guard"] = True
                    port_conf["stp_loop_guard"] = True
                
                # Send configuration to controller
                for attempt in range(CONF.unifi.port_setup_retry_count):
                    try:
                        loop.run_until_complete(
                            controller.devices.async_set_port_conf(port_conf)
                        )
                        LOG.info("Configured port %s on switch %s with VLAN %s",
                                port_id, switch_id, vlan_id)
                        return True
                    except Exception as e:
                        if attempt < CONF.unifi.port_setup_retry_count - 1:
                            LOG.warning("Failed to configure port, retrying: %s", e)
                            time.sleep(CONF.unifi.port_setup_retry_interval)
                        else:
                            raise
                
        except Exception as e:
            LOG.error("Failed to configure port %s on switch %s: %s",
                     port_id, switch_id, e)
            raise exceptions.UnifiNetmikoConfigError()

    def _unconfigure_port(self, switch_id, port_id):
        """Reset a port to default configuration.
        
        Args:
            switch_id: The MAC address of the switch
            port_id: The port ID on the switch
            
        Returns:
            True if successful
        """
        LOG.debug("Unconfiguring port %s on switch %s", port_id, switch_id)
                 
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Find this switch
                devices = loop.run_until_complete(controller.devices.update())
                switch = next((d for d in devices if hasattr(d, 'mac') and d.mac == switch_id), None)
                
                if not switch:
                    raise exceptions.CannotConnect(
                        f"Switch {switch_id} not found in UniFi controller")
                
                # Get port_idx from port_id (could be a name or number)
                try:
                    port_idx = int(port_id)
                except ValueError:
                    # Try to find port by name
                    port = next((p for p in switch.port_table 
                               if hasattr(p, 'name') and p.name == port_id), None)
                    if port:
                        port_idx = port.port_idx
                    else:
                        raise exceptions.UnifiException(
                            f"Port {port_id} not found on switch {switch_id}")
                
                # Reset port configuration
                port_conf = {
                    "mac": switch_id,
                    "port_idx": port_idx,
                    "name": f"Port {port_idx}",  # Reset to default name
                    "port_vlan_enabled": False,  # Disable VLAN
                    "tagged_vlan": []  # Clear any tagged VLANs
                }
                
                # Send configuration to controller
                loop.run_until_complete(
                    controller.devices.async_set_port_conf(port_conf)
                )
                
                LOG.info("Reset port %s on switch %s to default configuration",
                        port_id, switch_id)
                return True
                
        except Exception as e:
            LOG.error("Failed to reset port %s on switch %s: %s",
                     port_id, switch_id, e)
            # Log but don't raise to avoid preventing port deletion
            return False

    def subports_added(self, context, port, subports):
        """Tell the agent about new subports to add.

        :param context: Request context
        :param port: Port dictionary
        :subports: List with subports
        """

        # set the correct state on port in the case where it has subports.
        # If the parent port has been deleted then that delete will handle
        # removing the trunked vlans on the switch using the mac
        if not port:
            LOG.debug('Discarding attempt to ensure subports on a port'
                      'that has been deleted')
            return

        if not self._is_port_supported(port):
            return

        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')

        if not local_link_information:
            return

        for link in local_link_information:
            port_id = link.get('port_id')
            switch_info = link.get('switch_info')
            switch_id = link.get('switch_id')
            switch = device_utils.get_switch_device(
                self.switches, switch_info=switch_info,
                ngs_mac_address=switch_id)

            switch.add_subports_on_trunk(
                binding_profile, port_id, subports)

        core_plugin = directory.get_plugin()

        for subport in subports:
            subport_obj = core_plugin.get_port(context,
                                               subport['port_id'])
            if subport_obj['status'] != const.PORT_STATUS_ACTIVE:
                core_plugin.update_port_status(
                    context, subport["port_id"],
                    const.PORT_STATUS_ACTIVE)

    def subports_deleted(self, context, port, subports):
        """Tell the agent about subports to delete.

        :param context: Request context
        :param port: Port dictionary
        :subports: List with subports
        """

        if not port:
            LOG.debug('Discarding attempt to ensure subports on a port'
                      'that has been deleted')
            return

        if not self._is_port_supported(port):
            return

        binding_profile = port['binding:profile']
        local_link_information = binding_profile.get('local_link_information')

        if not local_link_information:
            return

        for link in local_link_information:
            port_id = link.get('port_id')
            switch_info = link.get('switch_info')
            switch_id = link.get('switch_id')
            switch = device_utils.get_switch_device(
                self.switches, switch_info=switch_info,
                ngs_mac_address=switch_id)

            switch.del_subports_on_trunk(
                binding_profile, port_id, subports)

    def _is_port_supported(self, port):
        """Check if a port is supported by this driver.
        
        Args:
            port: The neutron port object
            
        Returns:
            True if the port is supported by this driver
        """
        # Check if the port has binding information
        if not port.get('binding:profile'):
            return False
            
        # Check if it has local link information
        local_link_info = port['binding:profile'].get('local_link_information')
        if not local_link_info or not isinstance(local_link_info, list):
            return False
            
        # At least one switch must be supported
        for link in local_link_info:
            switch_id = link.get('switch_id')
            if self._is_switch_supported(switch_id):
                return True
                
        return False
        
    def _configure_trunk_port(self, switch_id, port_id, port_obj, subports=None):
        """Configure a trunk port with tagged VLANs.
        
        Args:
            switch_id: The MAC address of the switch
            port_id: The port ID on the switch
            port_obj: The neutron port object for the parent port
            subports: List of subport objects or None
            
        Returns:
            True if successful
        """
        LOG.debug("Configuring trunk port %s on switch %s with subports %s",
                 port_id, switch_id, subports)
        
        # Get the native VLAN of the trunk port
        network_id = port_obj.get('network_id')
        core_plugin = directory.get_plugin()
        context = n_context.get_admin_context()
        network = core_plugin.get_network(context, network_id)
        native_vlan = network.get('provider:segmentation_id', 1)
        
        # Get VLANs from subports
        tagged_vlans = []
        if subports:
            for subport in subports:
                segmentation_id = subport.get('segmentation_id')
                if segmentation_id:
                    tagged_vlans.append(segmentation_id)
        
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Find this switch
                devices = loop.run_until_complete(controller.devices.update())
                switch = next((d for d in devices if hasattr(d, 'mac') and d.mac == switch_id), None)
                
                if not switch:
                    raise exceptions.CannotConnect(
                        f"Switch {switch_id} not found in UniFi controller")
                
                # Get port_idx from port_id
                try:
                    port_idx = int(port_id)
                except ValueError:
                    # Try to find port by name
                    port = next((p for p in switch.port_table 
                               if hasattr(p, 'name') and p.name == port_id), None)
                    if port:
                        port_idx = port.port_idx
                    else:
                        raise exceptions.UnifiException(
                            f"Port {port_id} not found on switch {switch_id}")
                
                # Set trunk port configuration
                port_conf = {
                    "mac": switch_id,
                    "port_idx": port_idx,
                    "name": CONF.unifi.port_name_format.format(
                        port_id=port_obj['id'],
                        network_id=network_id,
                        segmentation_id=native_vlan
                    ),
                    # Set to trunk mode
                    "port_vlan_enabled": True,    # Native VLAN
                    "port_vlan": native_vlan      # Native VLAN ID
                }
                
                # Add tagged VLANs
                if tagged_vlans:
                    # Check if we should use "All Networks" mode
                    if CONF.unifi.use_all_networks_for_trunk:
                        port_conf["vlan_mode"] = "all"  # All VLANs are allowed
                    else:
                        port_conf["vlan_mode"] = "tagged"
                        port_conf["tagged_vlan"] = tagged_vlans
                        
                # Add QoS configuration if enabled
                if CONF.unifi.enable_qos:
                    port_conf["tx_rate_limit_enabled"] = True
                    port_conf["tx_rate_limit_kbps_cfg"] = CONF.unifi.default_bandwidth_limit
                
                # Add port security if enabled (typically less strict for trunk ports)
                if CONF.unifi.enable_port_security:
                    port_conf["stp_port_fast"] = False  # Disable port fast on trunk ports
                    port_conf["stp_bpdu_guard"] = False # Disable BPDU guard on trunk ports
                
                # Send configuration to controller
                for attempt in range(CONF.unifi.port_setup_retry_count):
                    try:
                        loop.run_until_complete(
                            controller.devices.async_set_port_conf(port_conf)
                        )
                        LOG.info("Configured trunk port %s on switch %s with native VLAN %s and tagged VLANs %s",
                                port_id, switch_id, native_vlan, tagged_vlans)
                        return True
                    except Exception as e:
                        if attempt < CONF.unifi.port_setup_retry_count - 1:
                            LOG.warning("Failed to configure trunk port, retrying: %s", e)
                            time.sleep(CONF.unifi.port_setup_retry_interval)
                        else:
                            raise
                
        except Exception as e:
            LOG.error("Failed to configure trunk port %s on switch %s: %s",
                     port_id, switch_id, e)
            raise exceptions.UnifiNetmikoConfigError()
            
    def add_subports_on_trunk(self, binding_profile, port_id, subports):
        """Add subports to a trunk port.
        
        Args:
            binding_profile: Port binding profile
            port_id: The port ID on the switch
            subports: List of subport objects
            
        Returns:
            None
        """
        LOG.debug("Adding subports %s to trunk port %s", subports, port_id)
        
        # Get the switch ID from binding profile
        local_link_info = binding_profile.get('local_link_information', [])
        for link in local_link_info:
            switch_id = link.get('switch_id')
            switch_port_id = link.get('port_id')
            
            if not switch_id or not switch_port_id:
                continue
                
            try:
                # Get the port object for the trunk parent port
                context = n_context.get_admin_context()
                core_plugin = directory.get_plugin()
                
                # Extract the parent port ID from the binding profile
                parent_port_id = binding_profile.get('parent_port_id')
                if not parent_port_id:
                    LOG.warning("No parent_port_id in binding profile")
                    continue
                    
                parent_port = core_plugin.get_port(context, parent_port_id)
                
                # Configure the trunk port with the new subports
                self._configure_trunk_port(switch_id, switch_port_id, parent_port, subports)
                
            except Exception as e:
                LOG.error("Failed to add subports to trunk port %s on switch %s: %s",
                         switch_port_id, switch_id, e)
                
    def del_subports_on_trunk(self, binding_profile, port_id, subports):
        """Remove subports from a trunk port.
        
        Args:
            binding_profile: Port binding profile
            port_id: The port ID on the switch
            subports: List of subport objects to remove
            
        Returns:
            None
        """
        LOG.debug("Removing subports %s from trunk port %s", subports, port_id)
        
        # Get the switch ID from binding profile
        local_link_info = binding_profile.get('local_link_information', [])
        for link in local_link_info:
            switch_id = link.get('switch_id')
            switch_port_id = link.get('port_id')
            
            if not switch_id or not switch_port_id:
                continue
                
            try:
                # Get the port object for the trunk parent port
                context = n_context.get_admin_context()
                core_plugin = directory.get_plugin()
                
                # Extract the parent port ID from the binding profile
                parent_port_id = binding_profile.get('parent_port_id')
                if not parent_port_id:
                    LOG.warning("No parent_port_id in binding profile")
                    continue
                    
                parent_port = core_plugin.get_port(context, parent_port_id)
                
                # Get all remaining subports for this trunk
                all_subports = self._get_subports_for_trunk(context, parent_port_id)
                
                # Remove the subports we're deleting
                subport_ids_to_remove = [s['port_id'] for s in subports]
                remaining_subports = [s for s in all_subports if s['port_id'] not in subport_ids_to_remove]
                
                # Reconfigure the trunk port with remaining subports
                self._configure_trunk_port(switch_id, switch_port_id, parent_port, remaining_subports)
                
            except Exception as e:
                LOG.error("Failed to remove subports from trunk port %s on switch %s: %s",
                         switch_port_id, switch_id, e)
                
    def _get_subports_for_trunk(self, context, parent_port_id):
        """Get all subports for a trunk port.
        
        Args:
            context: Neutron context
            parent_port_id: Parent port ID
            
        Returns:
            List of subport objects
        """
        # Access the trunk plugin
        trunk_plugin = directory.get_plugin('trunk')
        if not trunk_plugin:
            LOG.warning("Trunk plugin not available")
            return []
            
        # Get the trunk for this parent port
        filters = {'port_id': [parent_port_id]}
        trunks = trunk_plugin.get_trunks(context, filters=filters)
        
        if not trunks:
            return []
            
        # Return the subports for this trunk
        trunk = trunks[0]
        return trunk.get('sub_ports', [])

    def start_port_monitor(self):
        """Start a periodic task to monitor port state on switches."""
        if not CONF.unifi.monitor_port_state:
            LOG.debug("Port monitoring is disabled")
            return
        
        LOG.info("Starting port monitor thread with interval %d seconds",
                CONF.unifi.monitor_interval)
        
        # Start monitor thread
        self._monitor_thread = threading.Thread(
            target=self._port_monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
    
    def _port_monitor_loop(self):
        """Monitor ports in a loop and update their status."""
        while True:
            try:
                self._check_port_status()
            except Exception as e:
                LOG.error("Error in port monitor: %s", e)
                
            time.sleep(CONF.unifi.monitor_interval)
                
    def _check_port_status(self):
        """Check the status of all ports and update them if needed."""
        if not self.port_mappings:
            return
            
        LOG.debug("Checking status of %d ports", len(self.port_mappings))
        
        try:
            with self._get_controller() as controller:
                loop = asyncio.get_event_loop()
                
                # Fetch devices and their port status
                devices = loop.run_until_complete(controller.devices.update())
                
                # Dictionary to keep track of port status by switch + port_id
                port_status = {}
                
                # Create a mapping of switch MAC to device object
                switch_devices = {
                    d.mac: d for d in devices 
                    if hasattr(d, 'mac') and hasattr(d, 'type') and d.type == 'usw'
                }
                
                # Check each port in our mappings
                for port_id, mapping in self.port_mappings.items():
                    switch_id = mapping['switch_id']
                    port_id_on_switch = mapping['port_id']
                    
                    # Find this switch
                    switch = switch_devices.get(switch_id)
                    if not switch:
                        LOG.warning("Switch %s not found in controller", switch_id)
                        continue
                        
                    # Find this port on the switch
                    try:
                        port_idx = int(port_id_on_switch)
                    except ValueError:
                        # Try to find port by name
                        port = next((p for p in switch.port_table 
                                  if hasattr(p, 'name') and p.name == port_id_on_switch), None)
                        if port:
                            port_idx = port.port_idx
                        else:
                            LOG.warning("Port %s not found on switch %s",
                                       port_id_on_switch, switch_id)
                            continue
                    
                    # Find port status in port_table
                    port = next((p for p in switch.port_table 
                              if hasattr(p, 'port_idx') and p.port_idx == port_idx), None)
                    
                    if not port:
                        LOG.warning("Port %s not found in port_table for switch %s", 
                                   port_idx, switch_id)
                        continue
                        
                    # Check port status
                    is_up = False
                    if hasattr(port, 'up'):
                        is_up = port.up
                    elif hasattr(port, 'port_up'):
                        is_up = port.port_up
                        
                    # Map to Neutron port status
                    status = n_const.PORT_STATUS_ACTIVE if is_up else n_const.PORT_STATUS_DOWN
                    
                    # Store port status
                    port_status[port_id] = status
                
                # Update port status in Neutron if needed
                self._update_port_status_in_neutron(port_status)
                
        except Exception as e:
            LOG.error("Failed to check port status: %s", e)
            
    def _update_port_status_in_neutron(self, port_status):
        """Update port status in Neutron database.
        
        Args:
            port_status: Dictionary of port_id -> status
        """
        if not port_status:
            return
            
        # Get the Neutron core plugin
        try:
            core_plugin = directory.get_plugin()
            if not core_plugin:
                LOG.error("Neutron core plugin not available")
                return
                
            # Create an admin context
            context = n_context.get_admin_context()
            
            # Update port status for each port
            for port_id, status in port_status.items():
                # Skip ports with unknown status
                if status is None:
                    continue
                    
                # Get current port status
                try:
                    port = core_plugin.get_port(context, port_id)
                    current_status = port.get('status')
                    
                    # Only update if status has changed
                    if current_status != status:
                        LOG.info("Updating port %s status from %s to %s",
                                port_id, current_status, status)
                        core_plugin.update_port_status(context, port_id, status)
                except Exception as e:
                    LOG.error("Failed to update port %s status: %s",
                             port_id, e)
                    
        except Exception as e:
            LOG.error("Failed to update port status in Neutron: %s", e)
