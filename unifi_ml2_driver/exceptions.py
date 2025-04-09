# Copyright 2016 Mirantis, Inc.
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

"""Exceptions for UniFi ML2 Driver."""

from neutron_lib import exceptions

from unifi_ml2_driver._i18n import _


class UnifiException(exceptions.NeutronException):
    """Base UniFi Exception."""
    message = _("UniFi failure: %(reason)s")

    def __init__(self, msg=None, **kwargs):
        if msg is None:
            # Ensure kwargs has 'reason' if not provided
            if 'reason' not in kwargs and 'error' in kwargs:
                kwargs['reason'] = kwargs['error']
            msg = self.message % kwargs
        super(UnifiException, self).__init__(msg=msg)


class CannotConnect(UnifiException):
    """Raised when connection to UniFi controller fails."""
    message = _("Cannot connect to UniFi controller: %(reason)s")


class AuthenticationRequired(UnifiException):
    """Raised when authentication to UniFi controller fails."""
    message = _("Authentication to UniFi controller failed: %(reason)s")


class UnifiNetmikoConfigError(UnifiException):
    """Raised when configuration operation fails."""
    message = _("Failed to configure UniFi device: %(reason)s")


class UnifiVLANConfigError(UnifiException):
    """Raised when VLAN configuration operation fails."""
    message = _("Failed to configure VLAN: %(reason)s")


class UnifiPortNotFound(UnifiException):
    """Raised when port is not found on the device."""
    message = _("Port not found on device: %(reason)s")


class UnifiDeviceNotFound(UnifiException):
    """Raised when device is not found."""
    message = _("Device not found: %(reason)s")


class UnifiQoSConfigError(UnifiException):
    """Raised when QoS configuration fails."""
    message = _("Failed to configure QoS: %(reason)s")


class UnifiPortSecurityConfigError(UnifiException):
    """Raised when port security configuration fails."""
    message = _("Failed to configure port security: %(reason)s")


class UnifiTrunkConfigError(UnifiException):
    """Raised when trunk port configuration fails."""
    message = _("Failed to configure trunk port: %(reason)s")


class UnifiBatchError(UnifiException):
    """Raised when a batch operation fails."""
    message = _("Batch operation failed on device %(device)s: %(error)s")
    
    def __init__(self, device=None, error=None):
        kwargs = {'device': device, 'error': error}
        super(UnifiBatchError, self).__init__(msg=None, **kwargs)