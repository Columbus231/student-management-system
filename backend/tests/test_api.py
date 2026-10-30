from backend.tests.conftest import login


def test_health_and_authentication_required(client):
    assert client.get("/health").json == {"status": "ok", "database": "connected"}
    response = client.get("/api/v1/users")
    assert response.status_code == 401
    assert response.json["error"] == "Authentication required."


def test_frontend_assets_and_unknown_routes(client):
    page = client.get("/")
    assert page.status_code == 200
    assert b"Campusly | College Management" in page.data
    assert page.headers["X-Content-Type-Options"] == "nosniff"
    assert page.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]

    stylesheet = client.get("/css/app.css")
    assert stylesheet.status_code == 200
    assert stylesheet.mimetype == "text/css"

    script = client.get("/js/app.js")
    assert script.status_code == 200
    assert b'const API = "/api/v1"' in script.data

    missing = client.get("/not-a-frontend-asset")
    assert missing.status_code == 404
    assert missing.json["error"] == "Resource not found."


def test_production_configuration_rejects_sqlite():
    import pytest

    from backend.app import create_app

    with pytest.raises(RuntimeError, match="Production requires"):
        create_app(
            {
                "ENVIRONMENT": "production",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SECRET_KEY": "test-secret-key-with-at-least-thirty-two-characters",
                "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-thirty-two-characters",
            }
        )


def test_vercel_environment_without_deployment_settings_fails_closed(monkeypatch):
    import pytest

    from backend.app import create_app

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("VERCEL_ENV", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("JWT_SECRET_KEY", raising=False)
    with pytest.raises(RuntimeError, match="Production requires"):
        create_app(
            {
                "ENVIRONMENT": "development",
                "SQLALCHEMY_DATABASE_URI": "sqlite://",
                "SECRET_KEY": "local-secret",
                "JWT_SECRET_KEY": "local-jwt-secret",
            }
        )


def test_vercel_production_configuration_uses_postgresql_without_auto_create(monkeypatch):
    import pytest

    from backend.app import create_app, db

    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.setenv("VERCEL_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql://campus:secret@example.com/campus")
    monkeypatch.setenv("SECRET_KEY", "s" * 40)
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 40)
    monkeypatch.setattr(
        db,
        "create_all",
        lambda: pytest.fail("Production app startup must not create database tables."),
    )
    app = create_app(
        {
            "ENVIRONMENT": "production",
            "SQLALCHEMY_DATABASE_URI": "postgresql://campus:secret@example.com/campus",
            "SECRET_KEY": "s" * 40,
            "JWT_SECRET_KEY": "j" * 40,
            "AUTO_CREATE_TABLES": False,
        }
    )

    assert app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql+psycopg://")
    assert app.config["AUTO_CREATE_TABLES"] is False
    with app.app_context():
        assert db.engine.url.drivername == "postgresql+psycopg"


def test_student_registration_and_login_cookie(client):
    response = client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "New Student",
            "email": "new.student@example.edu",
            "password": "New-student-password-123",
            "role": "admin",
        },
    )
    assert response.status_code == 400
    assert client.post(
        "/api/v1/auth/register",
        json={
            "full_name": "New Student",
            "email": "new.student@example.edu",
            "password": "New-student-password-123",
        },
    ).status_code == 201
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "new.student@example.edu", "password": "New-student-password-123"},
    )
    assert response.status_code == 200
    assert "access_token_cookie" in response.headers.get("Set-Cookie", "")
    assert "HttpOnly" in response.headers.get("Set-Cookie", "")
    assert response.json["data"]["user"]["role"] == "student"
    assert client.get("/api/v1/auth/me").json["data"]["email"] == "new.student@example.edu"


