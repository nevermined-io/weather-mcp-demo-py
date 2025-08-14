"""Low-level CLI mirroring the TypeScript client-low-level.ts.

Performs raw JSON-RPC HTTP requests using requests, after negotiating an
Agent access token via Nevermined Payments if credentials are available.
"""

from typing import Optional, Dict, Any
import os
import json
import requests
from payments_py.payments import Payments


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Helper to read environment variables with a default value."""
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def _headers(access_token: Optional[str]) -> Dict[str, str]:
    """Build HTTP headers for JSON-RPC calls."""
    base = {"Content-Type": "application/json"}
    if access_token:
        base["Authorization"] = f"Bearer {access_token}"
    return base


def main() -> None:
    """Entrypoint for the low-level client."""
    endpoint = _get_env("MCP_LOW_ENDPOINT", "http://localhost:8000/mcp-low")
    city = _get_env("MCP_CITY", "Madrid") or "Madrid"
    plan_id = _get_env("NVM_PLAN_ID")
    agent_id = _get_env("NVM_AGENT_ID")
    nvm_api_key = _get_env("NVM_API_KEY")
    environment = _get_env("NVM_ENV", "staging_sandbox") or "staging_sandbox"

    access_token: Optional[str] = None
    before_balance: Optional[int] = None

    # Negotiate token similar to TS low-level
    if nvm_api_key and plan_id and agent_id:
        payments = Payments({"environment": environment, "nvm_api_key": nvm_api_key})
        try:
            bal = payments.plans.get_plan_balance(plan_id)
            before_balance = int(bal.get("balance") or 0)
            is_subscriber = bool(bal.get("isSubscriber") or bal.get("is_subscriber"))
            if not is_subscriber or before_balance <= 0:
                print("Ordering plan because there is no balance or not subscribed...")
                payments.plans.order_plan(plan_id)
            else:
                print(f"Before balance: {before_balance} (subscriber: {is_subscriber})")
        except Exception as e:
            print(f"Unable to get balance. Attempting to order plan... {e}")
            try:
                payments.plans.order_plan(plan_id)
                bal2 = payments.plans.get_plan_balance(plan_id)
                before_balance = int(bal2.get("balance") or 0)
                print(
                    f"Before balance: {before_balance} (subscriber: {bool(bal2.get('isSubscriber') or bal2.get('is_subscriber'))})"
                )
            except Exception as e2:
                print(f"Order plan failed: {e2}")

        try:
            creds = payments.agents.get_agent_access_token(plan_id, agent_id)
            access_token = creds.get("accessToken")
        except Exception as e:
            print(f"Unable to get agent access token: {e}")

    # 1) Initialize
    init_payload: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"protocolVersion": "2024-11-05", "capabilities": {}},
    }
    init_res = requests.post(endpoint, headers=_headers(access_token), json=init_payload)
    init_data = init_res.json()
    if init_data.get("error"):
        print("Initialize error:", json.dumps(init_data))
        return
    print("Initialized:", json.dumps(init_data))

    # 2) tools/call
    payload: Dict[str, Any] = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": "weather.today", "arguments": {"city": city}},
    }
    res = requests.post(endpoint, headers=_headers(access_token), json=payload)
    data = res.json()
    print("LowLevel result:", json.dumps(data))

    # After balances
    if access_token and plan_id and nvm_api_key:
        try:
            payments = Payments({"environment": environment, "nvm_api_key": nvm_api_key})
            after = payments.plans.get_plan_balance(plan_id)
            after_balance = int(after.get("balance") or 0)
            print(f"After balance: {after_balance}")
            if before_balance is not None:
                delta = before_balance - after_balance
                print(f"Credits burned (approx): {delta}")
        except Exception as e:
            print(f"Unable to get after balance: {e}")


if __name__ == "__main__":
    main()
