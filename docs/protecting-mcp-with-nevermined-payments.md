## **Protecting an MCP Server with Nevermined Payments (Python)**

This step-by-step guide will walk you through protecting a Model Context Protocol (MCP) server using the `payments-py` library from Nevermined.
We’ll start with a simple server built with **FastMCP** and progressively integrate the **Nevermined paywall** to protect tools, resources, and prompts — including **credit calculation and burning per call**.

The guide is based on the example project `weather-mcp` and the MCP integration included in `payments-py`.

---

### **What is MCP?**

As Large Language Models (LLMs) and AI agents become more sophisticated, their greatest limitation is their isolation. By default, they lack access to real-time information, private data sources, or the ability to perform actions in the outside world. The Model Context Protocol (MCP) was designed to solve this problem by creating a standardized communication layer for AI.

Think of MCP as a universal language that allows any AI agent to ask a server, "What can you do?" and "How can I use your capabilities?". It turns a closed-off model into an agent that can interact with the world through a secure and discoverable interface. An MCP server essentially publishes a "menu" of its services, which can include:

*   **Tools**: These are concrete actions the agent can request, like sending an email, querying a database, or fetching a weather forecast. The agent provides specific arguments (e.g., `city="Paris"`) and the server executes the action.
*   **Resources**: These are stable pointers to data, identified by a URI. While a tool call might give a human-readable summary, a resource link (`weather://today/Paris`) provides the raw, structured data (like a JSON object) that an agent can parse and use for further tasks.
*   **Prompts**: These are pre-defined templates that help guide an agent's behavior, ensuring it requests information in the correct format or follows a specific interaction pattern.

---

### **Why integrate MCP with Nevermined Payments?**

While MCP provides a powerful standard for *what* an AI agent can do, it doesn't specify *who* is allowed to do it or *how* those services are paid for. This is where Nevermined Payments comes in. By integrating Nevermined, you can transform your open MCP server into a secure, monetizable platform.

The core idea is to place a "paywall" in front of your MCP handlers. This paywall acts as a gatekeeper, intercepting every incoming request to a tool, resource, or prompt. Before executing your logic, it checks the user's `Authorization` header to verify they have a valid subscription and sufficient credits through the Nevermined protocol. If they don't, the request is blocked. If they do, the request proceeds, and after your handler successfully completes, the paywall automatically deducts the configured number of credits.

This integration allows you to build a sustainable business model around your AI services. You can offer different subscription tiers (plans), charge dynamically based on usage, and maintain a complete audit trail of every transaction, all without cluttering your core application logic with complex payment code.

---

### **Step-by-step tutorial**

In this tutorial, we will embark on a practical journey to build a secure, monetizable MCP server. Our starting point will be a standard, unprotected server built with FastMCP—a common scenario for developers who have already created useful AI tools and now wish to commercialize them. From there, we will layer on the security and monetization capabilities of Nevermined Payments step by step.

We will focus on the server-side integration, showing you how to instantiate the `payments-py` library, configure it for MCP, and wrap your existing tool handlers with the `with_paywall` decorator to enforce access control. We'll also cover how to set up both fixed and dynamic credit costs for your tools. By the end, you'll have a clear blueprint for protecting any MCP-based service.

---

## **0) Requirements**

*   Python >= 3.10
*   FastMCP (`mcp` package) + Uvicorn
*   `payments-py` (Nevermined SDK)

Install:

```bash
pip install mcp uvicorn python-dotenv
pip install -e payments-py
```

Environment variables (server side):

```bash
export NVM_API_KEY=...            # Builder/agent owner API key
export NVM_AGENT_ID=did:nv:...    # Agent ID registered in Nevermined
export NVM_ENV=sandbox            # or live
```

For testing as a **subscriber**:

```bash
export NVM_API_KEY=...            # Subscriber's API key
export NVM_PLAN_ID=...            # Subscription plan ID
export NVM_AGENT_ID=did:nv:...    # Agent ID linked to plan
```

---

## **1) Create a minimal MCP server with FastMCP**

This first snippet sets up a minimal FastMCP server that exposes a single tool, `weather.today`, without any paywall. We're starting simple to verify the basic MCP plumbing works. FastMCP's decorators make it easy to register tools. We'll also set `json_response=True` to make testing with generic HTTP clients simpler.

```python
# app_fastmcp.py
import os
from mcp.server.fastmcp import FastMCP

# Create a FastMCP instance. The name will appear in MCP initialize responses.
# json_response=True makes it easier to test with generic HTTP clients.
fastmcp = FastMCP(name="weather-mcp", json_response=True)

@fastmcp.tool(name="weather.today", title="Today's Weather")
async def weather_today(city: str) -> str:
    # This is a plain FastMCP tool handler returning a simple string result.
    # In a real app, you would call a weather service here.
    return f"Weather for {city}: Sunny, 25C."

if __name__ == "__main__":
    # Run with: uvicorn app_fastmcp:fastmcp.app --host 127.0.0.1 --port 8000
    pass
```

