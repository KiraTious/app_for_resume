from datetime import date, datetime, timedelta
import os

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
import requests

from app import db
from models.user import User
from models.route import Route
from models.vehicle import Vehicle
from models.maintenance import Maintenance
from routes.auth import role_required


driver_bp = Blueprint('driver', __name__)


MAP_PROXY_ENDPOINTS = [
    os.environ.get('MAPS_PROXY_URL'),
    'http://yandexmaps:8081/directions',
    'http://localhost:8081/directions',
]


def _call_map_proxy(payload):
    """Try contacting the maps proxy service with fallbacks."""

    for endpoint in [ep for ep in MAP_PROXY_ENDPOINTS if ep]:
        try:
            response = requests.post(endpoint, json=payload, timeout=12)
            response.raise_for_status()
            return response.json()
        except requests.RequestException:
            continue
    return None


def _map_preview(start_location: str, end_location: str, waypoint: str = None, preference: str = None):
    payload = {
        'start': start_location,
        'end': end_location,
        'waypoint': waypoint,
        'preference': preference,
    }

    return _call_map_proxy(payload)


def _get_current_driver():
    user_id = get_jwt_identity()
    if not user_id:
        return None

    user = User.query.get(int(user_id))
    if not user or not user.driver:
        return None
    return user.driver


@driver_bp.route('/today', methods=['GET'])
@role_required('driver')
def today_routes():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    today_date = date.today()

    routes = (
        Route.query.join(Vehicle, Route.vehicle_id == Vehicle.id)
        .filter(Route.driver_id == driver.id, Route.date == today_date)
        .order_by(Route.date.asc(), Route.id.asc())
        .all()
    )

    prepared_routes = []
    for idx, route in enumerate(routes):
        vehicle = route.vehicle
        prepared_routes.append(
            {
                'id': route.id,
                'start_location': route.start_location,
                'end_location': route.end_location,
                'date': route.date.isoformat(),
                'distance': route.distance,
                'vehicle_reg_number': vehicle.reg_number if vehicle else None,
                'status': 'in_progress' if idx == 0 else 'planned',
            }
        )

    planned_distance = round(sum(r.distance or 0 for r in routes), 1)

    maintenance_note = 'Информация по обслуживанию недоступна.'
    vehicle_ids = [vehicle.id for vehicle in driver.vehicles]
    if vehicle_ids:
        latest_maintenance = (
            Maintenance.query.filter(Maintenance.vehicle_id.in_(vehicle_ids))
            .order_by(Maintenance.created_at.desc())
            .first()
        )
        if latest_maintenance:
            maintenance_note = (
                f"Последнее ТО: {latest_maintenance.type_of_work}"
                f" ({latest_maintenance.created_at.strftime('%d.%m.%Y')})."
            )
        else:
            maintenance_note = 'Для вашего авто еще нет записей об обслуживании.'

    first_route_message = 'Сегодня рейсы не назначены.'
    if prepared_routes:
        first_route = prepared_routes[0]
        first_route_message = (
            f"Первый рейс: {first_route['start_location']} → "
            f"{first_route['end_location']}"
        )

    summary = {
        'planned_distance': planned_distance,
        'route_count': len(prepared_routes),
        'first_route': first_route_message,
        'maintenance_note': maintenance_note,
    }

    return jsonify({'routes': prepared_routes, 'summary': summary}), 200


def _serialize_route(route):
    return {
        'id': route.id,
        'start_location': route.start_location,
        'end_location': route.end_location,
        'date': route.date.isoformat() if route.date else None,
        'distance': route.distance,
        'vehicle_reg_number': route.vehicle.reg_number if route.vehicle else None,
    }


@driver_bp.route('/navigation', methods=['GET'])
@role_required('driver')
def navigation_overview():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    vehicle = _get_driver_vehicle(driver)
    if not vehicle:
        return jsonify({'message': 'За вами не закреплено транспортное средство.'}), 404

    today_date = date.today()

    upcoming_route = (
        Route.query.filter(Route.driver_id == driver.id, Route.date >= today_date)
        .order_by(Route.date.asc(), Route.id.asc())
        .first()
    )

    latest_route = (
        Route.query.filter_by(driver_id=driver.id)
        .order_by(Route.date.desc(), Route.id.desc())
        .first()
    )

    current_route = upcoming_route or latest_route

    routes = (
        Route.query.filter_by(driver_id=driver.id)
        .order_by(Route.date.desc(), Route.id.desc())
        .limit(25)
        .all()
    )

    payload = {
        'current_route': _serialize_route(current_route) if current_route else None,
        'routes': [_serialize_route(r) for r in routes],
    }

    if payload['current_route']:
        preview = _map_preview(
            payload['current_route']['start_location'],
            payload['current_route']['end_location'],
        )
        if preview:
            payload['current_route'].update(
                {
                    'map_url': preview.get('map_url'),
                    'distance_text': preview.get('distance_text'),
                    'duration_text': preview.get('duration_text'),
                }
            )

    return jsonify(payload), 200


