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

from neutron_lib import exceptions

from unifi_ml2_driver._i18n import _


class UnifiException(exceptions.NeutronException):
    message = _("%(method)s failed.")


class UnifiConfigException(exceptions.NeutronException):
    message = _("%(option)s must be one of: %(allowed_options)s")


class UnifiEntrypointLoadError(UnifiException):
    message = _("Failed to load entrypoint %(ep)s: %(err)s")


class UnifiNetworkNameFormatInvalid(UnifiException):
    message = _("Invalid value for 'ngs_network_name_format': "
                "%(name_format)s. Valid format options include 'network_id' "
                "and 'segmentation_id'")


class UnifiNetmikoMethodError(UnifiException):
    message = _("Can not parse arguments: commands %(cmds)s, args %(args)s")


class UnifiNetmikoNotSupported(UnifiException):
    message = _("Netmiko does not support device type %(device_type)s")


class UnifiNetmikoConnectError(UnifiException):
    message = _("Failed to connect to Netmiko switch. "
                "Please contact your administrator.")


class UnifiNetmikoConfigError(UnifiException):
    message = _("Netmiko switch configuration operation failed. "
                "Please contact your administrator.")


class UnifiBatchError(UnifiException):
    message = _("Batching error: %(device)s, error: %(error)s")


class UnifiNotSupported(UnifiException):
    message = _("Requested feature %(feature)s is not supported by "
                "networking-generic-switch on the %(switch)s. %(error)s")

class AlreadyConfigured(UnifiException):
    """Controller is already configured."""


class AuthenticationRequired(UnifiException):
    """Unknown error occurred."""


class CannotConnect(UnifiException):
    """Unable to connect to UniFi Network."""


class LoginRequired(UnifiException):
    """Integration got logged out."""


class UserLevel(UnifiException):
    """User level too low."""