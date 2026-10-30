import re
from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from backend.app import db
from backend.app.models import (
    Attendance,
    Course,
    Department,
    Enrollment,
    Examination,
    Notice,
    Result,
    User,
)
from backend.app.services.academic import dashboard_summary, scoped_query

api_bp = Blueprint("api", __name__)
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NULLABLE_FIELDS = {
    "users": {"student_number", "faculty_number", "department_id"},
    "departments": {"description"},
    "courses": {"description", "faculty_id"},
    "enrollments": set(),
    "attendance": {"notes"},
    "examinations": set(),
    "results": {"grade", "remarks"},
    "notices": set(),
}

SPECS = {
    "users": {
        "model": User,
        "read": {"admin", "faculty", "student"},
        "write": {"admin"},
        "fields": {
            "email": str,
            "full_name": str,
            "role": str,
            "student_number": str,
            "faculty_number": str,
            "department_id": int,
            "password": str,
        },
        "required": {"email", "full_name", "role"},
        "search": ["email", "full_name", "student_number", "faculty_number"],
        "filters": ["role", "department_id"],
    },
    "departments": {
        "model": Department,
        "read": {"admin", "faculty", "student"},
        "write": {"admin"},
        "fields": {"name": str, "code": str, "description": str},
        "required": {"name", "code"},
        "search": ["name", "code", "description"],
        "filters": [],
    },
    "courses": {
        "model": Course,
        "read": {"admin", "faculty", "student"},
        "write": {"admin", "faculty"},
        "faculty_fields": {"title", "description"},
        "fields": {
            "code": str,
            "title": str,
            "description": str,
            "credits": int,
            "department_id": int,
            "faculty_id": int,
        },
        "required": {"code", "title", "department_id"},
        "search": ["code", "title", "description"],
        "filters": ["department_id", "faculty_id"],
    },
    "enrollments": {
        "model": Enrollment,
        "read": {"admin", "faculty", "student"},
        "write": {"admin"},
        "fields": {
            "student_id": int,
            "course_id": int,
            "academic_year": str,
            "term": str,
            "status": str,
        },
        "required": {"student_id", "course_id", "academic_year", "term"},
        "search": ["academic_year", "term", "status"],
        "filters": ["student_id", "course_id", "academic_year", "term", "status"],
    },
    "attendance": {
        "model": Attendance,
        "read": {"admin", "faculty", "student"},
        "write": {"admin", "faculty"},
        "faculty_fields": {"enrollment_id", "date", "status", "notes"},
        "fields": {
            "enrollment_id": int,
            "date": date,
            "status": str,
            "notes": str,
        },
        "required": {"enrollment_id", "date", "status"},
        "search": ["status", "notes"],
        "filters": ["enrollment_id", "date", "status"],
    },
    "examinations": {
        "model": Examination,
        "read": {"admin", "faculty", "student"},
        "write": {"admin", "faculty"},
        "faculty_fields": {"course_id", "title", "exam_date", "total_marks"},
        "fields": {
            "course_id": int,
            "title": str,
            "exam_date": date,
            "total_marks": float,
        },
        "required": {"course_id", "title", "exam_date", "total_marks"},
        "search": ["title"],
        "filters": ["course_id", "exam_date"],
    },
    "results": {
        "model": Result,
        "read": {"admin", "faculty", "student"},
        "write": {"admin", "faculty"},
        "faculty_fields": {"examination_id", "student_id", "marks", "grade", "remarks"},
        "fields": {
            "examination_id": int,
            "student_id": int,
            "marks": float,
            "grade": str,
            "remarks": str,
        },
        "required": {"examination_id", "student_id", "marks"},
        "search": ["grade", "remarks"],
        "filters": ["examination_id", "student_id", "grade"],
    },
    "notices": {
        "model": Notice,
        "read": {"admin", "faculty", "student"},
        "write": {"admin"},
        "fields": {"title": str, "body": str, "audience": str},
        "required": {"title", "body"},
        "search": ["title", "body"],
        "filters": ["audience"],
    },
}


def _actor():
    return db.session.get(User, int(get_jwt_identity()))


def _json_body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        return None, (jsonify(error="Request body must be a JSON object."), 400)
    return body, None


def _convert(field, value, value_type):
    if value is None:
        return None, None
    try:
        if value_type is str:
            if not isinstance(value, str):
                raise ValueError
            return value.strip(), None
        if value_type is int:
            if isinstance(value, bool):
                raise ValueError
            return int(value), None
        if value_type is float:
            if isinstance(value, bool):
                raise ValueError
            converted = float(value)
            if converted != converted or converted in (float("inf"), float("-inf")):
                raise ValueError
            return converted, None
        if value_type is date:
            if isinstance(value, date):
                return value, None
            return date.fromisoformat(value), None
    except (TypeError, ValueError):
        return None, f"{field} has an invalid value."
    return value, None


