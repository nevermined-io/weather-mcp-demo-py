from typing import Any, Dict

from services.weather_service import sanitize_city


def weather_prompt_handler(args: Dict[str, Any], _extra: Any | None = None) -> Dict[str, Any]:
    """
    Build a prompt message instructing the client to call the weather tool.

    Parameters
    ----------
    args : Dict[str, Any]
        Prompt arguments. May include the "city" parameter to prefill the suggestion.
    _extra : Any | None, optional
        Extra authentication and request metadata, provided by the payments integration.

    Returns
    -------
    Dict[str, Any]
        MCP prompt response with a single user message.
    """
    city = sanitize_city(str(args.get("city", "")))
    return {
        "messages": [
            {
                "role": "user",
                "content": {
                    "type": "text",
                    "text": f"Please call the tool weather.today with {{ \"city\": \"{city}\" }}",
                },
            }
        ]
    }


