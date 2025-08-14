"""Command-line demo client mirroring the TypeScript client-demo.ts.

Reads environment variables, ensures plan subscription, obtains an Agent
access token via Nevermined Payments and calls the MCP server using
the high-level MCPHttpClient.
"""

from typing import Optional
import os
import json
from payments_py.payments import Payments
from client import MCPHttpClient


def _get_env(name: str, default: Optional[str] = None) -> Optional[str]:
    """Helper to read environment variables with a default value."""
    val = os.getenv(name)
    return val if val is not None and val != "" else default


def main() -> None:
    """Entrypoint for the demo client."""
    endpoint = _get_env("MCP_BASE_URL", "http://localhost:8000")
    city = _get_env("MCP_CITY", "Madrid") or "Madrid"
    plan_id = _get_env("NVM_PLAN_ID")
    agent_id = _get_env("NVM_AGENT_ID")
    nvm_api_key = _get_env("NVM_API_KEY")
    environment = _get_env("NVM_ENV", "staging_sandbox") or "staging_sandbox"

    access_token: Optional[str] = None
    before_balance: Optional[int] = None

    # Negotiate token similar to TS demo
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

    client = MCPHttpClient(endpoint, token=access_token)

    # 1) Initialize
    init_res = client.initialize()
    print("initialize:", 200, json.dumps(init_res))

    # 2) tools/list
    tools_res = client.list_tools()
    print("tools/list:", 200, json.dumps(tools_res))

    # 3) tools/call (weather.today)
    call_res = client.call_tool("weather.today", {"city": city})
    print("tools/call:", 200, json.dumps(call_res))

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
