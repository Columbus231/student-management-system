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

RESOURCE_MODELS = {
    "users": User,
    "departments": Department,
    "courses": Course,
    "enrollments": Enrollment,
    "attendance": Attendance,
    "examinations": Examination,
    "results": Result,
    "notices": Notice,
}


def scoped_query(entity, actor):
    query = RESOURCE_MODELS[entity].query
    if actor.role == "admin":
        return query
    if entity == "users":
        if actor.role == "faculty":
            return (
                query.join(Enrollment, Enrollment.student_id == User.id)
                .join(Course)
                .filter(Course.faculty_id == actor.id, User.role == "student")
                .distinct()
            )
        return query.filter(User.id == actor.id)
    if actor.role == "student":
        if entity == "enrollments":
            return query.filter(Enrollment.student_id == actor.id)
        if entity == "attendance":
            return query.join(Enrollment).filter(Enrollment.student_id == actor.id)
        if entity == "results":
            return query.filter(Result.student_id == actor.id)
        if entity == "notices":
            return query.filter(Notice.audience.in_(["all", "students"]))
        return query
    if actor.role == "faculty":
        if entity == "courses":
            return query.filter(Course.faculty_id == actor.id)
        if entity == "enrollments":
            return query.join(Course).filter(Course.faculty_id == actor.id)
        if entity == "attendance":
            return query.join(Enrollment).join(Course).filter(Course.faculty_id == actor.id)
        if entity == "examinations":
            return query.join(Course).filter(Course.faculty_id == actor.id)
        if entity == "results":
            return query.join(Examination).join(Course).filter(Course.faculty_id == actor.id)
        if entity == "notices":
            return query.filter(Notice.audience.in_(["all", "faculty"]))
        return query
    return query.filter(db.false())


def dashboard_summary(actor):
    if actor.role == "admin":
        return {
            "students": User.query.filter_by(role="student").count(),
            "faculty": User.query.filter_by(role="faculty").count(),
            "courses": Course.query.count(),
            "departments": Department.query.count(),
            "pending_enrollments": Enrollment.query.filter_by(status="enrolled").count(),
        }
    if actor.role == "faculty":
        courses = Course.query.filter_by(faculty_id=actor.id).all()
        course_ids = [course.id for course in courses]
        student_count = (
            db.session.query(Enrollment.student_id)
            .filter(Enrollment.course_id.in_(course_ids))
            .distinct()
            .count()
            if course_ids else 0
        )
        return {
            "courses": len(courses),
            "students": student_count,
            "examinations": Examination.query.filter(Examination.course_id.in_(course_ids)).count()
            if course_ids else 0,
        }

    enrollment_ids = [
        enrollment.id for enrollment in Enrollment.query.filter_by(student_id=actor.id).all()
    ]
    attendance = (
        Attendance.query.filter(Attendance.enrollment_id.in_(enrollment_ids)).all()
        if enrollment_ids else []
    )
    return {
        "courses": len(enrollment_ids),
        "attendance_records": len(attendance),
        "attendance_percentage": round(
            sum(item.status in {"present", "late"} for item in attendance) * 100
            / len(attendance),
            1,
        ) if attendance else 0,
        "results": Result.query.filter_by(student_id=actor.id).count(),
    }
