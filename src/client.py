"""Minimal HTTP client to interact with the MCP HTTP endpoint.

Exposes a small programmatic client and helpers that read configuration from
environment variables with sensible defaults.
"""

from typing import Any, Dict, Optional
import requests


class MCPHttpClient:
    """Very small JSON-RPC client targeting the /mcp endpoint."""

    def __init__(self, base_url: str, token: Optional[str] = None):
        """Initialize the MCP HTTP client.

        Parameters
        ----------
        base_url : str
            Base URL where the FastAPI app is listening (e.g., http://localhost:8000)
        token : Optional[str]
            Bearer token to include in Authorization header, if any
        """
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.session_id: Optional[str] = None
        self.protocol_version: Optional[str] = None

    def _headers(self) -> Dict[str, str]:
        """Build default headers for JSON-RPC requests."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["mcp-session-id"] = self.session_id
        if self.protocol_version:
            headers["mcp-protocol-version"] = self.protocol_version
        return headers

    def initialize(self) -> Dict[str, Any]:
        """Call MCP initialize."""
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "1.0",
                "clientInfo": {"name": "weather-mcp-py-client", "version": "0.1.0"},
                "capabilities": {},
            },
        }
        r = requests.post(f"{self.base_url}/mcp", json=payload, headers=self._headers(), timeout=20)
        r.raise_for_status()
        data = r.json()
        # Save session id for subsequent requests (stateful HTTP)
        self.session_id = r.headers.get("mcp-session-id") or self.session_id
        # Capture negotiated protocol version from response, if present
        try:
            self.protocol_version = (
                (data.get("result") or {}).get("protocolVersion")
                or self.protocol_version
            )
        except Exception:
            pass
        # Send notifications/initialized as per MCP spec
        try:
            notif_payload = {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": None,
            }
            requests.post(f"{self.base_url}/mcp", json=notif_payload, headers=self._headers(), timeout=10)
        except Exception:
            pass
        return data

    def _ensure_session(self) -> None:
        """Ensure initialize was called and session id stored."""
        if not self.session_id:
            self.initialize()

    def list_tools(self) -> Dict[str, Any]:
        """List available tools from the MCP server."""
        self._ensure_session()
        payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {"cursor": None}}
        r = requests.post(f"{self.base_url}/mcp", json=payload, headers=self._headers(), timeout=20)
        r.raise_for_status()
        return r.json()

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Generic tool invocation via JSON-RPC."""
        self._ensure_session()
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
        r = requests.post(f"{self.base_url}/mcp", json=payload, headers=self._headers(), timeout=30)
        r.raise_for_status()
        return r.json()

    # Convenience methods
    def call_weather_today(self, city: str) -> Dict[str, Any]:
        """Convenience helper to call the paywalled weather tool."""
        return self.call_tool("weather.today", {"city": city})

    def call_weather_free(self, city: str) -> Dict[str, Any]:
        """Convenience helper to call the free weather tool."""
        return self.call_tool("weather.free", {"city": city})

    # End of minimal client. Higher-level orchestration (env, payments, CLI) lives elsewhere.
