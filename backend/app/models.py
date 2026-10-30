from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

from backend.app import db


class User(db.Model):
    __tablename__ = "users"
    __table_args__ = (
        db.CheckConstraint("role IN ('admin', 'faculty', 'student')", name="valid_user_role"),
    )

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(254), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    student_number = db.Column(db.String(40), unique=True)
    faculty_number = db.Column(db.String(40), unique=True)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    department = db.relationship("Department", back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "role": self.role,
            "student_number": self.student_number,
            "faculty_number": self.faculty_number,
            "department_id": self.department_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False, unique=True)
    code = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text)

    users = db.relationship("User", back_populates="department")
    courses = db.relationship("Course", back_populates="department")


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(30), nullable=False, unique=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    credits = db.Column(db.Integer, nullable=False, default=3)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), nullable=False)
    faculty_id = db.Column(db.Integer, db.ForeignKey("users.id"))

    department = db.relationship("Department", back_populates="courses")
    faculty = db.relationship("User", foreign_keys=[faculty_id])
    enrollments = db.relationship("Enrollment", back_populates="course")


class Enrollment(db.Model):
    __tablename__ = "enrollments"
    __table_args__ = (
        db.UniqueConstraint("student_id", "course_id", "academic_year", "term"),
    )

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    academic_year = db.Column(db.String(20), nullable=False)
    term = db.Column(db.String(30), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="enrolled")

    student = db.relationship("User", foreign_keys=[student_id])
    course = db.relationship("Course", back_populates="enrollments")
    attendance_records = db.relationship("Attendance", back_populates="enrollment")


class Attendance(db.Model):
    __tablename__ = "attendance"
    __table_args__ = (
        db.UniqueConstraint("enrollment_id", "date"),
        db.CheckConstraint("status IN ('present', 'absent', 'late', 'excused')"),
    )

    id = db.Column(db.Integer, primary_key=True)
    enrollment_id = db.Column(db.Integer, db.ForeignKey("enrollments.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    notes = db.Column(db.String(500))

    enrollment = db.relationship("Enrollment", back_populates="attendance_records")
    recorder = db.relationship("User", foreign_keys=[recorded_by])


class Examination(db.Model):
    __tablename__ = "examinations"

    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey("courses.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    exam_date = db.Column(db.Date, nullable=False)
    total_marks = db.Column(db.Float, nullable=False)
    course = db.relationship("Course")
    results = db.relationship("Result", back_populates="examination")


class Result(db.Model):
    __tablename__ = "results"
    __table_args__ = (
        db.UniqueConstraint("examination_id", "student_id"),
        db.CheckConstraint("marks >= 0"),
    )

    id = db.Column(db.Integer, primary_key=True)
    examination_id = db.Column(db.Integer, db.ForeignKey("examinations.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    marks = db.Column(db.Float, nullable=False)
    grade = db.Column(db.String(5))
    remarks = db.Column(db.String(500))

    examination = db.relationship("Examination", back_populates="results")
    student = db.relationship("User", foreign_keys=[student_id])


class Notice(db.Model):
    __tablename__ = "notices"
    __table_args__ = (
        db.CheckConstraint(
            "audience IN ('all', 'students', 'faculty', 'admins')",
            name="valid_notice_audience",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    audience = db.Column(db.String(20), nullable=False, default="all")
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    author = db.relationship("User", foreign_keys=[created_by])


class RevokedToken(db.Model):
    __tablename__ = "revoked_tokens"

    jti = db.Column(db.String(36), primary_key=True)
    revoked_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
