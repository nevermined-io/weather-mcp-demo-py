from typing import Any, Dict

from services.weather_service import get_today_weather, sanitize_city


async def weather_tool_handler(args: Dict[str, Any], _extra: Any | None = None) -> Dict[str, Any]:
    """
    Handle the MCP tool call for today's weather summary.

    Parameters
    ----------
    args : Dict[str, Any]
        Tool arguments. Must include the "city" string parameter.
    _extra : Any | None, optional
        Extra authentication and request metadata, provided by the payments integration.

    Returns
    -------
    Dict[str, Any]
        MCP tool response including a human-readable summary and a resource link.
    """
    city = sanitize_city(str(args.get("city", "")))
    weather = get_today_weather(city)
    text = (
        f"Weather for {weather.city}, {weather.country or ''} (tz: {weather.timezone})\n"
        f"High: {weather.tmaxC or 'n/a'}°C, Low: {weather.tminC or 'n/a'}°C, "
        f"Precipitation: {weather.precipitationMm or 'n/a'}mm, "
        f"Conditions: {weather.weatherText or 'n/a'}"
    )
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


def weather_tool_credits_calculator(_ctx: Dict[str, Any]) -> int:
    """
    Compute the number of credits required for the weather tool.

    Parameters
    ----------
    _ctx : Dict[str, Any]
        Execution context for the call. Unused in this demo implementation.

    Returns
    -------
    int
        A small pseudo-random credit cost in the range 5..14.
    """
    import random

    return 5 + int(random.random() * 10)


