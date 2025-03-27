=================
Supported Devices
=================

The UniFi ML2 Driver supports Ubiquiti UniFi switches managed through a UniFi Network controller.

Supported UniFi Switch Models
----------------------------

The driver has been tested with the following UniFi switch models:

* UniFi Switch (USW) series
* UniFi Switch Enterprise (USW-Enterprise) series
* UniFi Switch Flex (USW-Flex) series
* UniFi Switch Aggregation (USW-Aggregation)
* UniFi Switch Pro (USW-Pro) series
* UniFi Industrial Switch (USW-Industrial)

Requirements
-----------

* UniFi Network Controller v6.0 or newer
* UniFi switches with firmware supporting VLANs

Architecture
-----------

The UniFi ML2 Driver communicates with the UniFi Network Controller API to manage switch configurations:

::

  OpenStack Neutron v2.0 => ML2 plugin => UniFi ML2 Driver => UniFi Network Controller API => UniFi Switches

The driver uses the `aiounifi <https://github.com/aiounifi/aiounifi>`_ library to interface with the UniFi Network Controller API.

Feature Support
-------------

The driver supports the following features on UniFi switches:

1. **VLAN Management**: Creating and deleting VLANs across switches
2. **Port Configuration**: Setting port VLANs (access and trunk modes)
3. **Port Security**: Enabling BPDU guard, loop guard, and storm control
4. **QoS**: Configuring bandwidth limits on ports
5. **Port Status Monitoring**: Tracking switch port status and updating Neutron

Limitations
----------

1. The UniFi Network Controller must be reachable from the Neutron servers.
2. Only VLANs defined within the ranges configured in Neutron can be managed.
3. Port security features depend on the capabilities of the specific UniFi switch model.

