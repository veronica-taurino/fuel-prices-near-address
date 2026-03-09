# -*- coding: utf-8 -*-
# SPDX-License-Identifier: MPL-2.0
"""
Find fuel stations and prices near a French address (2aaz API + BAN geocoding).

Uses:
- 2aaz API (prix-carburants) for fuel stations and prices in France
- BAN (Base Adresse Nationale) for geocoding addresses

Requirements: requests
Usage: Set ADDRESS in the script to your default, or leave the placeholder to be prompted at runtime.

Author: Veronica Taurino, 2026-03-08
"""

__version__ = "0.1.0"

from datetime import datetime, timedelta
import math
import sys
from typing import Any, Dict, List, Optional, Tuple
import requests

# =========================
# Configuration
# =========================

# Address: replace with yours or leave the placeholder to be prompted at runtime
ADDRESS_PLACEHOLDER = "XXX, chemin de chemin, Nice"
ADDRESS = "XXX, chemin de chemin, Nice"
# Filter: only show stations with fuel data updated in the last N days
DAYS_SINCE_LAST_UPDATE = 1
# Fuel type to highlight (gazole, sp95, sp95-e10, sp98, e85, gplc)
FAV_FUEL_TYPE = "gazole"
# Search radius in km (API allows max 10 km)
RADIUS_KM = 10.0
TIMEOUT = 20
# Set True to print all fuel types returned by the API (debug)
DEBUG = True

# API endpoints
API_BASE_URL = "https://api.prix-carburants.2aaz.fr"
BAN_SEARCH_URL = "https://api-adresse.data.gouv.fr/search/"

FUEL_LABELS = {
    "gazole": "Diesel",
    "sp95": "Petrol 95",
    "sp95-e10": "Petrol 95 E10",
    "sp98": "Petrol 98",
    "e85": "Ethanol E85",
    "gplc": "LPG",
}

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute great-circle distance between two GPS points in kilometers."""
    earth_radius_km = 6371.0

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return earth_radius_km * c

def geocode_address(address: str) -> Tuple[float, float, str]:
    """Convert a postal address into (lat, lon, label) using BAN (French national address database)."""
    params = {
        "q": address,
        "limit": 1,
    }

    response = requests.get(BAN_SEARCH_URL, params=params, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()
    features = data.get("features", [])
    if not features:
        raise ValueError(f"Address not found: {address}")

    feature = features[0]
    coordinates = feature["geometry"]["coordinates"]  # [lon, lat]
    label = feature["properties"].get("label", address)

    lon, lat = coordinates[0], coordinates[1]
    return lat, lon, label

def fetch_stations_around(lat: float, lon: float) -> List[Dict[str, Any]]:
    """Query 2aaz API for fuel stations around (lat, lon). Returns list of raw station objects."""
    url = (
        f"{API_BASE_URL}/stations/around/{lat},{lon}"
        "?responseFields=Fuels,Hours,Services,Price"
    )
    
    response = requests.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    data = response.json()

    if isinstance(data, list):
        return data

    for key in ("results", "stations", "items", "data"):
        value = data.get(key)
        if isinstance(value, list):
            return value

    raise ValueError("Unexpected API response format.")

def extract_station_coordinates(station: Dict[str, Any]) -> Optional[Tuple[float, float]]:
    """Extract station coordinates from the API response."""
    coords = station.get("Coordinates")
    if isinstance(coords, dict):
        try:
            return float(coords["latitude"]), float(coords["longitude"])
        except (KeyError, TypeError, ValueError):
            pass

    candidates = [
        ("latitude", "longitude"),
        ("lat", "lon"),
        ("lat", "lng"),
    ]

    for lat_key, lon_key in candidates:
        if lat_key in station and lon_key in station:
            try:
                return float(station[lat_key]), float(station[lon_key])
            except (TypeError, ValueError):
                pass

    location = station.get("location")
    if isinstance(location, dict):
        for lat_key, lon_key in candidates:
            if lat_key in location and lon_key in location:
                try:
                    return float(location[lat_key]), float(location[lon_key])
                except (TypeError, ValueError):
                    pass

    geometry = station.get("geometry")
    if isinstance(geometry, dict):
        coordinates = geometry.get("coordinates")
        if isinstance(coordinates, (list, tuple)) and len(coordinates) >= 2:
            try:
                lon, lat = float(coordinates[0]), float(coordinates[1])
                return lat, lon
            except (TypeError, ValueError):
                pass

    return None

def extract_station_name(station: Dict[str, Any]) -> str:
    """Extract station display name."""
    for key in ("name", "brand", "enseigne", "station", "label"):
        value = station.get(key)
        if value:
            return str(value)
    return "Unknown station"

def extract_station_address(station: Dict[str, Any]) -> str:
    """Extract station address."""
    address_obj = station.get("Address")
    if isinstance(address_obj, dict):
        street = address_obj.get("street_line", "")
        city = address_obj.get("city_line", "")
        full = ", ".join(part for part in [street, city] if part)
        if full:
            return full

    for key in ("address", "adresse", "full_address", "label"):
        value = station.get(key)
        if value:
            return str(value)

    return "Address not available"

def extract_station_brand(station: Dict[str, Any]) -> str:
    """Extract station brand name if available."""
    brand_obj = station.get("Brand")
    if isinstance(brand_obj, dict):
        brand_name = brand_obj.get("name")
        if brand_name:
            return str(brand_name)
    return "Unknown brand"

def extract_fuels(station: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract fuels list."""
    fuels = station.get("Fuels")
    return fuels if isinstance(fuels, list) else []

