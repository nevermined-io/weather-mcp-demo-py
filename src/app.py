import os
from dotenv import load_dotenv
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

from payments_py.payments import Payments

from server_lowlevel import LowLevelMcpServer
from mcp.server.fastmcp import FastMCP
from urllib.parse import urlparse
from services.weather_service import sanitize_city, get_today_weather

from local_mcp.handlers.weather_tool import (
    weather_tool_handler,
    weather_tool_credits_calculator,
)
from local_mcp.handlers.weather_resource import weather_resource_handler
from local_mcp.handlers.weather_prompt import weather_prompt_handler


def create_app(
    nvm_api_key: str | None = None,
    nvm_environment: str | None = None,
    agent_id: str | None = None,
    server_name: str | None = None,
    server_mode: str | None = None,
) -> FastAPI:
    """
    Create and configure the FastAPI application exposing an MCP-compatible HTTP endpoint.

    Parameters
    ----------
    nvm_api_key : str | None, optional
        Nevermined API key. If omitted, read from the environment.
    nvm_environment : str | None, optional
        Nevermined environment name. If omitted, read from the environment.
    agent_id : str | None, optional
        Agent decentralized identifier. If omitted, read from the environment.
    server_name : str | None, optional
        MCP server name. If omitted, read from the environment.

    Returns
    -------
    FastAPI
        Configured FastAPI app with the `/mcp` endpoint and a health root.
    """
    load_dotenv()
    # Resolve configuration from arguments or environment
    nvm_api_key = nvm_api_key or os.getenv("NVM_SERVER_API_KEY", "")
    nvm_environment = nvm_environment or os.getenv("NVM_ENV", "staging_sandbox")
    agent_id = agent_id or os.getenv("NVM_AGENT_ID", "")
    server_name = "weather-mcp"
    server_mode = (server_mode or os.getenv("MCP_SERVER_MODE", "fastmcp")).lower()

    # Build MCP server and the sub ASGI app once
    payments = Payments({"nvm_api_key": nvm_api_key, "environment": nvm_environment})
    if server_mode == "low" or server_mode == "lowlevel":
        # Low-level server passes `extra` to handlers directly; still provide getExtra for consistency
        payments_config = {
            "agentId": agent_id,
            "serverName": server_name,
            "getExtra": (lambda: {}),  # not used when low-level server supplies extra to handlers
        }
        server = LowLevelMcpServer(server_name, "0.1.0")
        sub_app = server.asgi_app()

        tools_keys = server.tools
        resources_keys = server.resources
        prompts_keys = server.prompts
    else:
        fastmcp = FastMCP(name=server_name, json_response=True)
        payments_config = {"agentId": agent_id, "serverName": server_name, "getContext": fastmcp.get_context}

        sub_app = None  # will be created after handlers are registered
        tools_keys: Dict[str, Any] = {}
        resources_keys: Dict[str, Any] = {}
        prompts_keys: Dict[str, Any] = {}

    payments.mcp.configure(payments_config)
    # Register handlers with paywall protection
    protected_tool = payments.mcp.with_paywall(
        weather_tool_handler,
        {"kind": "tool", "name": "weather.today", "credits": weather_tool_credits_calculator},
    )
    protected_resource = payments.mcp.with_paywall(
        weather_resource_handler,
        {"kind": "resource", "name": "weather.today", "credits": weather_tool_credits_calculator},
    )
    protected_prompt = payments.mcp.with_paywall(
        weather_prompt_handler,
        {"kind": "prompt", "name": "weather.ensureCity", "credits": 0},
    )

    async def free_tool_handler(args: Dict[str, Any]) -> Dict[str, Any]:
        """Unprotected tool that returns today's weather for a given city."""
        city = sanitize_city((args or {}).get("city", ""))
        data = get_today_weather(city)
        text = f"Weather today in {data.city}: {data.weatherText}, min {data.tminC}C, max {data.tmaxC}C"
        return {"content": [{"type": "text", "text": text}]}

    if server_mode == "low" or server_mode == "lowlevel":
        server.registerTool("weather.today", {"title": "Today's Weather"}, protected_tool)
        server.registerResource(
            "weather.today",
            {"tpl": True},
            {"title": "Today's Weather Resource", "mimeType": "application/json"},
            protected_resource,
        )
        server.registerPrompt("weather.ensureCity", {"title": "Ensure city"}, protected_prompt)
        # Unprotected tool registration
        server.registerTool("weather.free", {"title": "Free Weather"}, free_tool_handler)
    else:
        tools_keys["weather.today"] = {"config": {"title": "Today's Weather"}}
        resources_keys["weather.today"] = {"config": {"title": "Today's Weather Resource", "mimeType": "application/json"}}
        prompts_keys["weather.ensureCity"] = {"config": {"title": "Ensure city"}}
        tools_keys["weather.free"] = {"config": {"title": "Free Weather"}}

        @fastmcp.tool(name="weather.today", title="Today's Weather")
        async def _tool(city: str | None = None) -> str:
            args = {"city": city or ""}
            # Do not pass ctx explicitly; paywall builds extra via configured getContext
            res = await protected_tool(args)
            if isinstance(res, dict):
                for c in (res.get("content") or []):
                    if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
                        return c["text"]
            return str(res)

        @fastmcp.resource("weather://{city}", title="Today's Weather Resource", mime_type="application/json")
        async def _resource(city: str) -> str:
            uri = urlparse(f"weather://today/{city}")
            # Pass None as third arg so paywall resolves context via getContext
            result = await protected_resource(uri, {"city": [city]}, None)
            try:
                contents = result.get("contents", [])
                for item in contents:
                    text = item.get("text")
                    if isinstance(text, str):
                        return text
            except Exception:
                pass
            return "{}"

        @fastmcp.prompt(title="Ensure city")
        async def _prompt(city: str | None = None) -> str:
            # Do not pass ctx explicitly; paywall builds extra via configured getContext
            res = await protected_prompt({"city": city or ""})
            try:
                messages = res.get("messages", [])
                if messages:
                    content = messages[0].get("content", {})
                    if isinstance(content, dict) and content.get("type") == "text":
                        return str(content.get("text", ""))
            except Exception:
                pass
            return ""

        @fastmcp.tool(name="weather.free", title="Free Weather")
        async def _free(city: str | None = None) -> str:
            args = {"city": city or ""}
            out = await free_tool_handler(args)
            if isinstance(out, dict):
                for c in (out.get("content") or []):
                    if c.get("type") == "text" and isinstance(c.get("text"), str):
                        return c["text"]
            return str(out)

        # Create the ASGI app now that handlers are registered
        sub_app = fastmcp.streamable_http_app()

    # def _build_capabilities() -> Dict[str, Any]:
    #     """Collect tool, resource and prompt names exposed by the server."""
    #     return {
    #         "capabilities": {
    #             "tools": list((tools_keys or {}).keys()),
    #             "resources": list((resources_keys or {}).keys()),
    #             "prompts": list((prompts_keys or {}).keys()),
    #         }
    #     }

    # Define a lifespan that starts the FastMCP session manager for the app lifetime
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _lifespan(_app: FastAPI):  # noqa: D401
        if server_mode not in ("low", "lowlevel"):
            manager = fastmcp.session_manager
            async with manager.run():
                yield
        else:
            yield

    # Build FastAPI with custom lifespan and mount the MCP sub-app
    app = FastAPI(lifespan=_lifespan)
    app.mount("/", sub_app)

    @app.get("/health")
    async def root():
        """Simple health endpoint indicating the service is running."""
        return PlainTextResponse("weather-mcp-py is running")

    return app
