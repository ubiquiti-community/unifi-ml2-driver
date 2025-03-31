=============
Configuration
=============

In order to use this mechanism driver the Neutron configuration file needs to
be created/updated with the appropriate configuration information.

Switch configuration format::

    [unifi:<switch name>]
    device_type = <netmiko device type>
    ngs_mac_address = <switch mac address>
    ip = <IP address of switch>
    port = <ssh port>
    username = <credential username>
    password = <credential password>
    key_file = <ssh key file>
    secret = <enable secret>
    ngs_allowed_vlans = <comma-separated list of allowed vlans for switch>
    ngs_allowed_ports = <comma-separated list of allowed ports for switch>

    # If set ngs_port_default_vlan to default_vlan, switch's
    # interface will restore the default_vlan.
    ngs_port_default_vlan = <port default vlan>

The ``device_type`` entry is mandatory.  Most other configuration entries
are optional, see below.

The two new optional configuration parameters ``ngs_allowed_vlans`` and
``ngs_allowed_ports`` have been introduced to manage allowed VLANs and ports
on switches. If not set, all ports or VLANS are allowed.

.. note::

    Switch will be selected by local_link_connection/switch_info
    or ngs_mac_address. So, you can use the switch MAC address to identify
    switches if local_link_connection/switch_info is not set.

DNS Support
===========

The driver supports DNS resolution for the switch IP address. This is useful
when the switch IP address is not static and is resolved by a DNS server.

To enable the DNS integration feature in the UniFi ML2 Driver, add these configuration options to your Neutron configuration file:

    [unifi]
    # Enable DNS integration
    dns_integration_enabled = True

    # Base DNS domain for ports
    dns_domain = example.com

    # Optional: Format for DNS names
    # dns_domain_format = {dns_name}.{dns_domain}

    Once configured, set the dns_name attribute on Neutron ports to have DNS records automatically created. For example:

    openstack port create --network my-network --dns-name myserver server-port

This will create a DNS record with the name specified (e.g., myserver.example.com) pointing to the port's IP address.

Implementation Notes
This implementation:

Respects the existing UniFi ML2 Driver architecture and code patterns
Gracefully handles error cases
Uses async operations with the aiounifi library
Logs all operations for traceability
Only creates records when DNS names are specified
Supports both IPv4 (A records) and IPv6 (AAAA records)
The code is ready to be integrated into the UniFi ML2 Driver to provide DNS functionality alongside the existing networking features.



Examples
========

These example device configuration snippets are assumed to be part to a
specific file ``/etc/neutron/plugins/ml2/ml2_conf_unifi.ini``, but
they could also be added directly to ``/etc/neutron/plugins/ml2/ml2_conf.ini``.

Here is an example for the Cisco 300 series device::

    [unifi:sw-hostname]
    device_type = netmiko_cisco_s300
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Cisco IOS device::

    [unifi:sw-hostname]
    device_type = netmiko_cisco_ios
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the Cisco NX-OS device::

    [unifi:sw-hostname]
    device_type = netmiko_cisco_nxos
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Huawei VRPV3 or VRPV5 device::

    [unifi:sw-hostname]
    device_type = netmiko_huawei
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Huawei VRPV8 device::

    [unifi:sw-hostname]
    device_type = netmiko_huawei_vrpv8
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    port = 8222
    secret = secret
    ip = <switch mgmt ip address>

for the Arista EOS device::

    [unifi:arista-hostname]
    device_type = netmiko_arista_eos
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    key_file = /opt/data/arista_key

for the Dell Force10 device::

    [unifi:dell-hostname]
    device_type = netmiko_dell_force10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell OS10 device::

    [unifi:dell-hostname]
    device_type = netmiko_dell_os10
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

for the Dell PowerConnect device::

    [unifi:dell-hostname]
    device_type = netmiko_dell_powerconnect
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

    # You can set ngs_switchport_mode according to switchmode you have set on
    # the switch. The following options are supported: general, access. It
    # will default to access mode if left unset. In general mode, the port
    # be set to transmit untagged packets.
    ngs_switchport_mode = access

