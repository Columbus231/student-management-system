from datetime import date

import pytest

from backend.app import create_app, db
from backend.app.models import Course, Department, Enrollment, Examination, Result, User


@pytest.fixture()
def app():
    app = create_app(
        {
            "TESTING": True,
            "ENVIRONMENT": "testing",
            "SECRET_KEY": "test-secret-key-with-at-least-thirty-two-characters",
            "JWT_SECRET_KEY": "test-jwt-secret-with-at-least-thirty-two-characters",
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "RATELIMIT_ENABLED": False,
            "CORS_ORIGINS": ["http://localhost"],
        }
    )
    with app.app_context():
        db.create_all()
        department = Department(name="Computing", code="COMP")
        db.session.add(department)
        db.session.flush()
        admin = User(email="admin@example.edu", full_name="Campus Admin", role="admin")
        admin.set_password("Admin-password-123")
        faculty = User(
            email="faculty@example.edu",
            full_name="Faculty Member",
            role="faculty",
            faculty_number="F-101",
            department_id=department.id,
        )
        faculty.set_password("Faculty-password-123")
        other_faculty = User(
            email="other@example.edu",
            full_name="Other Faculty",
            role="faculty",
        )
        other_faculty.set_password("Other-password-123")
        student = User(
            email="student@example.edu",
            full_name="First Student",
            role="student",
            student_number="S-101",
        )
        student.set_password("Student-password-123")
        other_student = User(
            email="student2@example.edu",
            full_name="Second Student",
            role="student",
            student_number="S-102",
        )
        other_student.set_password("Student-password-456")
        db.session.add_all([admin, faculty, other_faculty, student, other_student])
        db.session.flush()
        course = Course(
            code="CS101",
            title="Foundations of Computing",
            credits=3,
            department_id=department.id,
            faculty_id=faculty.id,
        )
        other_course = Course(
            code="CS202",
            title="Data Systems",
            credits=3,
            department_id=department.id,
            faculty_id=other_faculty.id,
        )
        db.session.add_all([course, other_course])
        db.session.flush()
        enrollment = Enrollment(
            student_id=student.id,
            course_id=course.id,
            academic_year="2026-27",
            term="Fall",
        )
        other_enrollment = Enrollment(
            student_id=other_student.id,
            course_id=course.id,
            academic_year="2026-27",
            term="Fall",
        )
        other_faculty_enrollment = Enrollment(
            student_id=student.id,
            course_id=other_course.id,
            academic_year="2026-27",
            term="Fall",
        )
        db.session.add_all([enrollment, other_enrollment, other_faculty_enrollment])
        db.session.flush()
        exam = Examination(
            course_id=course.id,
            title="Midterm",
            exam_date=date(2026, 10, 10),
            total_marks=100,
        )
        db.session.add(exam)
        db.session.flush()
        db.session.add_all(
            [
                Result(examination_id=exam.id, student_id=student.id, marks=90, grade="A"),
                Result(examination_id=exam.id, student_id=other_student.id, marks=75, grade="B"),
            ]
        )
        db.session.commit()
        app.test_data = {
            "admin": admin.id,
            "faculty": faculty.id,
            "other_faculty": other_faculty.id,
            "student": student.id,
            "other_student": other_student.id,
            "course": course.id,
            "other_course": other_course.id,
            "enrollment": enrollment.id,
            "other_faculty_enrollment": other_faculty_enrollment.id,
            "exam": exam.id,
            "department": department.id,
        }
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def login(client, email, password):
    response = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    csrf_cookie = client.get_cookie("csrf_access_token")
    assert csrf_cookie is not None
    return {"X-CSRF-TOKEN": csrf_cookie.value}