def _validation(entity, values, creating):
    spec = SPECS[entity]
    unknown = set(values) - set(spec["fields"])
    if unknown:
        return None, f"Unknown fields: {', '.join(sorted(unknown))}."
    if creating:
        missing = spec["required"] - set(values)
        if missing:
            return None, f"Required fields: {', '.join(sorted(missing))}."
    for field, value in values.items():
        if value is None and field not in NULLABLE_FIELDS[entity]:
            return None, f"{field} cannot be null."
    empty_required = spec["required"].intersection(
        field for field, value in values.items() if value is None or value == ""
    )
    if empty_required:
        return None, f"Required fields cannot be empty: {', '.join(sorted(empty_required))}."
    converted = {}
    for field, value in values.items():
        converted[field], error = _convert(field, value, spec["fields"][field])
        if error:
            return None, error
    for key in ("email", "full_name", "name", "code", "title", "body"):
        if key in converted and converted[key] == "":
            return None, f"{key} cannot be empty."
    max_lengths = {
        "email": 254, "full_name": 120, "student_number": 40, "faculty_number": 40,
        "name": 120, "code": 30, "title": 160, "term": 30, "academic_year": 20,
        "status": 20, "grade": 5, "audience": 20,
    }
    for field, maximum in max_lengths.items():
        if field in converted and converted[field] is not None and len(converted[field]) > maximum:
            return None, f"{field} must be at most {maximum} characters."
    if entity == "departments" and "code" in converted and len(converted["code"]) > 20:
        return None, "Department code must be at most 20 characters."
    if "description" in converted and converted["description"] is not None and len(converted["description"]) > 10000:
        return None, "description must be at most 10000 characters."
    if "body" in converted and converted["body"] is not None and len(converted["body"]) > 20000:
        return None, "body must be at most 20000 characters."
    if "email" in converted and converted["email"] and not EMAIL_PATTERN.match(converted["email"]):
        return None, "A valid email address is required."
    if entity == "users":
        if "role" in converted and converted["role"] not in {"admin", "faculty", "student"}:
            return None, "role must be admin, faculty, or student."
        password = converted.get("password")
        if creating and (not password or not 10 <= len(password) <= 256):
            return None, "Password must contain between 10 and 256 characters."
    if entity == "courses" and "credits" in converted:
        if not 1 <= converted["credits"] <= 30:
            return None, "credits must be between 1 and 30."
    if entity == "enrollments" and "status" in converted:
        if converted["status"] not in {"enrolled", "completed", "withdrawn"}:
            return None, "status must be enrolled, completed, or withdrawn."
    if entity == "attendance" and "status" in converted:
        if converted["status"] not in {"present", "absent", "late", "excused"}:
            return None, "status must be present, absent, late, or excused."
    if entity == "examinations" and "total_marks" in converted:
        if converted["total_marks"] <= 0:
            return None, "total_marks must be greater than zero."
    if entity == "results":
        if "marks" in converted and converted["marks"] < 0:
            return None, "marks cannot be negative."
        if "grade" in converted and converted["grade"] and len(converted["grade"]) > 5:
            return None, "grade must be at most 5 characters."
        if "remarks" in converted and converted["remarks"] and len(converted["remarks"]) > 500:
            return None, "remarks must be at most 500 characters."
    if entity == "attendance" and "notes" in converted and converted["notes"] and len(converted["notes"]) > 500:
        return None, "notes must be at most 500 characters."
    if entity == "notices" and "audience" in converted:
        if converted["audience"] not in {"all", "students", "faculty", "admins"}:
            return None, "audience must be all, students, faculty, or admins."
    return converted, None


def _serialize(entity, record):
    if entity == "users":
        return record.to_dict()
    result = {column.name: getattr(record, column.name) for column in record.__table__.columns}
    for field, value in list(result.items()):
        if isinstance(value, date):
            result[field] = value.isoformat()
    if entity == "courses":
        result["department_name"] = record.department.name
        result["faculty_name"] = record.faculty.full_name if record.faculty else None
    elif entity == "enrollments":
        result.update(
            student_name=record.student.full_name,
            course_code=record.course.code,
            course_title=record.course.title,
        )
    elif entity == "attendance":
        enrollment = record.enrollment
        result.update(
            student_name=enrollment.student.full_name,
            course_code=enrollment.course.code,
        )
    elif entity == "examinations":
        result["course_code"] = record.course.code
    elif entity == "results":
        result.update(
            student_name=record.student.full_name,
            exam_title=record.examination.title,
            course_code=record.examination.course.code,
        )
    elif entity == "notices":
        result["author_name"] = record.author.full_name
    return result


