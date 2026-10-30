import os
from flask import Flask, jsonify
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
limiter = Limiter(key_func=get_remote_address)


def create_app(test_config=None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object("backend.app.config.Config")
    if test_config:
        app.config.update(test_config)

    database_url = app.config.get("SQLALCHEMY_DATABASE_URI")
    if database_url and database_url.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url.replace(
            "postgres://", "postgresql+psycopg://", 1
        )
    elif database_url and database_url.startswith("postgresql://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url.replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    is_postgresql = app.config["SQLALCHEMY_DATABASE_URI"].startswith(
        ("postgresql://", "postgresql+psycopg://")
    )
    is_deployment = app.config.get("ENVIRONMENT") in {"production", "preview"} or (
        os.getenv("VERCEL") == "1"
    )
    if is_deployment and (
        not os.getenv("SECRET_KEY")
        or not os.getenv("JWT_SECRET_KEY")
        or not os.getenv("DATABASE_URL")
        or not is_postgresql
        or app.config.get("AUTO_CREATE_TABLES")
        or len(os.getenv("SECRET_KEY", "")) < 32
        or len(os.getenv("JWT_SECRET_KEY", "")) < 32
    ):
        raise RuntimeError(
            "Production requires 32-character SECRET_KEY and JWT_SECRET_KEY values, "
            "a PostgreSQL DATABASE_URL, and migrations instead of AUTO_CREATE_TABLES."
        )

    db.init_app(app)
    if app.config["CORS_ORIGINS"]:
        CORS(
            app,
            origins=app.config["CORS_ORIGINS"],
            supports_credentials=True,
            allow_headers=["Content-Type", "X-CSRF-TOKEN"],
        )
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)

    from backend.app.models import RevokedToken
    from backend.app.routes.api import api_bp
    from backend.app.routes.auth import auth_bp
    from backend.app.routes.web import web_bp

    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(api_bp, url_prefix="/api/v1")
    app.register_blueprint(web_bp)

    @jwt.token_in_blocklist_loader
    def is_token_revoked(_jwt_header, jwt_payload):
        return db.session.get(RevokedToken, jwt_payload["jti"]) is not None

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return jsonify(error="Authentication required."), 401

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return jsonify(error="Invalid authentication token."), 401

    @jwt.expired_token_loader
    def expired_token(_jwt_header, _jwt_payload):
        return jsonify(error="Authentication token has expired."), 401

    @jwt.revoked_token_loader
    def revoked_token(_jwt_header, _jwt_payload):
        return jsonify(error="Authentication token has been revoked."), 401

    @app.errorhandler(404)
    def not_found(_error):
        return jsonify(error="Resource not found."), 404

    @app.errorhandler(405)
    def method_not_allowed(_error):
        return jsonify(error="Method not allowed."), 405

    @app.errorhandler(413)
    def request_too_large(_error):
        return jsonify(error="Request body exceeds the 1 MB limit."), 413

    @app.errorhandler(429)
    def too_many_requests(_error):
        return jsonify(error="Too many requests. Please try again later."), 429

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
            "base-uri 'self'; frame-ancestors 'none'",
        )
        return response

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.exception("Database request failed: %s", error)
        return jsonify(error="Database request failed."), 500

    @app.cli.command("create-admin")
    def create_admin():
        """Create an administrator using COLLEGE_ADMIN_* environment variables."""
        from backend.app.models import User

        email = os.getenv("COLLEGE_ADMIN_EMAIL", "").strip().lower()
        password = os.getenv("COLLEGE_ADMIN_PASSWORD", "")
        name = os.getenv("COLLEGE_ADMIN_NAME", "").strip()
        if not email or not password or not name:
            raise RuntimeError(
                "Set COLLEGE_ADMIN_EMAIL, COLLEGE_ADMIN_PASSWORD, and COLLEGE_ADMIN_NAME."
            )
        if len(password) < 12:
            raise RuntimeError("Administrator password must be at least 12 characters.")
        if User.query.filter_by(email=email).first():
            raise RuntimeError("An account already exists for that email.")
        user = User(email=email, full_name=name, role="admin")
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        print(f"Administrator created: {email}")

    if app.config.get("AUTO_CREATE_TABLES"):
        with app.app_context():
            db.create_all()

    @app.get("/health")
    def health():
        try:
            db.session.execute(db.text("SELECT 1"))
        except SQLAlchemyError as error:
            db.session.rollback()
            app.logger.exception("Health check database query failed: %s", error)
            return jsonify(status="error", database="unavailable"), 503
        return jsonify(status="ok", database="connected"), 200

    return app