Dell PowerConnect devices have been seen to have issues with multiple
concurrent configuration sessions. See :ref:`synchronization` and
:ref:`batching` for details on how to limit the number of concurrent active
connections to each device.

for the Brocade FastIron (ICX) device::

    [unifi:hostname-for-fast-iron]
    device_type = netmiko_brocade_fastiron
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password

for the Ruijie device::

    [unifi:sw-hostname]
    device_type = netmiko_ruijie
    ngs_mac_address = <switch mac address>
    username = admin
    password = password
    secret = secret
    ip = <switch mgmt ip address>

for the HPE 5900 Series device::

    [unifi:sw-hostname]
    device_type = netmiko_hp_comware
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Juniper Junos OS device::

    [unifi:hostname-for-juniper]
    device_type = netmiko_juniper
    ip = <switch mgmt ip address>
    username = admin
    password = password
    ngs_commit_timeout = <optional commit timeout (seconds)>
    ngs_commit_interval = <optional commit interval (seconds)>

for a Cumulus Linux device::

    [unifi:hostname-for-cumulus]
    device_type = netmiko_cumulus
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for a Cumulus NVUE Linux device::

    [unifi:hostname-for-cumulus]
    device_type = netmiko_cumulus_nvue
    ip = <switch mgmt_ip address>
    username = admin
    password = password
    secret = secret
    ngs_mac_address = <switch mac address>

for the Nokia SRL series device::

    [unifi:sw-hostname]
    device_type = netmiko_nokia_srl
    username = admin
    password = password
    ip = <switch mgmt ip address>

for a Pluribus switch::

    [unifi:sw-hostname]
    device_type = netmiko_pluribus
    username = admin
    password = password
    ip = <switch mgmt ip address>

for an ArubaOS-CX switch::

    [unifi:aruba-hostname]
    device_type = netmiko_aruba_os
    username = admin
    password = password
    ip = <switch mgmt ip address>

for the Supermicro device::

    [unifi:sw-hostname]
    device_type = netmiko_supermicro_smis
    ngs_mac_address = <switch mac address>
    ip = <switch mgmt ip address>
    username = admin
    password = password
    secret = secret

General configuration
=====================

Additionally the ``Unifi`` mechanism driver needs to be enabled from
the ml2 config file ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,unifi
   ...

Physical networks need to be declared in the ML2 config as well, with a range
of VLANs that can be allocated to tenant networks.  Several physical networks
can coexist, possibly with overlapping VLAN ranges: in that case, each switch
configuration needs to include its physical network, see :ref:`physicalnetworks`.
Example of ``/etc/neutron/plugins/ml2/ml2_conf.ini`` with two physical networks::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:799,physnet2:600:850

For a given physical network, it is possible to specify several disjoint
ranges of VLANs by simply repeating the physical network name multiple times::

   [ml2_type_vlan]
   network_vlan_ranges = physnet1:700:720,physnet1:750:760

(Re)start ``neutron-server`` specifying the additional configuration file
containing switch configuration::

    neutron-server \
        --config-file /etc/neutron/neutron.conf \
        --config-file /etc/neutron/plugins/ml2/ml2_conf.ini \
        --config-file /etc/neutron/plugins/ml2/ml2_conf_unifi.ini

.. _synchronization:

Synchronization
===============

Some devices are limited in the number of concurrent SSH sessions that they can
support, or do not support concurrent configuration database updates. In these
cases it can be useful to use an external service to synchronize access to the
managed devices. This synchronization is provided by the `Tooz library
<https://docs.openstack.org/tooz/latest/>`__, which provides support for a
number of different backends, including Etcd, ZooKeeper, and others. A
connection URL for the backend should be configured as follows::

    [ngs_coordination]
    backend_url = <backend URL>

The backend URL format includes the Tooz driver as the scheme, with driver
options passed using query string parameters. For example, to use the
``etcd3gw`` driver with an API version of ``v3`` and a path to a CA
certificate::

    [ngs_coordination]
    backend_url = etcd3+https://etcd.example.com?api_version=v3,ca_cert=/path/to/ca/cert.crt