def _can_write(entity, actor, record=None):
    if actor.role not in SPECS[entity]["write"]:
        return False
    if actor.role == "admin":
        return True
    if record is None:
        return True
    if entity == "courses":
        return record.faculty_id == actor.id
    if entity == "enrollments":
        return record.course.faculty_id == actor.id
    if entity == "attendance":
        return record.enrollment.course.faculty_id == actor.id
    if entity == "examinations":
        return record.course.faculty_id == actor.id
    if entity == "results":
        return record.examination.course.faculty_id == actor.id
    return False


def _can_create(entity, actor):
    if entity == "enrollments" and actor.role == "student":
        return True
    if actor.role not in SPECS[entity]["write"]:
        return False
    return not (entity == "courses" and actor.role == "faculty")


def _writable_fields(entity, actor):
    if actor.role == "admin":
        return set(SPECS[entity]["fields"])
    if actor.role == "student" and entity == "enrollments":
        return {"course_id", "academic_year", "term", "student_id", "status"}
    return set(SPECS[entity].get("faculty_fields", ()))


def _validate_relations(entity, values, actor, record=None):
    values = dict(values)
    if entity == "users":
        if values.get("department_id") is not None:
            department = db.session.get(Department, values["department_id"])
            if department is None:
                return None, "department_id does not identify a department."
        values["email"] = values.get("email", getattr(record, "email", "")).lower()
        return values, None
    if entity == "courses":
        department_id = values.get("department_id", getattr(record, "department_id", None))
        if not db.session.get(Department, department_id):
            return None, "department_id does not identify a department."
        faculty_id = values.get("faculty_id", getattr(record, "faculty_id", None))
        if faculty_id is not None:
            faculty = db.session.get(User, faculty_id)
            if faculty is None or faculty.role != "faculty":
                return None, "faculty_id must identify a faculty account."
    if entity == "enrollments":
        student_id = values.get("student_id", getattr(record, "student_id", None))
        student = db.session.get(User, student_id)
        if student is None or student.role != "student":
            return None, "student_id must identify a student account."
        course_id = values.get("course_id", getattr(record, "course_id", None))
        if db.session.get(Course, course_id) is None:
            return None, "course_id does not identify a course."
    if entity == "attendance":
        enrollment_id = values.get("enrollment_id", getattr(record, "enrollment_id", None))
        enrollment = db.session.get(Enrollment, enrollment_id)
        if enrollment is None:
            return None, "enrollment_id does not identify an enrollment."
        if actor.role == "faculty" and enrollment.course.faculty_id != actor.id:
            return None, "You may only manage attendance for your courses."
        values["recorded_by"] = actor.id
    if entity == "examinations":
        course_id = values.get("course_id", getattr(record, "course_id", None))
        course = db.session.get(Course, course_id)
        if course is None:
            return None, "course_id does not identify a course."
        if actor.role == "faculty" and course.faculty_id != actor.id:
            return None, "You may only manage examinations for your courses."
        total_marks = values.get("total_marks", getattr(record, "total_marks", None))
        if record is not None and total_marks != record.total_marks:
            highest_result = db.session.query(db.func.max(Result.marks)).filter_by(
                examination_id=record.id
            ).scalar()
            if highest_result is not None and total_marks < highest_result:
                return None, "total_marks cannot be lower than an existing result."
    if entity == "results":
        examination_id = values.get("examination_id", getattr(record, "examination_id", None))
        student_id = values.get("student_id", getattr(record, "student_id", None))
        examination = db.session.get(Examination, examination_id)
        student = db.session.get(User, student_id)
        if examination is None:
            return None, "examination_id does not identify an examination."
        if actor.role == "faculty" and examination.course.faculty_id != actor.id:
            return None, "You may only manage results for your courses."
        if student is None or student.role != "student":
            return None, "student_id must identify a student account."
        if not Enrollment.query.filter_by(
            course_id=examination.course_id, student_id=student.id
        ).first():
            return None, "Student is not enrolled in the examination course."
        marks = values.get("marks", getattr(record, "marks", None))
        if marks > examination.total_marks:
            return None, "marks cannot exceed the examination's total_marks."
    if entity == "notices":
        values["created_by"] = actor.id
    return values, None


