import os
import urllib.parse
from typing import Dict, List, Optional, Tuple

import requests
from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Default keys baked into the stack so the map proxy still works when env vars
# are not explicitly provided (e.g., local `docker compose up` without a `.env`).
DEFAULT_GEOCODER_KEY = "26bdda31-1de9-4707-9964-055d30041574"
DEFAULT_STATIC_KEY = "f8aed38b-c9ee-45cf-b1a5-efc69cc6e5af"

GEOCODER_API_KEY = (
    os.environ.get("YANDEX_GEOCODER_API_KEY")
    or os.environ.get("YANDEX_MAPS_API_KEY")
    or DEFAULT_GEOCODER_KEY
)
STATIC_API_KEY = (
    os.environ.get("YANDEX_STATIC_API_KEY")
    or os.environ.get("YANDEX_MAPS_API_KEY")
    or DEFAULT_STATIC_KEY
)
GEOCODE_URL = "https://geocode-maps.yandex.ru/1.x/"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
STATIC_MAP_URL = "https://static-maps.yandex.ru/1.x/"


def geocode(address: str) -> Optional[Tuple[float, float]]:
    params = {
        "apikey": GEOCODER_API_KEY,
        "format": "json",
        "lang": "ru_RU",
        "geocode": address,
    }
    try:
        response = requests.get(GEOCODE_URL, params=params, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    try:
        members = (
            response.json()
            .get("response", {})
            .get("GeoObjectCollection", {})
            .get("featureMember", [])
        )
    except ValueError:
        return None

    if not members:
        return None

    position = members[0].get("GeoObject", {}).get("Point", {}).get("pos")
    if not position:
        return None

    try:
        lon_str, lat_str = position.split()
        return float(lon_str), float(lat_str)
    except ValueError:
        return None


def build_route_request(points: List[Tuple[float, float]]) -> Dict:
    coords = ";".join(f"{lon},{lat}" for lon, lat in points)
    params = {
        "overview": "full",
        "geometries": "geojson",
    }
    return {"coords": coords, "params": params}


def fetch_osrm_route(points: List[Tuple[float, float]]) -> Optional[Dict]:
    payload = build_route_request(points)
    try:
        response = requests.get(
            f"{OSRM_URL}/{payload['coords']}",
            params=payload["params"],
            timeout=12,
        )
        response.raise_for_status()
    except requests.RequestException:
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not data.get("routes"):
        return None

    route = data["routes"][0]
    return {
        "distance": route.get("distance"),
        "duration": route.get("duration"),
        "geometry": (route.get("geometry") or {}).get("coordinates", []),
    }


def normalize_polyline(points: List[Dict]) -> List[Dict[str, float]]:
    normalized = []
    for p in points:
        if isinstance(p, dict) and "lon" in p and "lat" in p:
            normalized.append({"lon": float(p["lon"]), "lat": float(p["lat"])})
        elif isinstance(p, (list, tuple)) and len(p) >= 2:
            try:
                lon_val = float(p[0])
                lat_val = float(p[1])
                normalized.append({"lon": lon_val, "lat": lat_val})
            except (TypeError, ValueError):
                continue
    return normalized


def build_map_url(points: List[Tuple[float, float]], poly_points: List[Dict]) -> str:
    params: Dict[str, str] = {
        "l": "map",
        # Yandex Static API max size is 650x450; keep within limits while matching UI ratio
        "size": "650,420",
    }

    if STATIC_API_KEY:
        params["apikey"] = STATIC_API_KEY

    markers = []
    if points:
        lon, lat = points[0]
        markers.append(f"{lon},{lat},pm2gnl")
    if len(points) == 3:
        lon, lat = points[1]
        markers.append(f"{lon},{lat},pm2blm")
    if len(points) >= 2:
        lon, lat = points[-1]
        markers.append(f"{lon},{lat},pm2rdm")

    if markers:
        params["pt"] = "~".join(markers)

    path_coords = normalize_polyline(poly_points) or [
        {"lon": lon, "lat": lat} for lon, lat in points
    ]
    if path_coords:
        # Reduce number of points to fit static maps limits
        step = max(len(path_coords) // 50, 1)
        reduced = path_coords[::step]
        coords = ",".join(f"{p['lon']},{p['lat']}" for p in reduced)
        params["pl"] = f"c:1a73e8,w:4,{coords}"

    return f"{STATIC_MAP_URL}?{urllib.parse.urlencode(params, safe=':,')}"


def format_distance(distance_meters: Optional[float]) -> Optional[str]:
    if distance_meters is None:
        return None
    return f"{round(distance_meters / 1000, 1)} км"


def format_duration(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    minutes = int(round(seconds / 60))
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours} ч {mins} мин"
    return f"{mins} мин"


@app.route("/health", methods=["GET"])
def health() -> tuple:
    return jsonify({"status": "ok"}), 200


@app.route("/directions", methods=["POST"])
def directions() -> tuple:
    if not GEOCODER_API_KEY:
        return (
            jsonify(
                {
                    "message": "YANDEX_GEOCODER_API_KEY не задан. Установите ключ в переменной окружения и перезапустите сервис.",
                }
            ),
            503,
        )

    payload = request.get_json() or {}
    origin = (payload.get("start") or "").strip()
    destination = (payload.get("end") or "").strip()
    waypoint = (payload.get("waypoint") or "").strip()

    if not origin or not destination:
        return (
            jsonify({"message": "Необходимо указать точку старта и пункт назначения."}),
            400,
        )

    origin_coords = geocode(origin)
    destination_coords = geocode(destination)
    waypoint_coords = geocode(waypoint) if waypoint else None

    if not origin_coords or not destination_coords:
        return (
            jsonify({"message": "Не удалось определить координаты старта или финиша по адресу."}),
            400,
        )

    points = [origin_coords]
    if waypoint_coords:
        points.append(waypoint_coords)
    points.append(destination_coords)

    route_data = fetch_osrm_route(points)
    if not route_data:
        return (
            jsonify(
                {
                    "message": "Маршрут не найден или сервис построения временно недоступен.",
                }
            ),
            404,
        )

    distance_value = route_data.get("distance")
    duration_value = route_data.get("duration")
    geometry_points = route_data.get("geometry") or []

    map_url = build_map_url(points, geometry_points)

    return (
        jsonify(
            {
                "distance_text": format_distance(distance_value),
                "distance_value": distance_value,
                "duration_text": format_duration(duration_value),
                "duration_value": duration_value,
                "map_url": map_url,
                "start_address": origin,
                "end_address": destination,
            }
        ),
        200,
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8081))
    app.run(host="0.0.0.0", port=port)
