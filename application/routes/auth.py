from functools import wraps

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)

from models.user import User


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['POST'])
def login():
    payload = request.get_json() or {}
    username = payload.get('username')
    password = payload.get('password')

    if not username or not password:
        return jsonify({'message': 'Username and password are required.'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid credentials.'}), 401

    additional_claims = {'role': user.role}
    access_token = create_access_token(
        identity=str(user.id), additional_claims=additional_claims
    )

    return jsonify({
        'access_token': access_token,
        'user': {
            'id': user.id,
            'username': user.username,
            'role': user.role,
        }
    })


def role_required(*roles):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorated(*args, **kwargs):
            claims = get_jwt()
            if claims.get('role') not in roles:
                return jsonify({'message': 'Insufficient permissions.'}), 403
            return fn(*args, **kwargs)

        return decorated

    return wrapper


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def current_user():
    user_id = get_jwt_identity()
    user = User.query.get(int(user_id)) if user_id is not None else None
    if not user:
        return jsonify({'message': 'User not found.'}), 404

    return jsonify({
        'id': user.id,
        'username': user.username,
        'role': user.role,
    })


@auth_bp.route('/roles/demo', methods=['GET'])
@role_required('admin', 'manager')
def roles_demo():
    claims = get_jwt()
    return jsonify({'message': f"Hello, {claims.get('role')}! Authorization placeholder."})