def extract_distance_km(station: Dict[str, Any], ref_lat: float, ref_lon: float, coords: Optional[Tuple[float, float]] = None) -> Optional[float]:
    """Extract station distance in kilometers, using API value when available."""
    distance_m = station.get("distance")
    if isinstance(distance_m, (int, float)):
        return float(distance_m) / 1000.0

    distance_obj = station.get("Distance")
    if isinstance(distance_obj, dict):
        value = distance_obj.get("value")
        if isinstance(value, (int, float)):
            return float(value) / 1000.0

    if coords is None:
        coords = extract_station_coordinates(station)
        if coords is None:
            return None

    lat, lon = coords
    return haversine_km(ref_lat, ref_lon, lat, lon)

def normalize_station(station: Dict[str, Any], ref_lat: float, ref_lon: float) -> Optional[Dict[str, Any]]:
    """Build a normalized station record."""
    
    coords = extract_station_coordinates(station)
    if coords is None:
        return None

    distance_km = extract_distance_km(station, ref_lat, ref_lon, coords)
    if distance_km is None:
        return None

    lat, lon = coords

    return {
        "id": station.get("id"),
        "name": extract_station_name(station),
        "brand": extract_station_brand(station),
        "address": extract_station_address(station),
        "latitude": lat,
        "longitude": lon,
        "distance_km": distance_km,
        "fuels": extract_fuels(station),
        "raw": station,
    }

def extract_fuel_price(station: Dict[str, Any], fuel_type: str) -> Optional[float]:
    """Extract the selected fuel price value if available."""
    target = fuel_type.strip().lower()

    for fuel in station.get("fuels", []):
        short_name = str(fuel.get("shortName", "")).strip().lower()
        name = str(fuel.get("name", "")).strip().lower()

        if short_name == target or name == target:
            price_obj = fuel.get("Price")
            if isinstance(price_obj, dict):
                value = price_obj.get("value")
                if isinstance(value, (int, float)):
                    return float(value)
    return None

def extract_fuel_update(station: Dict[str, Any], fuel_type: str) -> Optional[str]:
    """Extract the selected fuel last update text if available."""
    target = fuel_type.strip().lower()

    for fuel in station.get("fuels", []):
        short_name = str(fuel.get("shortName", "")).strip().lower()
        name = str(fuel.get("name", "")).strip().lower()

        if short_name == target or name == target:
            update_obj = fuel.get("Update")
            if isinstance(update_obj, dict):
                return update_obj.get("text")
    return None

def extract_fuel_price_text(fuels: List[Dict[str, Any]], fuel_type: str) -> str:
    """Return formatted price text for the selected fuel, or '-' if missing."""
    target = fuel_type.strip().lower()

    for fuel in fuels:
        short_name = str(fuel.get("shortName", "")).strip().lower()
        name = str(fuel.get("name", "")).strip().lower()

        if short_name == target or name == target:
            price_obj = fuel.get("Price")
            value = price_obj.get("value") if isinstance(price_obj, dict) else None
            if isinstance(value, (int, float)):
                return f"{value:.3f}"
            return "-"

    return "-"

def format_update_short(update_text: Optional[str]) -> str:
    """Return update text in short format DD/MM HH:MM."""
    if not update_text:
        return "-"

    try:
        update_dt = datetime.strptime(update_text, "%d/%m/%Y %H:%M:%S")
        return update_dt.strftime("%d/%m %H:%M")
    except ValueError:
        return update_text