The default behaviour is to limit the number of concurrent active connections
to each device to one, but the number may be configured per-device as follows::

    [unifi:device-hostname]
    ngs_max_connections = <max connections>

When synchronization is used, each Neutron thread executing the
networking-generic-switch plugin will attempt to acquire a lock, with a default
timeout of 60 seconds before failing. This timeout can be configured as follows
(setting it to 0 means no timeout)::

    [ngs_coordination]
    ...
    acquire_timeout = <timeout in seconds>

.. _batching:

Batching
========

For many network devices there is a significant SSH connection overhead which
is incurred for each network or port configuration change. In a large scale
system with many concurrent changes, this overhead adds up quickly. Since the
Antelope release, the Generic Switch driver includes support to batch up switch
configuration changes and apply them together using a single SSH connection.

This is implemented using etcd as a queueing system. Commands are added
to an input key, then a worker thread processes the available commands
for a particular switch device. We pull off the queue using the version
at which the keys were added, giving a FIFO style queue. The result of
each command set are added to an output key, which the original request
thread is watching. Distributed locks are used to serialise the
processing of commands for each switch device.

The etcd endpoint is configured using the same ``[ngs_coordination]
backend_url`` option used in :ref:`synchronization`, with the limitation that
only ``etcd3gw`` is supported.

Additionally, each device that will use batched configuration should include
the following option::

    [unifi:device-hostname]
    ngs_batch_requests = True

Disabling Inactive Ports
========================

By default, switch interfaces remain administratively enabled when not in use,
and the access VLAN association is removed. On most devices, this will cause
the interface to be a member of the default VLAN, usually VLAN 1. This could
be a security issue, with unallocated ports having access to a shared network.

To resolve this issue, it is possible to configure interfaces as
administratively down when not in use. This is done on a per-device basis,
using the ``ngs_disable_inactive_ports`` flag::

    [unifi:device-hostname]
    ngs_disable_inactive_ports = <optional boolean>

This is currently supported by the following devices:

* Juniper Junos OS
* ArubaOS-CX
* Cisco NX-OS

Network Name Format
===================

By default, when a network is created on a switch, if the switch supports
assigning names to VLANs, they are assigned a name of the neutron network UUID.
For example::

    8f60256e4b6343bf873026036606ce5e

It is possible to use a different format for the network name using the
``ngs_network_name_format`` option. This option uses Python string formatting
syntax, and accepts the parameters ``{network_id}`` and ``{segmentation_id}``.
For example::

    [unifi:device-hostname]
    ngs_network_name_format = neutron-{network_id}-{segmentation_id}

Some switches have issues assigning VLANs a name that starts with a number,
and this configuration option can be used to avoid this.

Manage VLANs
============

By default, on network creation VLANs are added to all switches. In a similar
way, VLANs are removed when it seems they are no longer required.
However, in some cases only a subset of the ports are managed by Neutron.
In a similar way, when multiple switches are used, it is very common that
the network administrator restricts the VLANs allowed. In these cases, there
is little utility in adding and removing vlans on the switches. This process
takes time, so not doing this can speed up a number of common operations.
A particular case where this can cause problems is when a VLAN used for
the switch management interface, or any other port not managed by Neutron,
is removed by this Neutron driver.

To stop networking generic switch trying to add or remove VLANs on the switch,
administrator are expected to pre-add all enabled VLANs as well as tagging
these VLANs on trunk ports.
Once those VLANs and trunk ports are preconfigured on the switch, you can
use the following configuration to stop networking generic switch adding or
removing any VLANs::

    [unifi:device-hostname]
    ngs_manage_vlans = False

Saving configuration on devices
===============================

By default, all configuration changes are saved on persistent storage of the
devices, using model-specific commands.  This occurs after each change.

This may be undesirable for performance reasons, or if you have external means
of saving configuration on a regular basis.  In this case, configuration saving
can be disabled::

    [unifi:device-hostname]
    ngs_save_configuration = False

Trunk ports
===========

