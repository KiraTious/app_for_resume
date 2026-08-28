from flask import Blueprint, jsonify, request
from sqlalchemy import or_
from app import db
from models.user import User
from models.driver import Driver
from models.vehicle import Vehicle
from models.maintenance import Maintenance
from models.route import Route
from datetime import datetime, date
from routes.auth import role_required


admin_bp = Blueprint('admin', __name__)


def _validate_role(role: str) -> bool:
    return role in {'admin', 'manager', 'driver'}


def _serialize_route(route: Route):
    if not route:
        return None

    driver = route.driver
    vehicle = route.vehicle

    return {
        'id': route.id,
        'start_location': route.start_location,
        'end_location': route.end_location,
        'date': route.date.isoformat() if route.date else None,
        'distance': route.distance,
        'driver': (
            {
                'id': driver.id,
                'first_name': driver.first_name,
                'last_name': driver.last_name,
                'license_number': driver.license_number,
            }
            if driver
            else None
        ),
        'vehicle': (
            {
                'id': vehicle.id,
                'brand': vehicle.brand,
                'model': vehicle.model,
                'reg_number': vehicle.reg_number,
            }
            if vehicle
            else None
        ),
    }


@admin_bp.route('/users', methods=['POST'])
@role_required('admin')
def create_user():
    payload = request.get_json() or {}

    username = (payload.get('username') or '').strip()
    password = payload.get('password') or ''
    role = (payload.get('role') or '').strip()

    first_name = (payload.get('first_name') or '').strip()
    last_name = (payload.get('last_name') or '').strip()
    license_number = (payload.get('license_number') or '').strip()
    vehicle_id = payload.get('vehicle_id')
    vehicle_reg_number = (payload.get('vehicle_reg_number') or '').strip()

    if not username or not password or not role:
        return jsonify({'message': 'username, password и role обязательны.'}), 400

    if not _validate_role(role):
        return jsonify({'message': 'Недопустимая роль.'}), 400

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        return jsonify({'message': 'Пользователь с таким логином уже существует.'}), 409

    user = User(username=username, role=role)
    user.set_password(password)

    driver = None
    if role == 'driver':
        if not (first_name and last_name and license_number):
            return (
                jsonify({
                    'message': 'Для водителя необходимы first_name, last_name и license_number.'
                }),
                400,
            )

        if Driver.query.filter_by(license_number=license_number).first():
            return jsonify({'message': 'Водитель с таким номером удостоверения уже есть.'}), 409

        driver = Driver(
            first_name=first_name,
            last_name=last_name,
            license_number=license_number,
            user=user,
        )

    if vehicle_id or vehicle_reg_number:
        vehicle = None
        if vehicle_id:
            vehicle = Vehicle.query.get(vehicle_id)
        elif vehicle_reg_number:
            vehicle = Vehicle.query.filter_by(reg_number=vehicle_reg_number).first()

        if not vehicle:
            return jsonify({'message': 'Указанное ТС не найдено.'}), 404
        vehicle.driver = driver

    db.session.add(user)
    if driver:
        db.session.add(driver)
    try:
        db.session.commit()
    except Exception:  # pragma: no cover - простая обработка ошибок для demo
        db.session.rollback()
        return jsonify({'message': 'Не удалось создать пользователя.'}), 500

    response = {
        'id': user.id,
        'username': user.username,
        'role': user.role,
    }
    if driver:
        response['driver'] = {
            'first_name': driver.first_name,
            'last_name': driver.last_name,
            'license_number': driver.license_number,
        }
    return jsonify(response), 201


@admin_bp.route('/vehicles', methods=['POST'])
@role_required('admin')
def create_vehicle():
    payload = request.get_json() or {}

    brand = (payload.get('brand') or '').strip()
    model = (payload.get('model') or '').strip()
    reg_number = (payload.get('reg_number') or '').strip()
    driver_id = payload.get('driver_id')

    if not brand or not model or not reg_number:
        return jsonify({'message': 'brand, model и reg_number обязательны.'}), 400

    if Vehicle.query.filter_by(reg_number=reg_number).first():
        return jsonify({'message': 'ТС с таким госномером уже существует.'}), 409

    vehicle = Vehicle(brand=brand, model=model, reg_number=reg_number)

    if driver_id:
        driver = Driver.query.get(driver_id)
        if not driver:
            return jsonify({'message': 'Указанный водитель не найден.'}), 404
        vehicle.driver = driver

    db.session.add(vehicle)
    try:
        db.session.commit()
    except Exception:  # pragma: no cover - простая обработка ошибок для demo
        db.session.rollback()
        return jsonify({'message': 'Не удалось создать транспортное средство.'}), 500

    response = {
        'id': vehicle.id,
        'brand': vehicle.brand,
        'model': vehicle.model,
        'reg_number': vehicle.reg_number,
        'driver_id': vehicle.driver_id,
    }
    return jsonify(response), 201