def build_station_table_row(station: Dict[str, Any], fuel_update: Optional[str]) -> str:
    """Build one aligned table row for the station."""
    fuels = station["fuels"]

    return (
        f"{station['distance_km']:<7.2f} "
        f"{format_update_short(fuel_update):<18} "
        f"{extract_fuel_price_text(fuels, 'gazole'):<8} "
        f"{extract_fuel_price_text(fuels, 'sp95'):<7} "
        f"{extract_fuel_price_text(fuels, 'sp95-e10'):<7} "
        f"{extract_fuel_price_text(fuels, 'sp98'):<7} "
        f"{extract_fuel_price_text(fuels, 'e85'):<7} "
        f"{extract_fuel_price_text(fuels, 'gplc'):<6} "
        f"{station['name']}"
    )

def is_recent_update(update_text: Optional[str], days: int) -> bool:
    """Return True if update_text is within the last `days` days."""
    if not update_text:
        return False
    try:
        update_dt = datetime.strptime(update_text, "%d/%m/%Y %H:%M:%S")
        return update_dt >= datetime.now() - timedelta(days=days)
    except ValueError:
        return False

def main() -> None:
    """Run the nearby fuel stations search."""
    if ADDRESS.strip() == ADDRESS_PLACEHOLDER or not ADDRESS.strip():
        address = input("Enter address: ").strip()
    else:
        address = ADDRESS.strip()
    if not address:
        print("Error: address is required.", file=sys.stderr)
        sys.exit(1)

    try:
        lat, lon, resolved_address = geocode_address(address)
    except requests.RequestException as e:
        print(f"Geocoding failed: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    print(f"Resolved address: {resolved_address}")
    print(f"Coordinates: {lat}, {lon}")
    print()

    try:
        stations = fetch_stations_around(lat, lon)
    except requests.RequestException as e:
        print(f"Failed to fetch stations: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    normalized = []
    for station in stations:
        item = normalize_station(station, lat, lon)
        if item is not None and item["distance_km"] <= RADIUS_KM:
            normalized.append(item)

    normalized.sort(key=lambda x: x["distance_km"])

    print(f"Stations within {RADIUS_KM:.1f} km: {len(normalized)}")
    print("-" * 110)

    # Debug: list all fuel types returned by the API for this area
    if DEBUG:
        all_fuels = sorted({
            fuel.get("shortName")
            for station in normalized
            for fuel in station.get("fuels", [])
            if fuel.get("shortName")
        })
        print(f"Number of fuel types read: {len(all_fuels)}")
        print(all_fuels)
        print("-" * 110)

    # Keep only stations that have FAV_FUEL_TYPE and were updated recently
    recent_stations = []
    for station in normalized:
        fuel_price = extract_fuel_price(station, FAV_FUEL_TYPE)
        fuel_update = extract_fuel_update(station, FAV_FUEL_TYPE)
        if fuel_price is None:
            continue
        if not is_recent_update(fuel_update, days=DAYS_SINCE_LAST_UPDATE):
            continue
        recent_stations.append((station, fuel_price, fuel_update))
        
    min_fuel_station = None
    min_fuel_price = None
    min_fuel_update = None
    if recent_stations:
        min_fuel_station, min_fuel_price, min_fuel_update = min(
            recent_stations,
            key=lambda item: item[1]
        )
    
    if min_fuel_station is not None:
        print(
            f"Cheapest {FUEL_LABELS[FAV_FUEL_TYPE]}: {min_fuel_station['name']} | "
            f"{min_fuel_station['distance_km']:.2f} km | "
            f"{min_fuel_price:.3f} €/l | "
            f"Updated: {min_fuel_update}"
        )
        print("-" * 110)
    
    for station, fuel_price, fuel_update in recent_stations:
        fuel_text = f"{fuel_price:.3f} €/l"
        print(f"{station['distance_km']:>5.2f} km | {fuel_text:>10} | {fuel_update} | {station['name']}")

    print()
    print("-" * 110)
    print(f"All fuels updated in the last {DAYS_SINCE_LAST_UPDATE} {'days' if DAYS_SINCE_LAST_UPDATE > 1 else 'day'}:")
    print("-" * 110)
    print(f"{'Dist':<7} {'Update':<18} {'Diesel':<8} {'SP95':<7} {'E10':<7} {'SP98':<7} {'E85':<7} {'GPL':<6} Station")
    print(f"{'(km)':<7} {'(DD/MM HH:MM)':<18} {'(€/l)':<8} {'(€/l)':<7} {'(€/l)':<7} {'(€/l)':<7} {'(€/l)':<7} {'(€/l)':<6} ")
    print("-" * 110)

    for station, fuel_price, fuel_update in recent_stations:
        print(build_station_table_row(station, fuel_update))
    
if __name__ == "__main__":
    main()