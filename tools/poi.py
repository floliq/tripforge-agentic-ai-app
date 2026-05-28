from dotenv import load_dotenv
import os
import httpx
from langchain.tools import tool
from models import PoiDetails, PoiItem, PoiResults

load_dotenv()

@tool
def search_poi(
    lat: float,
    lon: float,
    radius: int,
    interests: list[str],
    limit: int = 10,
) -> PoiResults:
    """Search for points of interest (POI) around a given location using OpenTripMap."""
    print(
        f" starting search poi: lat={lat}, lon={lon}, radius={radius}, interests={interests}, limit={limit}"
    )
    params = {
        "radius": radius,
        "lon": lon,
        "lat": lat,
        "limit": limit,
        "apikey": os.getenv("OPENTRIPMAP_API_KEY"),
    }
    if interests:
        params["kinds"] = ",".join(interests)

    response = httpx.get(
        "https://api.opentripmap.com/0.1/en/places/radius",
        params=params,
    )
    if response.status_code != 200:
        raise Exception(f"Failed to search poi: {response.status_code}")
    features = response.json().get("features", [])
    if not features:
        raise Exception(f"No results found for poi: {lat}, {lon}, {radius}, {interests}")

    items: list[PoiItem] = []
    for feature in features:
        properties = feature.get("properties", {})
        xid = properties.get("xid")
        if not xid:
            continue

        items.append(
            PoiItem(
                xid=xid,
                name=properties.get("name", ""),
                dist=float(properties.get("dist", 0.0)),
                kinds=properties.get("kinds", "").split(",")
                if properties.get("kinds")
                else [],
            )
        )

    if not items:
        raise Exception(f"No valid POI found for poi: {lat}, {lon}, {radius}, {interests}")

    return PoiResults(
        items=items
    )

@tool
def get_poi_details(xid: str) -> PoiDetails:
    """Get details for a point of interest (POI) using OpenTripMap."""
    print(f" starting get poi details: xid={xid}")
    response = httpx.get(
        f"https://api.opentripmap.com/0.1/en/places/xid/{xid}",
        params={"apikey": os.getenv("OPENTRIPMAP_API_KEY")})
    if response.status_code != 200:
        raise Exception(f"Failed to get poi details: {response.status_code}")
    data = response.json()
    point = data.get("point", {})
    address_data = data.get("address", {})
    address_parts = [
        address_data.get("road"),
        address_data.get("house_number"),
        address_data.get("suburb"),
        address_data.get("city"),
        address_data.get("state"),
        address_data.get("country"),
        address_data.get("postcode"),
    ]
    address = ", ".join(str(part) for part in address_parts if part)

    return PoiDetails(
        name=data.get("name", ""),
        description=data.get("wikipedia_extracts", {}).get("text"),
        wikipedia_url=data.get("wikipedia"),
        address=address or None,
        coordinates=[float(point.get("lat", 0.0)), float(point.get("lon", 0.0))]
    )

#print(search_poi(52.4238936, 31.0131698, 1000, ["cultural"], limit=5))
#print(get_poi_details("W64946710"))