@admin_bp.route('/users', methods=['GET'])
@role_required('admin')
def list_users():
    search_query = (request.args.get('query') or '').strip()
    limit_param = request.args.get('limit', type=int)

    # По умолчанию показываем последние 5. Для поиска без указанного лимита — до 20.
    limit = limit_param if limit_param is not None else (20 if search_query else 5)
    limit = max(1, min(limit, 100))  # простая защита от слишком больших выборок

    query = User.query.outerjoin(Driver).order_by(User.created_at.desc())

    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                User.username.ilike(pattern),
                Driver.first_name.ilike(pattern),
                Driver.last_name.ilike(pattern),
                Driver.license_number.ilike(pattern),
            )
        )

    users = query.limit(limit).all()

    result = []
    for user in users:
        driver = user.driver
        driver_vehicles = driver.vehicles if driver else []
        result.append(
            {
                'id': user.id,
                'username': user.username,
                'role': user.role,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'driver': (
                    {
                        'first_name': driver.first_name,
                        'last_name': driver.last_name,
                        'license_number': driver.license_number,
                    }
                    if driver
                    else None
                ),
                'vehicles': [vehicle.reg_number for vehicle in driver_vehicles],
            }
        )

    return jsonify({'items': result, 'limit': limit, 'query': search_query}), 200


@admin_bp.route('/vehicles', methods=['GET'])
@role_required('admin')
def list_vehicles():
    search_query = (request.args.get('query') or '').strip()
    limit_param = request.args.get('limit', type=int)

    limit = limit_param if limit_param is not None else (20 if search_query else 5)
    limit = max(1, min(limit, 100))

    query = Vehicle.query.outerjoin(Driver).order_by(Vehicle.created_at.desc())

    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Vehicle.reg_number.ilike(pattern),
                Vehicle.brand.ilike(pattern),
                Vehicle.model.ilike(pattern),
                Driver.first_name.ilike(pattern),
                Driver.last_name.ilike(pattern),
            )
        )

    vehicles = query.limit(limit).all()

    result = []
    for vehicle in vehicles:
        driver = vehicle.driver
        result.append(
            {
                'id': vehicle.id,
                'brand': vehicle.brand,
                'model': vehicle.model,
                'reg_number': vehicle.reg_number,
                'driver': (
                    {
                        'first_name': driver.first_name,
                        'last_name': driver.last_name,
                        'license_number': driver.license_number,
                    }
                    if driver
                    else None
                ),
            }
        )

    return jsonify({'items': result, 'limit': limit, 'query': search_query}), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@role_required('admin')
def delete_user(user_id: int):
    user = User.query.get(user_id)
    if not user:
        return jsonify({'message': 'Пользователь не найден.'}), 404

    try:
        driver = user.driver
        if driver:
            # Снимаем привязку ТС, чтобы избежать проблем с внешними ключами
            for vehicle in driver.vehicles:
                vehicle.driver = None
            db.session.delete(driver)

        db.session.delete(user)
        db.session.commit()
    except Exception:  # pragma: no cover - простая обработка ошибок для demo
        db.session.rollback()
        return jsonify({'message': 'Не удалось удалить пользователя.'}), 500

    return jsonify({'message': 'Пользователь удален.'}), 200


@admin_bp.route('/vehicles/<int:vehicle_id>', methods=['DELETE'])
@role_required('admin')
def delete_vehicle(vehicle_id: int):
    vehicle = Vehicle.query.get(vehicle_id)
    if not vehicle:
        return jsonify({'message': 'ТС не найдено.'}), 404

    try:
        db.session.delete(vehicle)
        db.session.commit()
    except Exception:  # pragma: no cover - простая обработка ошибок для demo
        db.session.rollback()
        return jsonify({'message': 'Не удалось удалить ТС.'}), 500

    return jsonify({'message': 'ТС удалено.'}), 200