@driver_bp.route('/navigation', methods=['POST'])
@role_required('driver')
def create_navigation_route():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    vehicle = _get_driver_vehicle(driver)
    if not vehicle:
        return jsonify({'message': 'За вами не закреплено транспортное средство.'}), 404

    payload = request.get_json() or {}
    start_location = (payload.get('start_location') or '').strip()
    end_location = (payload.get('end_location') or '').strip()
    date_raw = payload.get('date')

    if not start_location or not end_location:
        return jsonify({'message': 'Укажите точки старта и назначения.'}), 400

    if not date_raw:
        return jsonify({'message': 'Укажите дату маршрута.'}), 400

    try:
        route_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Некорректный формат даты. Используйте ГГГГ-ММ-ДД.'}), 400

    map_data = _map_preview(start_location, end_location, payload.get('waypoint'), payload.get('preference'))
    distance_value = None
    if map_data and map_data.get('distance_value') is not None:
        try:
            distance_value = float(map_data['distance_value']) / 1000.0
        except (TypeError, ValueError):
            distance_value = None

    if distance_value is None:
        distance_value = 0

    new_route = Route(
        start_location=start_location,
        end_location=end_location,
        date=route_date,
        distance=distance_value,
        vehicle_id=vehicle.id,
        driver_id=driver.id,
    )

    db.session.add(new_route)
    db.session.commit()

    route_payload = _serialize_route(new_route)
    if map_data:
        route_payload.update(
            {
                'map_url': map_data.get('map_url'),
                'distance_text': map_data.get('distance_text'),
                'duration_text': map_data.get('duration_text'),
            }
        )

    return jsonify({'route': route_payload, 'message': 'Маршрут сохранён.'}), 201


def _get_driver_vehicle(driver):
    return (
        Vehicle.query.filter_by(driver_id=driver.id)
        .order_by(Vehicle.created_at.desc())
        .first()
    )


@driver_bp.route('/vehicle', methods=['GET'])
@role_required('driver')
def vehicle_overview():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    vehicle = _get_driver_vehicle(driver)
    if not vehicle:
        return jsonify({'message': 'За вами не закреплено транспортное средство.'}), 404

    today = date.today()
    window_start = today - timedelta(days=30)

    maintenance_items = (
        Maintenance.query.filter_by(vehicle_id=vehicle.id)
        .order_by(Maintenance.created_at.desc())
        .limit(5)
        .all()
    )

    routes_all = Route.query.filter(Route.vehicle_id == vehicle.id).all()
    total_distance = round(sum(r.distance or 0 for r in routes_all), 1)

    recent_routes = (
        Route.query.filter(Route.vehicle_id == vehicle.id, Route.date >= window_start)
        .order_by(Route.date.desc())
        .all()
    )
    recent_distance = sum(r.distance or 0 for r in recent_routes)
    recent_days = max((today - window_start).days, 1)
    avg_daily_km = round(recent_distance / recent_days, 1)
    avg_monthly_km = round(avg_daily_km * 30, 1)

    latest_maintenance = maintenance_items[0] if maintenance_items else None
    next_service_km = max(0, 10000 - (total_distance % 10000))
    days_since_maintenance = (
        (today - latest_maintenance.created_at.date()).days
        if latest_maintenance
        else None
    )

    if not latest_maintenance:
        status = 'Нужна диагностика'
    elif days_since_maintenance <= 120 and next_service_km > 1000:
        status = 'Готов к рейсу'
    else:
        status = 'Требуется ТО'

    maintenance_list = [
        {
            'id': item.id,
            'date': item.created_at.date().isoformat(),
            'type_of_work': item.type_of_work,
            'cost': item.cost,
        }
        for item in maintenance_items
    ]

    response = {
        'vehicle': {
            'id': vehicle.id,
            'brand': vehicle.brand,
            'model': vehicle.model,
            'reg_number': vehicle.reg_number,
            'assigned_since': vehicle.created_at.date().isoformat(),
            'total_distance': total_distance,
        },
        'metrics': {
            'status': status,
            'next_service_km': next_service_km,
            'avg_daily_km': avg_daily_km,
            'avg_monthly_km': avg_monthly_km,
            'trips_last_30_days': len(recent_routes),
            'days_since_maintenance': days_since_maintenance,
        },
        'maintenance': maintenance_list,
        'latest_maintenance': (
            {
                'date': latest_maintenance.created_at.date().isoformat(),
                'type_of_work': latest_maintenance.type_of_work,
                'cost': latest_maintenance.cost,
            }
            if latest_maintenance
            else None
        ),
    }

    return jsonify(response), 200