def _apply_filters(entity, query):
    spec = SPECS[entity]
    for field in spec["filters"]:
        raw_value = request.args.get(field)
        if raw_value is None:
            continue
        converted, error = _convert(field, raw_value, spec["fields"][field])
        if error:
            return None, (jsonify(error=error), 400)
        query = query.filter(getattr(spec["model"], field) == converted)
    search = request.args.get("q", "").strip()
    if search:
        query = query.filter(
            or_(*[
                getattr(spec["model"], field).ilike(f"%{search}%")
                for field in spec["search"]
            ])
        )
    return query, None


@api_bp.get("/dashboard")
@jwt_required()
def dashboard():
    actor = _actor()
    if actor is None:
        return jsonify(error="Account no longer exists."), 401
    return jsonify(data={"user": actor.to_dict(), "summary": dashboard_summary(actor)}), 200


@api_bp.route("/<string:entity>", methods=["GET", "POST"])
@jwt_required()
def collection(entity):
    if entity not in SPECS:
        return jsonify(error="Unknown resource."), 404
    actor = _actor()
    if actor is None:
        return jsonify(error="Account no longer exists."), 401
    if request.method == "GET":
        if actor.role not in SPECS[entity]["read"]:
            return jsonify(error="You are not allowed to view this resource."), 403
        query, error = _apply_filters(entity, scoped_query(entity, actor))
        if error:
            return error
        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(100, max(1, int(request.args.get("per_page", 20))))
        except ValueError:
            return jsonify(error="page and per_page must be integers."), 400
        pagination = query.order_by(SPECS[entity]["model"].id.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        return jsonify(
            data=[_serialize(entity, item) for item in pagination.items],
            meta={
                "page": pagination.page,
                "per_page": pagination.per_page,
                "total": pagination.total,
                "pages": pagination.pages,
            },
        ), 200

    if not _can_create(entity, actor):
        return jsonify(error="You are not allowed to create this resource."), 403
    body, error = _json_body()
    if error:
        return error
    if entity == "enrollments" and actor.role == "student":
        body = dict(body)
        body["student_id"] = actor.id
        body["status"] = "enrolled"
    values, error = _validation(entity, body, creating=True)
    if error:
        return jsonify(error=error), 400
    if set(values) - _writable_fields(entity, actor):
        return jsonify(error="You are not allowed to set one or more fields."), 403
    values, error = _validate_relations(entity, values, actor)
    if error:
        return jsonify(error=error), 400
    try:
        password = values.pop("password", None)
        record = SPECS[entity]["model"](**values)
        if entity == "users":
            record.set_password(password)
        db.session.add(record)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="The record conflicts with an existing record or constraint."), 409
    return jsonify(data=_serialize(entity, record)), 201


@api_bp.route("/<string:entity>/<int:record_id>", methods=["GET", "PATCH", "DELETE"])
@jwt_required()
def resource(entity, record_id):
    if entity not in SPECS:
        return jsonify(error="Unknown resource."), 404
    actor = _actor()
    if actor is None:
        return jsonify(error="Account no longer exists."), 401
    query = scoped_query(entity, actor)
    record = query.filter(SPECS[entity]["model"].id == record_id).first()
    if record is None:
        return jsonify(error="Resource not found."), 404
    if request.method == "GET":
        return jsonify(data=_serialize(entity, record)), 200
    if not _can_write(entity, actor, record):
        return jsonify(error="You are not allowed to modify this resource."), 403
    if request.method == "DELETE":
        if entity == "users" and record.id == actor.id:
            return jsonify(error="You cannot delete your own account."), 400
        db.session.delete(record)
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return jsonify(error="This record is still referenced by other records."), 409
        return "", 204
    body, error = _json_body()
    if error:
        return error
    values, error = _validation(entity, body, creating=False)
    if error:
        return jsonify(error=error), 400
    if set(values) - _writable_fields(entity, actor):
        return jsonify(error="You are not allowed to change one or more fields."), 403
    values, error = _validate_relations(entity, values, actor, record)
    if error:
        return jsonify(error=error), 400
    try:
        password = values.pop("password", None)
        if password is not None:
            if not 10 <= len(password) <= 256:
                return jsonify(error="Password must contain between 10 and 256 characters."), 400
            record.set_password(password)
        for field, value in values.items():
            setattr(record, field, value)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return jsonify(error="The record conflicts with an existing record or constraint."), 409
    return jsonify(data=_serialize(entity, record)), 200