When VLANs are created on the switches, it is common to want to tag these
VLANS on one or more trunk ports.  To do this, you need to declare a
comma-separated list of trunk ports that can be managed by Networking Generic
Switch.  It will then dynamically tag and untag VLANs on these ports whenever
it creates and deletes VLANs.  For example::

    [unifi:device-hostname]
    ngs_trunk_ports = Ethernet1/48, Port-channel1

This is useful when managing several switches in the same physical network,
because they are likely to be interconnected with trunk links.
Another important use-case is to connect the DHCP agent with a trunk port,
because the agent needs access to all active VLANs.

Note that this option is only used if ``ngs_manage_vlans = True``.

.. _physicalnetworks:

Multiple physical networks
==========================

It is possible to use Networking Generic Switch to manage several physical
networks.  The desired physical network is selected by the Neutron API client
when it creates the network object.

In this case, you may want to only create VLANs on switches that belong to the
requested physical network, especially because VLAN ranges from separate
physical networks may overlap.  This also improves reconfiguration performance
because fewer switches will need to be configured whenever a network is
created/deleted.

To this end, each switch can be configured with a list of physical networks
it belongs to::

    [unifi:device-hostname]
    ngs_physical_networks = physnet1, physnet2

Physical network names should match the names defined in the ML2 configuration.

If no physical network is declared in a switch configuration, then VLANs for
all physical networks will be created on this switch.

Note that this option is only used if ``ngs_manage_vlans = True``.

SSH algorithm configuration
===========================

You may need to tune the SSH negotiation process for some devices.  Reasons
include using a faster key exchange algorithm, disabling an algorithm that
has a buggy implementation on the target device, or working around limitations
related to FIPS requirements.

The ``ngs_ssh_disabled_algorithms`` configuration parameter allows to selectively
disable algorithms of a given type (key exchange, cipher, MAC, etc). It is based
on `Paramiko's disabled_algorithms setting
<https://docs.paramiko.org/en/stable/api/transport.html#paramiko.transport.Transport.__init__>`__.

The format is a list of ``<type>:<algorithm>`` entries to disable. The same type
can be repeated several times with different algorithms. Here is an example configuration::

    [unifi:device-hostname]
    ngs_ssh_disabled_algorithms = kex:diffie-hellman-group-exchange-sha1, ciphers:blowfish-cbc, ciphers:3des-cbc

As of Paramiko 2.9.1, the valid types are ``ciphers``, ``macs``, ``keys``, ``pubkeys``,
``kex``, ``gsskex``.  However, this might change depending on the version of Paramiko.
Check Paramiko source code or documentation to determine the accepted algorithm types.

UniFi Controller Integration
=========================

The UniFi ML2 Driver allows OpenStack Neutron to integrate with Ubiquiti UniFi Network controllers to manage switch ports, VLANs, and other features on UniFi switches. This section describes the configuration options specific to the UniFi ML2 driver.

To enable the UniFi mechanism driver, add it to the ML2 configuration in ``/etc/neutron/plugins/ml2/ml2_conf.ini``::

   [ml2]
   tenant_network_types = vlan
   type_drivers = local,flat,vlan,gre,vxlan
   mechanism_drivers = openvswitch,unifi
   ...

UniFi Controller Configuration
-----------------------------

The UniFi ML2 driver connects to a UniFi Network controller to manage UniFi switches. The following configuration options should be added to ``/etc/neutron/plugins/ml2/ml2_conf.ini`` or a separate file like ``/etc/neutron/plugins/ml2/ml2_conf_unifi.ini``::

    [unifi]
    controller = https://<controller-ip>
    username = <admin-username>
    password = <admin-password>
    site = default
    verify_ssl = True
    
    # Optional configuration for port naming
    port_name_format = openstack-port-{port_id}
    port_description_format = OpenStack port {port_id}
    
    # Connection retry settings
    api_retry_count = 3
    port_setup_retry_count = 3
    port_setup_retry_interval = 1
    
    # Startup behavior
    sync_startup = True
    
    # Advanced trunk port behavior
    use_all_networks_for_trunk = True
    
    # Port security features
    enable_port_security = True
    
    # QoS features
    enable_qos = False
    default_bandwidth_limit = 0
    
    # Storm control
    enable_storm_control = False
    storm_control_broadcasting = 0
    storm_control_multicasting = 0
    storm_control_unknown_unicast = 0
    
    # Port monitoring
    monitor_port_state = True
    monitor_interval = 60