@admin_bp.route('/maintenance', methods=['POST'])
@role_required('admin')
def create_maintenance():
    payload = request.get_json() or {}

    vehicle_id = payload.get('vehicle_id')
    vehicle_reg_number = (payload.get('vehicle_reg_number') or '').strip()
    type_of_work = (payload.get('type_of_work') or '').strip()
    cost = payload.get('cost')
    performed_at = (payload.get('performed_at') or '').strip()

    if not type_of_work or cost is None:
        return jsonify({'message': 'type_of_work и cost обязательны.'}), 400

    try:
        cost_value = float(cost)
    except (TypeError, ValueError):
        return jsonify({'message': 'Стоимость должна быть числом.'}), 400

    if cost_value < 0:
        return jsonify({'message': 'Стоимость не может быть отрицательной.'}), 400

    vehicle = None
    if vehicle_id:
        vehicle = Vehicle.query.get(vehicle_id)
    elif vehicle_reg_number:
        vehicle = Vehicle.query.filter_by(reg_number=vehicle_reg_number).first()

    if not vehicle:
        return jsonify({'message': 'Указанное ТС не найдено.'}), 404

    maintenance = Maintenance(
        type_of_work=type_of_work,
        cost=cost_value,
        vehicle=vehicle,
    )

    if performed_at:
        try:
            maintenance.created_at = datetime.fromisoformat(performed_at)
        except ValueError:
            return jsonify({'message': 'Некорректная дата.'}), 400

    db.session.add(maintenance)

    try:
        db.session.commit()
    except Exception:  # pragma: no cover
        db.session.rollback()
        return jsonify({'message': 'Не удалось сохранить обслуживание.'}), 500

    return (
        jsonify(
            {
                'id': maintenance.id,
                'type_of_work': maintenance.type_of_work,
                'cost': maintenance.cost,
                'created_at': maintenance.created_at.isoformat() if maintenance.created_at else None,
                'vehicle': {
                    'id': vehicle.id,
                    'brand': vehicle.brand,
                    'model': vehicle.model,
                    'reg_number': vehicle.reg_number,
                },
            }
        ),
        201,
    )


@admin_bp.route('/maintenance', methods=['GET'])
@role_required('admin')
def list_maintenance():
    search_query = (request.args.get('query') or '').strip()
    limit_param = request.args.get('limit', type=int)

    limit = limit_param if limit_param is not None else (20 if search_query else 5)
    limit = max(1, min(limit, 100))

    query = Maintenance.query.join(Vehicle).order_by(Maintenance.created_at.desc())

    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Maintenance.type_of_work.ilike(pattern),
                Vehicle.reg_number.ilike(pattern),
                Vehicle.brand.ilike(pattern),
                Vehicle.model.ilike(pattern),
            )
        )

    items = query.limit(limit).all()

    result = []
    for record in items:
        vehicle = record.vehicle
        result.append(
            {
                'id': record.id,
                'type_of_work': record.type_of_work,
                'cost': record.cost,
                'created_at': record.created_at.isoformat() if record.created_at else None,
                'vehicle': (
                    {
                        'id': vehicle.id,
                        'brand': vehicle.brand,
                        'model': vehicle.model,
                        'reg_number': vehicle.reg_number,
                    }
                    if vehicle
                    else None
                ),
            }
        )

    return jsonify({'items': result, 'limit': limit, 'query': search_query}), 200


@admin_bp.route('/drivers', methods=['GET'])
@role_required('admin', 'manager')
def list_drivers():
    drivers = (
        Driver.query.order_by(Driver.last_name.asc(), Driver.first_name.asc())
        .all()
    )

    items = []
    for driver in drivers:
        vehicle = (
            Vehicle.query.filter_by(driver_id=driver.id)
            .order_by(Vehicle.created_at.desc())
            .first()
        )
        items.append(
            {
                'id': driver.id,
                'first_name': driver.first_name,
                'last_name': driver.last_name,
                'license_number': driver.license_number,
                'vehicle': (
                    {
                        'id': vehicle.id,
                        'brand': vehicle.brand,
                        'model': vehicle.model,
                        'reg_number': vehicle.reg_number,
                    }
                    if vehicle
                    else None
                ),
            }
        )

    return jsonify({'items': items}), 200


@admin_bp.route('/routes', methods=['GET'])
@role_required('admin', 'manager')
def list_routes():
    search_query = (request.args.get('query') or '').strip()
    limit_param = request.args.get('limit', type=int)
    limit = limit_param if limit_param is not None else 25
    limit = max(1, min(limit, 100))

    today_date = date.today()
    query = (
        Route.query.join(Driver).join(Vehicle)
        .filter(Route.date >= today_date)
        .order_by(Route.date.asc(), Route.id.desc())
    )

    if search_query:
        pattern = f"%{search_query}%"
        query = query.filter(
            or_(
                Route.start_location.ilike(pattern),
                Route.end_location.ilike(pattern),
                Driver.first_name.ilike(pattern),
                Driver.last_name.ilike(pattern),
                Vehicle.reg_number.ilike(pattern),
            )
        )

    routes = query.limit(limit).all()
    return jsonify({'items': [_serialize_route(r) for r in routes], 'limit': limit}), 200