Run:

```bash
uvicorn app_fastmcp:fastmcp.app --host 127.0.0.1 --port 8000
```

---

## **2) Initialize Nevermined Payments**

Now, let's initialize the Nevermined Payments SDK. This requires your builder/agent owner API key and the environment, which can be `sandbox` for testing or `live` for production.

```python
# payments_setup.py
import os
from payments_py.payments import Payments

payments = Payments({
    "nvm_api_key": os.environ["NVM_API_KEY"],
    "environment": os.environ.get("NVM_ENV", "sandbox"), # or live
})

# Later in FastMCP:
# payments.mcp.configure({
#     "agentId": os.environ["NVM_AGENT_ID"],
#     "serverName": "weather-mcp",
#     "getContext": fastmcp.get_context,
# })
```

---

## **3) Wrap handlers with the paywall**

This decorator checks authentication, executes your logic, and burns credits.

Next, we'll create the handler that contains our core business logic. It's important to keep payment logic separate from the business logic. This handler will return a standard MCP `content` object, including a `resource_link` that points to more detailed data. We'll also define a simple, fixed-cost credit calculator, though this could be a dynamic function.

```python
# handlers.py
from typing import Any, Dict

async def weather_tool_handler(args: Dict[str, Any]) -> Dict[str, Any]:
    # Extract arguments in a robust way. Validate/sanitize in real apps.
    city = str(args.get("city", "")).strip() or "Madrid"

    # Build a human-friendly summary and a resource link pointing to the raw JSON.
    text = f"Weather for {city}: Sunny, 25C."
    return {
        "content": [
            {"type": "text", "text": text},
            {
                "type": "resource_link",
                "uri": f"weather://today/{city}",
                "name": f"weather today {city}",
                "mimeType": "application/json",
                "description": "Raw JSON for today's weather",
            },
        ]
    }

def credits_calculator(_ctx: Dict[str, Any]) -> int:
    return 1  # fixed cost
```

Here, we wire the Nevermined Payments SDK into our FastMCP application. The key step is `payments.mcp.configure`, where we provide the `agentId`, a `serverName`, and—most critically—the `getContext` function from our FastMCP instance. This allows the paywall to automatically access HTTP headers (`Authorization`) for each request. The `with_paywall` function then wraps our original handler, returning a new, protected version. The FastMCP tool calls this protected handler and adapts its dictionary-based MCP response back into a simple string for the client.

```python
# app_fastmcp_paywalled.py
from handlers import weather_tool_handler, credits_calculator
from mcp.server.fastmcp import FastMCP
from payments_py.payments import Payments
import os

fastmcp = FastMCP(name="weather-mcp", json_response=True)

payments = Payments({
    "nvm_api_key": os.environ["NVM_API_KEY"],
    "environment": os.environ.get("NVM_ENV", "sandbox"),
})

payments.mcp.configure({
    "agentId": os.environ["NVM_AGENT_ID"],   # Your Nevermined Agent ID
    "serverName": "weather-mcp",             # Logical name used for auth context
    "getContext": fastmcp.get_context,        # Critical: lets paywall access headers
})


protected_weather = payments.mcp.with_paywall(
    weather_tool_handler,
    {"kind": "tool", "name": "weather.today", "credits": credits_calculator},
)

@fastmcp.tool(name="weather.today", title="Today's Weather")
async def weather_today(city: str) -> str:
    # Call the protected handler passing the tool args as a dict
    result = await protected_weather({"city": city})

    # Extract the first text content for a simple FastMCP response
    for part in (result.get("content") or []):
        if isinstance(part, dict) and part.get("type") == "text":
            return str(part.get("text"))
    # Fallback: stringify the full result if no text content is available
    return str(result)
```

---

## **4) Dynamic credit calculation**

For more flexible pricing, you can provide a function instead of a fixed integer for the `credits` option. This function receives a context dictionary (`ctx`) containing the request arguments, the handler's result, and authentication metadata. This allows you to implement any custom pricing logic, such as charging based on input size or features used.

```python
# dynamic_credits.py
from typing import Any, Dict

def dynamic_credits(ctx: Dict[str, Any]) -> int:
    city = str((ctx.get("args") or {}).get("city", ""))
    return 1 if len(city) <= 5 else 2

# protected_dynamic = payments.mcp.with_paywall(
#     weather_tool_handler,
#     {"kind": "tool", "name": "weather.today", "credits": dynamic_credits},
# )
```

---

## **5) Protecting Resources & Prompts**

The same `with_paywall` pattern applies to resources and prompts.

