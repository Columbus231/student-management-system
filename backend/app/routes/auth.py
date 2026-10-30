import re

from flask import Blueprint, jsonify, make_response, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
    set_access_cookies,
    unset_access_cookies,
)
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from backend.app import db, limiter
from backend.app.models import RevokedToken, User

auth_bp = Blueprint("auth", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, (jsonify(error="Request body must be a JSON object."), 400)
    return body, None


@auth_bp.post("/register")
@limiter.limit("5 per minute")
def register():
    body, error = _json_body()
    if error:
        return error
    allowed = {"email", "password", "full_name", "student_number"}
    unknown = set(body) - allowed
    if unknown:
        return jsonify(error="Unknown fields.", fields=sorted(unknown)), 400
    email_value = body.get("email")
    name_value = body.get("full_name")
    student_number_value = body.get("student_number")
    password = body.get("password")
    if not isinstance(email_value, str) or not isinstance(name_value, str):
        return jsonify(error="Email and full name must be strings."), 400
    if student_number_value is not None and not isinstance(student_number_value, str):
        return jsonify(error="Student number must be a string."), 400
    email = email_value.strip().lower()
    full_name = name_value.strip()
    student_number = (student_number_value or "").strip() or None
    if not email or not EMAIL_PATTERN.match(email):
        return jsonify(error="A valid email address is required."), 400
    if len(email) > 254:
        return jsonify(error="Email address must be at most 254 characters."), 400
    if not full_name or len(full_name) > 120:
        return jsonify(error="Full name is required and must be at most 120 characters."), 400
    if not isinstance(password, str) or not 10 <= len(password) <= 256:
        return jsonify(error="Password must contain between 10 and 256 characters."), 400
    if student_number and len(student_number) > 40:
        return jsonify(error="Student number must be at most 40 characters."), 400
    if User.query.filter(func.lower(User.email) == email).first():
        return jsonify(error="An account with that email already exists."), 409
    if student_number and User.query.filter_by(student_number=student_number).first():
        return jsonify(error="That student number is already registered."), 409
    user = User(
        email=email,
        full_name=full_name,
        role="student",
        student_number=student_number,
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="An account with that email or student number already exists."), 409
    return jsonify(data=user.to_dict()), 201


@auth_bp.post("/login")
@limiter.limit("5 per minute")
def login():
    body, error = _json_body()
    if error:
        return error
    email_value = body.get("email")
    password = body.get("password")
    if not isinstance(email_value, str) or not isinstance(password, str):
        return jsonify(error="Email and password are required."), 400
    email = email_value.strip().lower()
    user = User.query.filter(func.lower(User.email) == email).first() if email else None
    if not user or not user.check_password(password):
        return jsonify(error="Email or password is incorrect."), 401
    token = create_access_token(identity=str(user.id), additional_claims={"role": user.role})
    response = make_response(jsonify(data={"user": user.to_dict()}), 200)
    set_access_cookies(response, token)
    return response


@auth_bp.get("/me")
@jwt_required()
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    if user is None:
        return jsonify(error="Account no longer exists."), 401
    return jsonify(data=user.to_dict()), 200


@auth_bp.post("/logout")
@jwt_required()
def logout():
    db.session.add(RevokedToken(jti=get_jwt()["jti"]))
    db.session.commit()
    response = make_response(jsonify(message="Logged out successfully."), 200)
    unset_access_cookies(response)
    return response
