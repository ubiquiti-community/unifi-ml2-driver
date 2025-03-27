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
import ssl
from types import MappingProxyType
import unittest
from unittest import mock

import aiohttp
import aiounifi
from aiounifi.models.configuration import Configuration
from oslo_config import cfg
from oslo_log import log as logging

from unifi_ml2_driver import unifi_api
from unifi_ml2_driver import exceptions


class TestUnifiApi(unittest.TestCase):
    """Test cases for UniFi API client."""

    def setUp(self):
        """Set up test environment."""
        # Mock configuration
        self.cfg_mock = mock.patch.object(cfg, 'CONF')
        self.cfg_mock.start()
        
        # Configure settings
        cfg.CONF.unifi = mock.MagicMock()
        cfg.CONF.unifi.controller = "https://unifi.example.com"
        cfg.CONF.unifi.username = "admin"
        cfg.CONF.unifi.password = "password"
        cfg.CONF.unifi.verify_ssl = False
        
        # Mock aiohttp.ClientSession
        self.mock_session = mock.MagicMock()
        self.session_patch = mock.patch('aiohttp.ClientSession', 
                                       return_value=self.mock_session)
        self.mock_client_session = self.session_patch.start()
        
        # Mock aiounifi.Controller
        self.mock_controller = mock.MagicMock()
        self.controller_patch = mock.patch('aiounifi.Controller', 
                                         return_value=self.mock_controller)
        self.mock_controller_class = self.controller_patch.start()
        
        # Set up event loop
        self.event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.event_loop)
        
        # Mock asyncio.timeout
        self.mock_timeout = mock.MagicMock()
        self.timeout_patch = mock.patch('asyncio.timeout', 
                                      return_value=self.mock_timeout)
        self.mock_timeout_factory = self.timeout_patch.start()
        
        # Mock successful login
        self.mock_controller.login = mock.AsyncMock()
    
    def tearDown(self):
        """Clean up test environment."""
        self.cfg_mock.stop()
        self.session_patch.stop()
        self.controller_patch.stop()
        self.timeout_patch.stop()
        self.event_loop.close()
    
    async def _test_get_unifi_api(self):
        """Helper method to run asyncio test."""
        config = MappingProxyType({})
        return await unifi_api.get_unifi_api(config)
    
    def test_get_unifi_api_success(self):
        """Test successful API client creation."""
        # Run the coroutine
        controller = self.event_loop.run_until_complete(self._test_get_unifi_api())
        
        # Verify the controller was created correctly
        self.assertEqual(controller, self.mock_controller)
        
        # Verify login was called
        self.mock_controller.login.assert_called_once()
        
        # Verify client session was created with correct parameters
        self.mock_client_session.assert_called_once()
        call_kwargs = self.mock_client_session.call_args[1]
        self.assertFalse(call_kwargs['verify_ssl'])
        
        # Verify controller was created with correct configuration
        self.mock_controller_class.assert_called_once()
        config_arg = self.mock_controller_class.call_args[0][0]
        self.assertEqual(config_arg.host, cfg.CONF.unifi.controller)
        self.assertEqual(config_arg.username, cfg.CONF.unifi.username)
        self.assertEqual(config_arg.password, cfg.CONF.unifi.password)
        self.assertEqual(config_arg.ssl_context, False)
    
    def test_get_unifi_api_with_verify_ssl(self):
        """Test API client creation with SSL verification."""
        # Set SSL verification to True
        cfg.CONF.unifi.verify_ssl = True
        
        # Run the coroutine
        controller = self.event_loop.run_until_complete(self._test_get_unifi_api())
        
        # Verify client session was created without verify_ssl parameter
        self.mock_client_session.assert_called_once_with()
        
        # Verify controller was created with default SSL context
        self.mock_controller_class.assert_called_once()
        config_arg = self.mock_controller_class.call_args[0][0]
        self.assertNotEqual(config_arg.ssl_context, False)
    
    @mock.patch('ssl.create_default_context')
    def test_get_unifi_api_with_ssl_cafile(self, mock_ssl_context):
        """Test API client creation with SSL CA file."""
        # Set SSL verification to CA file path
        cfg.CONF.unifi.verify_ssl = "/path/to/ca.crt"
        
        # Mock SSL context
        mock_context = mock.MagicMock()
        mock_ssl_context.return_value = mock_context
        
        # Run the coroutine
        controller = self.event_loop.run_until_complete(self._test_get_unifi_api())
        
        # Verify SSL context was created with CA file
        mock_ssl_context.assert_called_once_with(cafile="/path/to/ca.crt")
        
        # Verify controller was created with the SSL context
        self.mock_controller_class.assert_called_once()
        config_arg = self.mock_controller_class.call_args[0][0]
        self.assertEqual(config_arg.ssl_context, mock_context)
    
    def test_get_unifi_api_unauthorized(self):
        """Test unauthorized exception handling."""
        # Set up unauthorized exception
        self.mock_controller.login.side_effect = aiounifi.Unauthorized("Unauthorized")
        
        # Run the coroutine and expect exception
        with self.assertRaises(exceptions.AuthenticationRequired):
            self.event_loop.run_until_complete(self._test_get_unifi_api())
    
    def test_get_unifi_api_connection_error(self):
        """Test connection error handling."""
        # Set up various connection errors
        for error in [
            TimeoutError("Connection timed out"),
            aiounifi.BadGateway("Bad gateway"),
            aiounifi.Forbidden("Forbidden"),
            aiounifi.ServiceUnavailable("Service unavailable"),
            aiounifi.RequestError("Request error"),
            aiounifi.ResponseError("Response error")
        ]:
            self.mock_controller.login.side_effect = error
            
            # Run the coroutine and expect exception
            with self.assertRaises(exceptions.CannotConnect):
                self.event_loop.run_until_complete(self._test_get_unifi_api())
    
    def test_get_unifi_api_login_required(self):
        """Test login required exception handling."""
        # Set up login required exception
        self.mock_controller.login.side_effect = aiounifi.LoginRequired("Login required")
        
        # Run the coroutine and expect exception
        with self.assertRaises(exceptions.AuthenticationRequired):
            self.event_loop.run_until_complete(self._test_get_unifi_api())
            
    def test_get_unifi_api_general_exception(self):
        """Test general exception handling."""
        # Set up general exception
        self.mock_controller.login.side_effect = aiounifi.AiounifiException("Unknown error")
        
        # Run the coroutine and expect exception
        with self.assertRaises(exceptions.AuthenticationRequired):
            self.event_loop.run_until_complete(self._test_get_unifi_api())