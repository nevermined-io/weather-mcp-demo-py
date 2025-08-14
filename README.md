[![banner](https://raw.githubusercontent.com/nevermined-io/assets/main/images/logo/banner_logo.png)](https://nevermined.io)

## Weather MCP (Python: High-Level and Low-Level servers)

Minimal MCP server exposing a `weather.today(city)` tool, a `weather://today/{city}` resource and a `weather.ensureCity` prompt. Includes both a FastMCP-based server (High-Level) and a Low-Level server to demonstrate Nevermined Payments integration.

### About this demo

This repository is a reference/demo project used to test and validate the Model Context Protocol (MCP) integration inside Nevermined's Python SDK `payments-py`. It showcases how to protect MCP tools, resources and prompts with the paywall, both in a High‑Level (FastMCP) server and a Low‑Level JSON‑RPC server. It is intended for examples, local experimentation and integration tests, not as production‑ready code.

### Requirements

- Python >= 3.10
- Poetry (recommended) or pip

### Install

```bash
poetry install
# or
pip install -e .
```

### Run the server (High-Level: FastMCP over HTTP)

```bash
poetry run uvicorn weather_mcp_py.app:create_app \
  --factory --host 127.0.0.1 --port 8000
```

Environment (server):

```bash
export NVM_SERVER_API_KEY=...     # Server key (builder/agent owner)
export NVM_AGENT_ID=weather-agent # Logical agent id used in validation (or your real ID)
export NVM_ENV=staging_sandbox    # optional (staging_sandbox | production)
poetry run uvicorn weather_mcp_py.app:create_app --factory --host 127.0.0.1 --port 8000
```

### Run the server (Low-Level)

```bash
export MCP_SERVER_MODE=low
poetry run uvicorn weather_mcp_py.app:create_app \
  --factory --host 127.0.0.1 --port 8000
```

- High-Level endpoint: `POST /mcp` (JSON‑RPC; stateful HTTP via headers)
- Low-Level endpoint: `POST /mcp-low` (raw JSON‑RPC; path is arbitrary, client default uses `/mcp-low`)
- Health: `GET /health`

### Client demo (High-Level)

```bash
# Defaults: MCP_BASE_URL=http://localhost:8000, city "Madrid"
poetry run weather-mcp

# Custom base URL and city
MCP_BASE_URL=http://localhost:8000 MCP_CITY=Paris poetry run weather-mcp
```

Client environment:

```bash
export MCP_BASE_URL=http://localhost:8000
export NVM_API_KEY=...            # Subscriber key
export NVM_PLAN_ID=...            # Plan that grants access
export NVM_AGENT_ID=...           # Agent id associated to the plan
poetry run weather-mcp
```

### Client demo (Low-Level)

```bash
# Defaults: MCP_LOW_ENDPOINT=http://localhost:8000/mcp-low, city "Madrid"
poetry run weather-mcp-low

# Custom endpoint and city
MCP_LOW_ENDPOINT=http://localhost:8000/mcp-low MCP_CITY=Paris poetry run weather-mcp-low
```

### Tests

```bash
poetry run pytest -q
```

### Nevermined auth

The client obtains an access token with its `NVM_API_KEY` and sends it as `Authorization: Bearer ...`. The server requires `Authorization` and performs validation via the paywall. If unauthorized, the server responds with a custom JSON‑RPC error `-32003`.

Server env (recap):

```bash
export NVM_SERVER_API_KEY=...     # Server key (builder/agent owner)
export NVM_AGENT_ID=weather-agent # Logical agent id used in validation (or your real ID)
export NVM_ENV=staging_sandbox    # optional
```

Client env (recap):

```bash
export NVM_API_KEY=...            # Subscriber key
export NVM_PLAN_ID=...            # Plan that grants access
export NVM_AGENT_ID=...           # Agent id associated to the plan
```

### MCP Inspector (over HTTP)

If you have Node.js available, you can use the MCP Inspector to connect to the High-Level server:

```bash
npx @modelcontextprotocol/inspector connect http://localhost:8000/mcp
```

Note: Inspector requests typically do not include `Authorization` headers; use the Python clients above for auth tests.

### Endpoints

- High-Level (FastMCP):
  - `POST /mcp` — JSON‑RPC requests (initialize handled here; server-side session via headers)
  - `GET /mcp` — SSE stream for server notifications (if supported by the client/tooling)
  - `GET /health` — simple health check
- Low-Level:
  - `POST /mcp-low` — Minimal JSON‑RPC with Authorization header passthrough
  - `GET /health` — simple health check

### Context and Authorization: FastMCP vs Low‑Level

- FastMCP (High‑Level): the paywall obtains the context automatically because it is configured with FastMCP's `getContext`. You do not need to pass `extra` to the handler.

```python
# FastMCP: build context automatically via FastMCP.get_context
from mcp.server.fastmcp import FastMCP
from payments_py.payments import Payments

fastmcp = FastMCP(name="weather-mcp", json_response=True)
payments = Payments({"nvm_api_key": NVM_SERVER_API_KEY, "environment": NVM_ENV})

payments.mcp.configure({
    "agentId": NVM_AGENT_ID,
    "serverName": "weather-mcp",
    "getContext": fastmcp.get_context,  # Paywall builds extra from this
})

protected_tool = payments.mcp.with_paywall(
    weather_tool_handler,
    {"kind": "tool", "name": "weather.today", "credits": weather_tool_credits_calculator},
)

# When calling, do NOT pass extra; paywall resolves it from FastMCP context
res = await protected_tool({"city": city})
```

- Low‑Level: you must pass `extra` explicitly to the handler. Typically you capture the request and the `Authorization` header in middleware or directly in the ASGI app and build `extra` with `build_extra_from_http_headers`.

```python
# Low-Level: build extra from HTTP headers and pass it to the handler
from payments_py.mcp import build_extra_from_http_headers

async def asgi_app(scope, receive, send):
    # 1) Collect headers into a dict
    headers_list = scope.get("headers", [])  # List[Tuple[bytes, bytes]]
    headers = {k.decode(): v.decode() for k, v in headers_list}

    # 2) Build extra (contains requestInfo + auth token extraction helpers)
    extra = build_extra_from_http_headers(headers)

    # 3) Route and call a tool handler passing extra as second arg
    result = await protected_tool({"city": "Madrid"}, extra)
    # ... return JSON-RPC result ...
```

In this app, the Low‑Level variant already implements this pattern inside the ASGI (`server_lowlevel.py`): it builds `extra` from the headers and passes it as the second parameter to the handler (`handler(args, extra)`).

Additional note (resources in FastMCP): when invoking a protected resource from FastMCP, you can pass `None` as `extra` and the paywall will resolve the context via the configured `getContext`.

### Acceptance checklist

- List Tools shows `weather.today`
- Calling `weather.today` with `{ "city": "Madrid" }` returns a text summary and a `resource_link` to `weather://today/Madrid`
- Reading that resource returns JSON with the TodayWeather fields

### Notes

- Inspector requests do not include `Authorization`; prefer the demo clients when testing paywall.

## Tutorial: Protecting an MCP server with Nevermined (Paywall + Credits Burn)

This guide shows how to protect your MCP tools with Nevermined so that only subscribed users can access them, and how to burn credits after each call. The Python SDK mirrors the TypeScript flow but with Python naming.

### 1) Initialize Nevermined in your MCP server

```python
import os
from payments_py.payments import Payments

payments = Payments({
    "nvm_api_key": os.environ["NVM_SERVER_API_KEY"],
    "environment": os.environ.get("NVM_ENV", "staging_sandbox"),
})

# Configure paywall defaults once
payments.mcp.configure({
    "agentId": os.environ["NVM_AGENT_ID"],
    "serverName": "weather-mcp",
})
```

### 2) Wrap your handlers with the paywall (works in both servers)

```python
# Your original tool handler
async def my_handler(args):
    return {"content": [{"type": "text", "text": "Hello World"}]}

# Protect it with paywall (single call). Burn 1 credit per call
protected_handler = payments.mcp.with_paywall(
    my_handler,
    {"kind": "tool", "name": "my.namespace.tool", "credits": 1},
)

# Low-Level server
server.registerTool("my.namespace.tool", {"title": "My Tool"}, protected_handler)

# High-Level (FastMCP): call the protected handler from your decorated tool
@fastmcp.tool(name="my.namespace.tool", title="My Tool")
async def _tool(arg: str | None = None) -> str:
    res = await protected_handler({"arg": arg or ""})
    # Extract text content
    for c in (res.get("content") or []):
        if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
            return c["text"]
    return str(res)
```

What the paywall does:

- Extracts `Authorization` from the MCP HTTP headers automatically.
- Validates access with Nevermined.
- If unauthorized, responds with a JSON‑RPC error `-32003` (and suggests plans when possible).
- Runs your handler.
- Burns credits after the call based on the `credits` option.

### 3) Client side

Use the Nevermined client to obtain an access token and pass it as `Authorization` to your MCP transport.

```python
from payments_py.payments import Payments

subs_payments = Payments({
    "nvm_api_key": os.environ["NVM_API_KEY"],
    "environment": os.environ.get("NVM_ENV", "staging_sandbox"),
})

creds = subs_payments.agents.get_agent_access_token(
    os.environ["NVM_PLAN_ID"], os.environ["NVM_AGENT_ID"],
)
access_token = creds.get("accessToken")

# Send Authorization: Bearer {access_token} in your HTTP client
```

### 4) Error semantics

- Missing token → JSON‑RPC `-32003` (“Authorization required”).
- Invalid/not subscribed → JSON‑RPC `-32003` (“Payment required”, optionally with plan suggestions).
- Network/other errors → JSON‑RPC `-32002`.

### 5) Advanced

- Customize `credits` to a function that receives a context `{ args, result, request }` and returns an `int`.
- Use `payments.mcp.with_paywall` to protect tools, resources, and prompts.

Example: dynamic credits for tool calls (e.g., random 1..10 credits per call):

```python
import random

def dynamic_credits(_ctx):
    return 1 + int(random.random() * 10)

protected = payments.mcp.with_paywall(
    my_handler,
    {"kind": "tool", "name": "my.namespace.tool", "credits": dynamic_credits},
)
```

Example: burn 1 credit for resource reads (manual control, without the paywall wrapper):

```python
from urllib.parse import urlparse

async def resource_handler(uri, variables, extra):
    headers = (extra or {}).get("requestInfo", {}).get("headers", {})
    raw = headers.get("authorization") or headers.get("Authorization")
    if not raw:
        raise {"code": -32003, "message": "Authorization required"}
    token = raw[7:].strip() if raw.startswith("Bearer ") else raw

    logical_url = f"mcp://weather-mcp/resources/weather-today?city={variables.get('city', [''])[0]}"
    agent_id = os.environ["NVM_AGENT_ID"]

    start = payments.requests.start_processing_request(agent_id, token, logical_url, "GET")
    if not (start or {}).get("balance", {}).get("isSubscriber"):
        raise {"code": -32003, "message": "Payment required"}

    # ... build the JSON body for the resource ...
    body = {"ok": True}

    payments.requests.redeem_credits_from_request(start["agentRequestId"], token, 1)
    return {"contents": [{"uri": uri.geturl(), "mimeType": "application/json", "text": json.dumps(body)}]}
```

In most cases, prefer the `with_paywall` wrapper which authenticates and redeems for you and supports streaming (async iterables).

# Weather MCP Python
