from dataclasses import dataclass


@dataclass
class TodayWeather:
    """
    Data model with a minimal snapshot of today's weather.

    Attributes
    ----------
    city : str
        City name.
    country : str | None
        Country code if known.
    timezone : str | None
        Timezone identifier.
    tmaxC : float | None
        Expected maximum temperature in Celsius degrees.
    tminC : float | None
        Expected minimum temperature in Celsius degrees.
    precipitationMm : float | None
        Precipitation in millimeters.
    weatherText : str | None
        Human-readable weather summary.
    """

    city: str
    country: str | None = None
    timezone: str | None = None
    tmaxC: float | None = None
    tminC: float | None = None
    precipitationMm: float | None = None
    weatherText: str | None = None


def sanitize_city(city: str) -> str:
    """
    Normalize a user-provided city string.

    Parameters
    ----------
    city : str
        Raw city input.

    Returns
    -------
    str
        Trimmed and title-cased city name.
    """
    return (city or "").strip().title()


def get_today_weather(city: str) -> TodayWeather:
    """
    Get a mocked snapshot of today's weather for a city.

    Parameters
    ----------
    city : str
        City name (already sanitized).

    Returns
    -------
    TodayWeather
        Synthetic weather data used for demonstration/testing.
    """
    return TodayWeather(
        city=city,
        country="ES",
        timezone="Europe/Madrid",
        tmaxC=30.0,
        tminC=18.0,
        precipitationMm=0.0,
        weatherText="Sunny",
    )
