"""
Minimal low-level MCP HTTP server without FastMCP dependency.

Provides a registration API compatible with `payments.mcp.attach(server)`
by exposing `registerTool`, `registerResource`, and `registerPrompt`.

It also exposes a simple ASGI app handling a subset of MCP JSON-RPC over HTTP:
- initialize
- tools/list, tools/call
- resources/list
- prompts/list
"""

from typing import Any, Awaitable, Callable, Dict, List, Tuple
import json

from payments_py.mcp import build_extra_from_http_headers


class LowLevelMcpServer:
    """Low-level MCP server adapter storing registrations and serving a raw ASGI app."""

    def __init__(self, server_name: str, version: str):
        """Initialize the low-level server.

        Args:
            server_name: Logical server name used in MCP URLs
            version: Server version (informational)
        """
        self.server_name = server_name
        self.version = version
        self.tools: Dict[str, Dict[str, Any]] = {}
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.prompts: Dict[str, Dict[str, Any]] = {}

    def registerTool(self, name: str, config: Any, handler: Callable[..., Awaitable[Any]]) -> None:  # noqa: N802
        """Register a tool handler.

        Args:
            name: Tool name
            config: Arbitrary configuration, usually includes `title`
            handler: Async handler with signature (args, extra)
        """
        self.tools[name] = {"config": config, "handler": handler}

    def registerResource(  # noqa: N802
        self, name: str, template: Any, config: Any, handler: Callable[..., Awaitable[Any]]
    ) -> None:
        """Register a resource handler.

        Args:
            name: Resource name
            template: Template spec (unused here)
            config: Arbitrary configuration
            handler: Async handler with signature (uri, variables, extra)
        """
        self.resources[name] = {"template": template, "config": config, "handler": handler}

    def registerPrompt(self, name: str, config: Any, handler: Callable[..., Awaitable[Any]]) -> None:  # noqa: N802
        """Register a prompt handler.

        Args:
            name: Prompt name
            config: Arbitrary configuration
            handler: Async handler with signature (args, extra)
        """
        self.prompts[name] = {"config": config, "handler": handler}

    def _capabilities(self) -> Dict[str, Any]:
        return {
            "tools": list(self.tools.keys()),
            "resources": list(self.resources.keys()),
            "prompts": list(self.prompts.keys()),
        }

    def _list_tools(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for name, entry in self.tools.items():
            cfg = entry.get("config") or {}
            items.append(
                {
                    "name": name,
                    "description": str(cfg.get("title") or name),
                    "inputSchema": {"type": "object"},
                }
            )
        return items

    def _list_resources(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for name, entry in self.resources.items():
            cfg = entry.get("config") or {}
            items.append(
                {
                    "uri": f"mcp://{self.server_name}/resources/{name}",
                    "name": name,
                    "mimeType": str(cfg.get("mimeType") or "application/json"),
                }
            )
        return items

    def _list_prompts(self) -> List[Dict[str, Any]]:
        items: List[Dict[str, Any]] = []
        for name, entry in self.prompts.items():
            cfg = entry.get("config") or {}
            items.append({"name": name, "description": str(cfg.get("title") or name)})
        return items

    def asgi_app(self):
        """Return a minimal JSON-RPC ASGI app implementing core MCP methods."""

        async def app(scope, receive, send):
            if scope.get("type") != "http":
                await send(
                    {
                        "type": "http.response.start",
                        "status": 404,
                        "headers": [(b"content-type", b"application/json")],
                    }
                )
                await send({"type": "http.response.body", "body": b"{}"})
                return

            # Read body
            body = b""
            more = True
            while more:
                message = await receive()
                if message["type"] != "http.request":
                    continue
                body += message.get("body", b"")
                more = message.get("more_body", False)

            # Parse JSON-RPC
            try:
                payload = json.loads(body.decode() or "{}") if body else {}
            except Exception:
                payload = {}

            method = payload.get("method") if isinstance(payload, dict) else None
            pid = payload.get("id") if isinstance(payload, dict) else None

            # Build extra from headers
            headers_dict: Dict[str, Any] = {}
            try:
                headers_list: List[Tuple[bytes, bytes]] = scope.get("headers", [])
                headers_dict = {k.decode(): v.decode() for k, v in headers_list}
            except Exception:
                headers_dict = {}
            extra = build_extra_from_http_headers(headers_dict)

            resp: Dict[str, Any]
            try:
                if method == "initialize":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": pid,
                        "result": {
                            "protocolVersion": payload.get("params", {}).get(
                                "protocolVersion", "0.1.0"
                            ),
                            "serverInfo": {"name": self.server_name, "version": self.version},
                            "capabilities": {},
                        },
                    }
                elif method == "tools/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": pid,
                        "result": {"tools": self._list_tools()},
                    }
                elif method == "resources/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": pid,
                        "result": {"resources": self._list_resources()},
                    }
                elif method == "prompts/list":
                    resp = {
                        "jsonrpc": "2.0",
                        "id": pid,
                        "result": {"prompts": self._list_prompts()},
                    }
                elif method == "tools/call":
                    params = payload.get("params", {})
                    name = params.get("name")
                    args = params.get("arguments") or {}
                    entry = self.tools.get(str(name))
                    if not entry:
                        resp = {
                            "jsonrpc": "2.0",
                            "id": pid,
                            "error": {"code": -32601, "message": "Tool not found"},
                        }
                    else:
                        handler = entry["handler"]
                        result = handler(args, extra)
                        if hasattr(result, "__await__"):
                            result = await result  # type: ignore[assignment]

                        # If async iterable, consume to ensure paywall redeem on completion
                        if hasattr(result, "__aiter__"):
                            texts: List[str] = []
                            async for chunk in result:  # type: ignore[assignment]
                                texts.append(str(chunk))
                            result = {"content": [{"type": "text", "text": "\n".join(texts)}]}

                        if isinstance(result, str):
                            result = {"content": [{"type": "text", "text": result}]}

                        resp = {"jsonrpc": "2.0", "id": pid, "result": result}
                else:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": pid,
                        "error": {"code": -32601, "message": "Method not found"},
                    }
            except Exception as e:  # pragma: no cover - best effort error mapping
                resp = {
                    "jsonrpc": "2.0",
                    "id": pid,
                    "error": {"code": -32000, "message": str(e)},
                }

            data = json.dumps(resp).encode()
            await send(
                {
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [(b"content-type", b"application/json")],
                }
            )
            await send({"type": "http.response.body", "body": data})

        return app
