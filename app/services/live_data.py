"""Best-effort, source-attributed external data adapters.

These feeds provide weather context and satellite catalogue metadata. They do
not issue flood warnings and do not replace official DHM instructions.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import urlencode
import logging

import requests
from .storage import archive_json_snapshot

logger = logging.getLogger(__name__)
WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
STAC_SEARCH_URL = "https://stac.dataspace.copernicus.eu/v1/search"
CACHE_SECONDS = 900
_cache_lock = Lock()
_cache: dict[str, tuple[datetime, object]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _cache_get(key):
    with _cache_lock:
        item = _cache.get(key)
        if item and _utc_now() - item[0] < timedelta(seconds=CACHE_SECONDS):
            return item[1]
        return None


def _cache_set(key, value):
    with _cache_lock:
        _cache[key] = (_utc_now(), value)


def _number(value, unit=""):
    if value is None:
        return "—"
    try:
        return f"{float(value):g}{unit}"
    except (TypeError, ValueError):
        return "—"


def get_current_weather(locations, testing=False):
    """Return Open-Meteo current modelled weather context for configured sites."""
    if not locations:
        return {"available": False, "checked_at": _utc_now(), "items": [], "message": "No monitoring locations configured."}
    if testing:
        return {"available": False, "checked_at": None, "items": [], "message": "External feeds are disabled during automated tests."}

    key = "open-meteo:" + ",".join(str(location.id) for location in locations)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    latitudes = ",".join(str(location.latitude) for location in locations)
    longitudes = ",".join(str(location.longitude) for location in locations)
    params = {
        "latitude": latitudes,
        "longitude": longitudes,
        "current": "temperature_2m,relative_humidity_2m,precipitation,rain,showers,wind_speed_10m",
        "timezone": "UTC",
        "forecast_days": 1,
    }
    try:
        response = requests.get(WEATHER_URL, params=params, timeout=(2.5, 5))
        response.raise_for_status()
        payload = response.json()
        # Open-Meteo returns an object for one coordinate and a list for many.
        payloads = payload if isinstance(payload, list) else [payload]
        items = []
        for index, location in enumerate(locations):
            record = payloads[index] if index < len(payloads) else {}
            current = record.get("current") or {}
            items.append({
                "location_id": location.id,
                "location_name": location.name,
                "district": location.district,
                "time": current.get("time"),
                "temperature": _number(current.get("temperature_2m"), " °C"),
                "humidity": _number(current.get("relative_humidity_2m"), "%"),
                "precipitation": _number(current.get("precipitation"), " mm"),
                "rain": _number(current.get("rain"), " mm"),
                "showers": _number(current.get("showers"), " mm"),
                "wind": _number(current.get("wind_speed_10m"), " km/h"),
            })
        result = {
            "available": bool(items) and any(item["time"] for item in items),
            "checked_at": _utc_now(),
            "items": items,
            "source_name": "Open-Meteo Forecast API",
            "source_url": "https://open-meteo.com/en/docs",
            "message": "Current modelled weather context; not a river gauge reading or official flood warning.",
        }
        archive_json_snapshot("open-meteo-weather", result)
        _cache_set(key, result)
        return result
    except (requests.RequestException, ValueError, TypeError, IndexError) as exc:
        logger.warning("Open-Meteo request failed: %s", exc)
        result = {
            "available": False,
            "checked_at": _utc_now(),
            "items": [],
            "source_name": "Open-Meteo Forecast API",
            "source_url": "https://open-meteo.com/en/docs",
            "message": "The weather feed is currently unavailable. No live values are being shown.",
        }
        _cache_set(key, result)
        return result


def get_satellite_catalogue(testing=False, days=30, limit=12):
    """Search the public Copernicus Data Space STAC catalogue for Nepal products."""
    if testing:
        return {"available": False, "checked_at": None, "items": [], "message": "External feeds are disabled during automated tests."}
    key = f"copernicus-stac:nepal:{days}:{limit}"
    cached = _cache_get(key)
    if cached is not None:
        return cached

    end = _utc_now()
    start = end - timedelta(days=days)
    payload = {
        "bbox": [80.0, 26.0, 89.5, 31.5],
        "datetime": f"{start.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end.strftime('%Y-%m-%dT%H:%M:%SZ')}",
        "collections": ["sentinel-1-grd", "sentinel-2-l2a"],
        "limit": limit,
    }
    try:
        response = requests.post(STAC_SEARCH_URL, json=payload, timeout=(3, 8))
        response.raise_for_status()
        features = response.json().get("features", [])
        items = []
        for feature in features:
            props = feature.get("properties") or {}
            collection = feature.get("collection") or "Copernicus Sentinel"
            title = props.get("title") or props.get("s2:product_uri") or feature.get("id") or "Satellite product"
            feature_links = feature.get("links") or []
            item_url = next((link.get("href") for link in feature_links if link.get("rel") in ("self", "canonical")), None)
            items.append({
                "id": feature.get("id", ""),
                "title": title,
                "collection": collection,
                "datetime": props.get("datetime") or props.get("start_datetime") or "Unknown",
                "platform": props.get("platform") or props.get("constellation") or "Sentinel",
                "cloud_cover": props.get("eo:cloud_cover"),
                "url": item_url or "https://browser.stac.dataspace.copernicus.eu/",
            })
        result = {
            "available": True,
            "checked_at": _utc_now(),
            "items": items,
            "source_name": "Copernicus Data Space STAC catalogue",
            "source_url": "https://stac.dataspace.copernicus.eu/v1/",
            "message": "Catalogue metadata only. These results are not processed flood maps or confirmed flood detections.",
        }
        archive_json_snapshot("copernicus-satellite-catalogue", result)
        _cache_set(key, result)
        return result
    except (requests.RequestException, ValueError, TypeError) as exc:
        logger.warning("Copernicus STAC catalogue request failed: %s", exc)
        result = {
            "available": False,
            "checked_at": _utc_now(),
            "items": [],
            "source_name": "Copernicus Data Space STAC catalogue",
            "source_url": "https://stac.dataspace.copernicus.eu/v1/",
            "message": "The satellite catalogue is currently unavailable. No fabricated products are shown.",
        }
        _cache_set(key, result)
        return result
