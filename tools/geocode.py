import os
import httpx
from langchain.tools import tool
from models import GeocodeResult
from dotenv import load_dotenv

load_dotenv()

@tool
def geocode_city(city: str) -> GeocodeResult:
    """Return latitude and longitude for a city using OpenStreetMap Nominatim."""
    response = httpx.get(
        f"https://nominatim.openstreetmap.org/search?q={city}&format=json&addressdetails=1",
        headers={"User-Agent": os.getenv("NOMINATIM_USER_AGENT")},
    )
    if response.status_code != 200:
        raise Exception(f"Failed to geocode city: {response.status_code}")
    data = response.json()
    if not data:
        raise Exception(f"No results found for city: {city}")
    result = data[0]
    country = data[0].get("address", {}).get("country")
    if not country:
        parts = data[0]["display_name"].split(", ")
        country = parts[-1]
    return GeocodeResult(
        city=city, latitude=result["lat"], longitude=result["lon"], country=country
    )


#print(geocode_city("Rome"))