@admin_bp.route('/routes', methods=['POST'])
@role_required('admin', 'manager')
def create_route():
    payload = request.get_json() or {}

    start_location = (payload.get('start_location') or '').strip()
    end_location = (payload.get('end_location') or '').strip()
    date_raw = payload.get('date')
    driver_id = payload.get('driver_id')

    if not start_location or not end_location:
        return jsonify({'message': 'Укажите начальную и конечную точки маршрута.'}), 400

    if not date_raw:
        return jsonify({'message': 'Укажите дату маршрута.'}), 400

    try:
        route_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Некорректный формат даты.'}), 400

    if not driver_id:
        return jsonify({'message': 'Необходимо выбрать водителя.'}), 400

    driver = Driver.query.get(driver_id)
    if not driver:
        return jsonify({'message': 'Выбранный водитель не найден.'}), 404

    vehicle = (
        Vehicle.query.filter_by(driver_id=driver.id)
        .order_by(Vehicle.created_at.desc())
        .first()
    )
    if not vehicle:
        return jsonify({'message': 'За водителем не закреплено транспортное средство.'}), 400

    new_route = Route(
        start_location=start_location,
        end_location=end_location,
        date=route_date,
        distance=float(payload.get('distance') or 0) if payload.get('distance') is not None else 0,
        driver_id=driver.id,
        vehicle_id=vehicle.id,
    )

    db.session.add(new_route)
    db.session.commit()

    return jsonify({'route': _serialize_route(new_route), 'message': 'Маршрут создан.'}), 201


@admin_bp.route('/routes/<int:route_id>', methods=['PUT'])
@role_required('admin', 'manager')
def update_route(route_id: int):
    route = Route.query.get(route_id)
    if not route:
        return jsonify({'message': 'Маршрут не найден.'}), 404

    payload = request.get_json() or {}

    start_location = (payload.get('start_location') or '').strip()
    end_location = (payload.get('end_location') or '').strip()
    date_raw = payload.get('date')
    driver_id = payload.get('driver_id')

    if not start_location or not end_location:
        return jsonify({'message': 'Укажите начальную и конечную точки маршрута.'}), 400

    if not date_raw:
        return jsonify({'message': 'Укажите дату маршрута.'}), 400

    try:
        route_date = datetime.strptime(date_raw, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'message': 'Некорректный формат даты.'}), 400

    if not driver_id:
        return jsonify({'message': 'Необходимо выбрать водителя.'}), 400

    driver = Driver.query.get(driver_id)
    if not driver:
        return jsonify({'message': 'Выбранный водитель не найден.'}), 404

    vehicle = (
        Vehicle.query.filter_by(driver_id=driver.id)
        .order_by(Vehicle.created_at.desc())
        .first()
    )
    if not vehicle:
        return jsonify({'message': 'За водителем не закреплено транспортное средство.'}), 400

    route.start_location = start_location
    route.end_location = end_location
    route.date = route_date
    route.driver_id = driver.id
    route.vehicle_id = vehicle.id

    if 'distance' in payload:
        try:
            distance_value = float(payload.get('distance') or 0)
        except (TypeError, ValueError):
            return jsonify({'message': 'Некорректная длина маршрута.'}), 400
        if distance_value < 0:
            return jsonify({'message': 'Длина маршрута не может быть отрицательной.'}), 400
        route.distance = distance_value

    db.session.commit()

    return jsonify({'route': _serialize_route(route), 'message': 'Маршрут обновлён.'}), 200


@admin_bp.route('/routes/<int:route_id>', methods=['DELETE'])
@role_required('admin', 'manager')
def delete_route(route_id: int):
    route = Route.query.get(route_id)
    if not route:
        return jsonify({'message': 'Маршрут не найден.'}), 404

    try:
        db.session.delete(route)
        db.session.commit()
    except Exception:  # pragma: no cover - простая обработка ошибок для demo
        db.session.rollback()
        return jsonify({'message': 'Не удалось удалить маршрут.'}), 500

    return jsonify({'message': 'Маршрут удалён.'}), 200