```python
# protected_resource = payments.mcp.with_paywall(
#     my_resource_handler,
#     {"kind": "resource", "name": "weather-today", "credits": dynamic_credits}
# )

# protected_prompt = payments.mcp.with_paywall(
#     my_prompt_handler,
#     {"kind": "prompt", "name": "weather.ensureCity", "credits": 0}
# )
```

---

## **Alternative: Custom ASGI Low‑Level MCP server**

If you prefer full control, you can implement an ASGI app that:

-   Parses JSON‑RPC requests at a custom path (e.g., `/mcp-low`).
-   Captures HTTP headers (especially `Authorization`).
-   Builds the `extra` metadata using `build_extra_from_http_headers`.
-   Passes `extra` as the second parameter to protected handlers (`handler(args, extra)` for tools).

This example demonstrates a minimal low-level MCP router using a custom ASGI application. This approach gives you full control over the server logic but requires more boilerplate than FastMCP. The key steps are: 1) route requests by path, 2) read the request body, 3) parse the JSON-RPC envelope, 4) build an `extra` dictionary from the HTTP headers, and 5) call the appropriate handler, passing `extra` as the second argument. This final step is critical, as it provides the paywall with the necessary authentication information.

```python
# server_lowlevel_custom.py
import json
from typing import Any, Dict, Callable

from payments_py.mcp import build_extra_from_http_headers

# Assume this dict is populated with handlers wrapped by payments.mcp.with_paywall
PROTECTED_TOOLS: Dict[str, Callable[..., Any]] = {
    # "weather.today": protected_weather_handler,
}

async def app(scope, receive, send):
    assert scope["type"] == "http"

    # 1) Basic routing by path
    path = scope.get("path", "/")
    if path != "/mcp-low":
        await _send_json(send, 404, {"error": "not found"})
        return

    # 2) Read the full request body
    body = b""
    while True:
        event = await receive()
        if event["type"] == "http.request":
            body += event.get("body", b"")
            if not event.get("more_body"):
                break

    # 3) Parse JSON-RPC envelope
    try:
        req = json.loads(body.decode("utf-8"))
    except Exception:
        await _send_json(send, 400, {"error": "invalid json"})
        return

    # 4) Build "extra" from HTTP headers (Authorization, etc.)
    headers = {k.decode(): v.decode() for k, v in scope.get("headers", [])}
    extra = build_extra_from_http_headers(headers)

    # 5) Handle supported methods (expand as needed)
    method = req.get("method")
    if method == "tools/call":
        params = req.get("params") or {}
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        handler = PROTECTED_TOOLS.get(tool_name)
        if not handler:
            await _send_json(send, 404, {"error": f"tool not found: {tool_name}"})
            return

        # Critical: pass extra as second argument so paywall can authenticate and redeem credits
        result = await handler(arguments, extra)
        await _send_json(send, 200, {"jsonrpc": "2.0", "id": req.get("id"), "result": result})
        return

    # Add branches for: initialize, tools/list, resources/read, prompts/list, etc.
    await _send_json(send, 400, {"error": f"unsupported method: {method}"})


async def _send_json(send, status: int, payload: Dict[str, Any]):
    data = json.dumps(payload).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": status,
        "headers": [(b"content-type", b"application/json")],
    })
    await send({"type": "http.response.body", "body": data})
```

---

## **6) Client: getting access & calling**

**6.1 Get `accessToken`:**

```python
# get_access_token.py
import os
from payments_py.payments import Payments

subscriber = Payments({
    "nvm_api_key": os.environ["NVM_API_KEY"],
    "environment": os.environ.get("NVM_ENV", "sandbox"), # or live
})

creds = subscriber.agents.get_agent_access_token(
    os.environ["NVM_PLAN_ID"], os.environ["NVM_AGENT_ID"],
)
print(creds.get("accessToken"))
```

**6.2 Call a tool:**

This client-side example demonstrates how a subscriber calls the protected MCP endpoints. The process always involves sending the `Authorization: Bearer <accessToken>` header. A typical interaction flow is `initialize`, followed by `tools/list` to discover capabilities, and finally `tools/call` to execute a tool. Optionally, a `resources/read` call can be made to fetch detailed data.

```python
# client_call_tool.py
import os
import requests

BASE_URL = os.environ.get("MCP_BASE_URL", "http://localhost:8000")
ACCESS_TOKEN = creds.get("accessToken")

def rpc(method, params, id_):
    r = requests.post(
        f"{BASE_URL}/mcp",
        json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params},
        headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    r.raise_for_status()
    return r.json()

# 1) initialize
print(rpc("initialize", {}, 1))

# 2) tools/list
print(rpc("tools/list", {}, 2))

# 3) tools/call -> weather.today
print(rpc("tools/call", {"name": "weather.today", "arguments": {"city": "Madrid"}}, 3))
```

---

## **Error handling**

*   **No token / Invalid token** → `-32003` (“Authorization required”)
*   **Other errors** → `-32002`
