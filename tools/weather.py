from datetime import date

import httpx
from langchain.tools import tool

from models import WeatherDay, WeatherResult


# WMO weather interpretation codes (Open-Meteo)
_WEATHER_DESCRIPTIONS: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _weather_description(code: int) -> str:
    return _WEATHER_DESCRIPTIONS.get(code, f"Weather code {code}")


def _fetch_open_meteo(
    lat: float,
    lon: float,
    date_from: date,
    date_to: date,
) -> dict:
    if date_from > date_to:
        raise ValueError("date_from must be on or before date_to")

    base_url = "https://api.open-meteo.com/v1/forecast"

    params = {
        "latitude": lat,
        "longitude": lon,
        "start_date": date_from.isoformat(),
        "end_date": date_to.isoformat(),
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max",
        "timezone": "auto",
    }

    response = httpx.get(base_url, params=params, timeout=30.0)
    if response.status_code != 200:
        raise RuntimeError(
            f"Open-Meteo returned HTTP {response.status_code}: {response.text[:200]}"
        )
    return response.json()


def _build_weather_days(data: dict, date_from: date, date_to: date) -> list[WeatherDay]:
    daily = data.get("daily")
    if not daily or not daily.get("time"):
        raise RuntimeError(
            "Open-Meteo returned no daily forecast for the requested dates"
        )

    days: list[WeatherDay] = []
    for i, day_str in enumerate(daily["time"]):
        day = date.fromisoformat(day_str)
        if day < date_from or day > date_to:
            continue

        t_max = daily["temperature_2m_max"][i]
        t_min = daily["temperature_2m_min"][i]
        temperature = round((t_max + t_min) / 2, 1)
        code = int(daily["weather_code"][i])
        wind = daily["wind_speed_10m_max"][i]

        days.append(
            WeatherDay(
                date=day,
                temperature=temperature,
                description=_weather_description(code),
                wind_speed=wind,
            )
        )

    if not days:
        raise RuntimeError(
            f"No forecast days between {date_from} and {date_to}. "
            "Check that dates are within the API range (forecast ~16 days ahead)."
        )
    return days


@tool
def fetch_weather(
    lat: float,
    lon: float,
    date_from: date,
    date_to: date,
) -> WeatherResult:
    """Fetch daily weather forecast for coordinates and a date range (Open-Meteo).

    Args:
        lat: Latitude from geocode_city.
        lon: Longitude from geocode_city.
        date_from: Start date (YYYY-MM-DD).
        date_to: End date (YYYY-MM-DD), inclusive.
    """
    data = _fetch_open_meteo(lat, lon, date_from, date_to)
    days = _build_weather_days(data, date_from, date_to)
    return WeatherResult(
        latitude=lat,
        longitude=lon,
        date_from=date_from,
        date_to=date_to,
        days_weather=days,
    )


# print(fetch_weather(41.89, 12.49, date(2026, 6, 1), date(2026, 6, 5)))