def test_admin_crud_validation_and_pagination(client):
    csrf = login(client, "admin@example.edu", "Admin-password-123")
    assert client.post(
        "/api/v1/departments",
        json={"name": "Blocked", "code": "BLOCK"},
    ).status_code == 401
    assert client.post("/api/v1/departments", json={"name": "Missing code"}, headers=csrf).status_code == 400
    created = client.post(
        "/api/v1/departments",
        json={"name": "Mathematics", "code": "MATH", "description": "Numbers and patterns"},
        headers=csrf,
    )
    assert created.status_code == 201
    department_id = created.json["data"]["id"]
    listed = client.get("/api/v1/departments?page=1&per_page=1")
    assert listed.status_code == 200
    assert listed.json["meta"]["per_page"] == 1
    assert listed.json["meta"]["total"] == 2
    updated = client.patch(
        f"/api/v1/departments/{department_id}",
        json={"description": "Pure and applied mathematics"},
        headers=csrf,
    )
    assert updated.status_code == 200
    assert updated.json["data"]["description"] == "Pure and applied mathematics"
    assert client.delete(f"/api/v1/departments/{department_id}", headers=csrf).status_code == 204
    assert client.delete("/api/v1/departments/1", headers=csrf).status_code == 409


def test_students_only_see_their_own_records_and_can_self_enroll(client, app):
    csrf = login(client, "student@example.edu", "Student-password-123")
    results = client.get("/api/v1/results")
    assert results.status_code == 200
    assert len(results.json["data"]) == 1
    assert results.json["data"][0]["student_name"] == "First Student"
    enroll = client.post(
        "/api/v1/enrollments",
        json={
            "student_id": app.test_data["other_student"],
            "course_id": app.test_data["other_course"],
            "academic_year": "2026-27",
            "term": "Spring",
        },
        headers=csrf,
    )
    assert enroll.status_code == 201
    assert enroll.json["data"]["student_id"] == app.test_data["student"]
    assert enroll.json["data"]["status"] == "enrolled"
    assert client.get("/api/v1/users").json["data"][0]["id"] == app.test_data["student"]
    assert client.post(
        "/api/v1/users",
        json={"email": "bad@example.edu"},
        headers=csrf,
    ).status_code == 403


def test_faculty_scope_blocks_other_course_attendance(client, app):
    csrf = login(client, "faculty@example.edu", "Faculty-password-123")
    courses = client.get("/api/v1/courses")
    assert [course["id"] for course in courses.json["data"]] == [app.test_data["course"]]
    response = client.post(
        "/api/v1/attendance",
        json={
            "enrollment_id": app.test_data["other_faculty_enrollment"],
            "date": "2026-10-30",
            "status": "present",
        },
        headers=csrf,
    )
    assert response.status_code == 400
    assert client.post(
        "/api/v1/courses",
        json={
            "code": "CS303",
            "title": "New course",
            "department_id": 1,
        },
        headers=csrf,
    ).status_code == 403
    attendance = client.post(
        "/api/v1/attendance",
        json={
            "enrollment_id": app.test_data["enrollment"],
            "date": "2026-10-30",
            "status": "present",
        },
        headers=csrf,
    )
    assert attendance.status_code == 201
    examination = client.post(
        "/api/v1/examinations",
        json={
            "course_id": app.test_data["course"],
            "title": "Final",
            "exam_date": "2026-12-10",
            "total_marks": 100,
        },
        headers=csrf,
    )
    assert examination.status_code == 201
    result = client.post(
        "/api/v1/results",
        json={
            "examination_id": examination.json["data"]["id"],
            "student_id": app.test_data["student"],
            "marks": 89,
            "grade": "A",
        },
        headers=csrf,
    )
    assert result.status_code == 201


def test_logout_revokes_the_cookie(client):
    csrf = login(client, "student@example.edu", "Student-password-123")
    assert client.get("/api/v1/auth/me").status_code == 200
    response = client.post("/api/v1/auth/logout", json={}, headers=csrf)
    assert response.status_code == 200
    assert client.get("/api/v1/auth/me").status_code == 401