@driver_bp.route('/maintenance', methods=['GET'])
@role_required('driver')
def maintenance_overview():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    vehicle = _get_driver_vehicle(driver)
    if not vehicle:
        return jsonify({'message': 'За вами не закреплено транспортное средство.'}), 404

    today = date.today()
    month_start = today.replace(day=1)

    operations_query = Maintenance.query.filter_by(vehicle_id=vehicle.id)

    operations = (
        operations_query
        .order_by(Maintenance.event_date.desc(), Maintenance.created_at.desc())
        .limit(20)
        .all()
    )

    monthly_operations = (
        operations_query
        .filter(
            Maintenance.event_date >= month_start,
            Maintenance.event_date <= today,
        )
        .all()
    )

    routes_month = (
        Route.query.filter(
            Route.vehicle_id == vehicle.id,
            Route.date >= month_start,
            Route.date <= today,
        ).all()
    )

    monthly_distance = round(sum(r.distance or 0 for r in routes_month), 1)

    fuel_ops = [op for op in monthly_operations if op.operation_type == 'fuel']
    service_ops = [op for op in monthly_operations if op.operation_type == 'service']

    fuel_volume = sum(op.fuel_volume_l or 0 for op in fuel_ops)
    fuel_cost = sum(op.cost or 0 for op in fuel_ops)
    service_cost = sum(op.cost or 0 for op in service_ops)

    avg_consumption = None
    if monthly_distance > 0 and fuel_volume > 0:
        avg_consumption = round((fuel_volume / monthly_distance) * 100, 1)

    operations_list = [
        {
            'id': op.id,
            'operation_type': op.operation_type,
            'event_date': op.event_date.isoformat() if op.event_date else None,
            'mileage_km': op.mileage_km,
            'fuel_volume_l': op.fuel_volume_l,
            'type_of_work': op.type_of_work,
            'cost': op.cost,
        }
        for op in operations
    ]

    summary = {
        'distance': monthly_distance,
        'fuel_volume': fuel_volume,
        'fuel_cost': fuel_cost,
        'service_cost': service_cost,
        'avg_consumption': avg_consumption,
    }

    return jsonify({'operations': operations_list, 'summary': summary}), 200


@driver_bp.route('/maintenance', methods=['POST'])
@role_required('driver')
def create_maintenance():
    driver = _get_current_driver()
    if not driver:
        return jsonify({'message': 'Driver profile not found.'}), 404

    vehicle = _get_driver_vehicle(driver)
    if not vehicle:
        return jsonify({'message': 'За вами не закреплено транспортное средство.'}), 404

    payload = request.get_json() or {}
    op_type = payload.get('operation_type')
    event_date_raw = payload.get('event_date')
    mileage_km = payload.get('mileage_km')
    cost = payload.get('cost')

    if op_type not in {'fuel', 'service'}:
        return jsonify({'message': 'Некорректный тип операции.'}), 400

    if not event_date_raw:
        return jsonify({'message': 'Требуется дата операции.'}), 400

    try:
        event_date = datetime.strptime(event_date_raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Некорректный формат даты. Используйте ГГГГ-ММ-ДД.'}), 400

    try:
        cost_value = float(cost)
    except (TypeError, ValueError):
        return jsonify({'message': 'Некорректная стоимость операции.'}), 400

    new_entry = None
    if op_type == 'fuel':
        try:
            fuel_volume = float(payload.get('fuel_volume_l'))
        except (TypeError, ValueError):
            return jsonify({'message': 'Укажите объём топлива.'}), 400

        new_entry = Maintenance(
            operation_type='fuel',
            type_of_work='Топливо',
            cost=cost_value,
            event_date=event_date,
            mileage_km=mileage_km,
            fuel_volume_l=fuel_volume,
            vehicle_id=vehicle.id,
        )
    else:
        work_type = (payload.get('type_of_work') or '').strip()
        if not work_type:
            return jsonify({'message': 'Укажите тип выполненных работ.'}), 400

        new_entry = Maintenance(
            operation_type='service',
            type_of_work=work_type,
            cost=cost_value,
            event_date=event_date,
            mileage_km=mileage_km,
            vehicle_id=vehicle.id,
        )

    db.session.add(new_entry)
    db.session.commit()

    return (
        jsonify(
            {
                'id': new_entry.id,
                'message': 'Операция сохранена',
            }
        ),
        201,
    )
