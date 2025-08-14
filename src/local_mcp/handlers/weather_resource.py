from typing import Any, Dict
import json

from services.weather_service import get_today_weather, sanitize_city


async def weather_resource_handler(_uri: Any, variables: Dict[str, Any], _extra: Any | None = None) -> Dict[str, Any]:
    """
    Build the resource contents for today's weather.

    Parameters
    ----------
    _uri : Any
        Parsed URI of the requested resource. Unused in this demo implementation.
    variables : Dict[str, Any]
        Variables extracted from the resource template, expected to contain a "city" entry.
    _extra : Any | None, optional
        Extra authentication and request metadata, provided by the payments integration.

    Returns
    -------
    Dict[str, Any]
        MCP resource response with the JSON content of today's weather.
    """
    raw = variables.get("city")
    city_param = raw[0] if isinstance(raw, list) and raw else raw
    try:
        decoded = str(city_param)
    except Exception:
        decoded = city_param
    sanitized = sanitize_city(decoded)
    weather = get_today_weather(sanitized)
    return {
        "contents": [
            {
                "uri": f"weather://today/{sanitized}",
                "text": json.dumps(weather.__dict__),
                "mimeType": "application/json",
            }
        ]
    }


