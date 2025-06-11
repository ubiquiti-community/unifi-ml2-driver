"""Provide an object to communicate with UniFi Network application."""

from __future__ import annotations

import asyncio
import ssl
from types import MappingProxyType
from typing import Any, Literal

from aiohttp import CookieJar, ClientSession
from aiounifi import Unauthorized, BadGateway, Forbidden, ServiceUnavailable, RequestError, ResponseError, LoginRequired, AiounifiException
from aiounifi.controller import Controller
from aiounifi.models.configuration import Configuration

from .exceptions import AuthenticationRequired, CannotConnect

from oslo_log import log as logging

from oslo_config import cfg
LOG = logging.getLogger(__name__)
CONF = cfg.CONF


async def get_unifi_api(
    config: MappingProxyType[str, Any],
) -> Controller:
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

    api = Controller(
        Configuration(
            session,
            host=CONF.unifi.host,
            username=CONF.unifi.username,
            password=CONF.unifi.password,
            port=CONF.unifi.port,
            site=CONF.unifi.site,
            ssl_context=ssl_context,
        )
    )

    try:
        async with asyncio.timeout(10):
            await api.login()

    except Unauthorized as err:
        LOG.warning(
            "Connected to UniFi Network at %s but not registered: %s",
            CONF.unifi.host,
            err,
        )
        raise AuthenticationRequired(reason=str(err)) from err

    except (
        TimeoutError,
        BadGateway,
        Forbidden,
        ServiceUnavailable,
        RequestError,
        ResponseError,
    ) as err:
        LOG.error(
            "Error connecting to the UniFi Network at %s: %s", CONF.unifi.host, err
        )
        raise CannotConnect(reason=str(err)) from err

    except LoginRequired as err:
        LOG.warning(
            "Connected to UniFi Network at %s but login required: %s",
            CONF.unifi.host,
            err,
        )
        raise AuthenticationRequired(reason=str(err)) from err

    except AiounifiException as err:
        LOG.exception("Unknown UniFi Network communication error occurred: %s", err)
        raise AuthenticationRequired(reason=str(err)) from err

    return api
