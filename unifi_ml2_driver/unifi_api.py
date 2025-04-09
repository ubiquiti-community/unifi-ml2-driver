"""Provide an object to communicate with UniFi Network application."""

from __future__ import annotations

import asyncio
import ssl
from types import MappingProxyType
from typing import Any, Literal

from aiohttp import CookieJar, ClientSession
import aiounifi
from aiounifi.models.configuration import Configuration

from .exceptions import AuthenticationRequired, CannotConnect

from oslo_log import log as logging

from oslo_config import cfg
LOG = logging.getLogger(__name__)
CONF = cfg.CONF


async def get_unifi_api(
    config: MappingProxyType[str, Any],
) -> aiounifi.Controller:
    """Create a aiounifi object and verify authentication."""
    ssl_context: ssl.SSLContext | Literal[False] = False
    if CONF.unifi.verify_ssl:
        ssl_context = ssl.create_default_context(
            purpose=ssl.Purpose.CLIENT_AUTH,
        )
        session = ClientSession(
            cookie_jar=CookieJar(unsafe=False),
        )
    else:
        session = ClientSession(
            cookie_jar=CookieJar(unsafe=True)
            )

    api = aiounifi.Controller(
        Configuration(
            session,
            host=CONF.unifi.controller,
            username=CONF.unifi.username,
            password=CONF.unifi.password,
            # port=8443,
            # site=CONF.unifi.site_id,
            ssl_context=ssl_context,
        )
    )

    try:
        async with asyncio.timeout(10):
            await api.login()

    except aiounifi.Unauthorized as err:
        LOG.warning(
            "Connected to UniFi Network at %s but not registered: %s",
            CONF.unifi.controller,
            err,
        )
        raise AuthenticationRequired(reason=str(err)) from err

    except (
        TimeoutError,
        aiounifi.BadGateway,
        aiounifi.Forbidden,
        aiounifi.ServiceUnavailable,
        aiounifi.RequestError,
        aiounifi.ResponseError,
    ) as err:
        LOG.error(
            "Error connecting to the UniFi Network at %s: %s", CONF.unifi.controller, err
        )
        raise CannotConnect(reason=str(err)) from err

    except aiounifi.LoginRequired as err:
        LOG.warning(
            "Connected to UniFi Network at %s but login required: %s",
            CONF.unifi.controller,
            err,
        )
        raise AuthenticationRequired(reason=str(err)) from err

    except aiounifi.AiounifiException as err:
        LOG.exception("Unknown UniFi Network communication error occurred: %s", err)
        raise AuthenticationRequired(reason=str(err)) from err

    return api