Required Parameters:

* ``controller``: URL of the UniFi Network controller (e.g., https://unifi.example.com:8443)
* ``username``: Username for UniFi controller authentication
* ``password``: Password for UniFi controller authentication

Optional Parameters:

* ``site``: UniFi site name to manage (defaults to "default")
* ``verify_ssl``: Whether to verify SSL certificates (default: True)
* ``port_name_format``: Format string for port names on switches (default: openstack-port-{port_id})
* ``port_description_format``: Format string for port descriptions (default: OpenStack port {port_id})
* ``api_retry_count``: Number of times to retry API calls (default: 3)
* ``port_setup_retry_count``: Number of times to retry port setup operations (default: 3)
* ``port_setup_retry_interval``: Interval between port setup retries in seconds (default: 1)
* ``sync_startup``: Whether to sync networks on startup (default: True)
* ``use_all_networks_for_trunk``: Use "All Networks" option for trunk ports (default: True)

ML2 Feature Support
------------------

The UniFi ML2 driver supports the following ML2 features:

1. **VLAN Networks**: Creating and managing VLAN networks on UniFi switches
2. **Port Binding**: Binding ports to specific switch ports
3. **Trunk Ports**: Managing trunk ports with native and tagged VLANs
4. **Port Security**: Configuring port security features like MAC address filtering, BPDU guard, and loop guard
5. **QoS**: Bandwidth limiting on a per-port basis
6. **Storm Control**: Limiting broadcast, multicast, and unknown unicast traffic
7. **Port Monitoring**: Monitoring port state and updating OpenStack port status

Advanced Features Configuration
-----------------------------

Port Security Features:

* ``enable_port_security``: Enable port security features (default: True)
* When enabled, configures BPDU guard, loop guard, and STP port fast on access ports

QoS Features:

* ``enable_qos``: Enable QoS features (default: False)
* ``default_bandwidth_limit``: Default bandwidth limit in Kbps (0 means unlimited)

Storm Control:

* ``enable_storm_control``: Enable storm control on ports (default: False)
* ``storm_control_broadcasting``: Storm control threshold for broadcast traffic (0-100%)
* ``storm_control_multicasting``: Storm control threshold for multicast traffic (0-100%)
* ``storm_control_unknown_unicast``: Storm control threshold for unknown unicast traffic (0-100%)

Port Monitoring:

* ``monitor_port_state``: Monitor port state and update OpenStack port status (default: True)
* ``monitor_interval``: Interval in seconds to monitor port state (default: 60)

Example Configuration
-------------------

Here's a complete example configuration for the UniFi ML2 driver::

    [ml2]
    tenant_network_types = vlan
    type_drivers = local,flat,vlan,gre,vxlan
    mechanism_drivers = openvswitch,unifi
    
    [ml2_type_vlan]
    network_vlan_ranges = physnet1:100:200,physnet2:300:400
    
    [unifi]
    controller = https://unifi.example.com:8443
    username = admin
    password = verysecurepassword
    site = default
    verify_ssl = True
    
    # Enable QoS with a default limit of 1Gbps
    enable_qos = True
    default_bandwidth_limit = 1000000
    
    # Enable storm control
    enable_storm_control = True
    storm_control_broadcasting = 80
    storm_control_multicasting = 80
    storm_control_unknown_unicast = 80

Binding Ports to UniFi Switches
-----------------------------

To bind a port to a specific UniFi switch port, use the following binding profile format::

    {
        "binding:profile": {
            "local_link_information": [
                {
                    "switch_id": "78:45:58:ab:cd:ef",  # MAC address of the UniFi switch
                    "port_id": "3"                    # Port number on the switch
                }
            ]
        }
    }

The ``switch_id`` must match the MAC address of a UniFi switch managed by the configured UniFi controller.
