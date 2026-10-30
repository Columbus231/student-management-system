# Campusly — College Management

Campusly is a role-aware college management application for students, faculty, and administrators. It combines a responsive HTML/CSS/JavaScript dashboard with a versioned Flask REST API and SQLAlchemy persistence.

## Features

- **Students:** create a student account, browse courses, register for a course, and view their own profile, registration, attendance, examination results, and announcements.
- **Faculty:** view assigned courses and enrolled students, update assigned course descriptions, record attendance, create examinations, and manage results for their own courses.
- **Administrators:** manage accounts, departments, courses, registrations, attendance, examinations, results, and announcements.
- Search, filtering, pagination, a health/database check, and role-specific dashboard summaries.
- Password hashing, role checks, HTTP-only JWT cookies, CSRF protection for cookie-authenticated mutations, login rate limits, and production environment checks.
- SQLite for local development and PostgreSQL for production. The application does not create database tables implicitly in production; migrations are explicit.

## Technology

- Python 3.11 or newer, Flask, Flask-SQLAlchemy, Flask-Migrate, SQLAlchemy
- SQLite locally; PostgreSQL using Psycopg in production
- Vanilla HTML, CSS, and JavaScript
- pytest and a Postman collection
- Vercel Python/Flask runtime for the combined deployment

## Project layout

```text
backend/
  app/
    __init__.py          Application factory, extensions, error handlers
    config.py            Environment and database configuration
    models.py            SQLAlchemy models
    routes/
      api.py             Versioned academic-record API
      auth.py            Registration, login, logout, current user
      web.py             Local frontend delivery
  services/              Role-scoped queries and dashboard reporting
  tests/                 API and role-scope tests
  requirements.txt
  server.py              WSGI entry point
frontend/
  index.html
  css/app.css
  js/app.js
database/                Local SQLite database (created when configured)
migrations/              Flask-Migrate revision history
postman/                 Collection and local environment
.env.example
build.py                 Copies frontend assets to Vercel's public/ directory
pyproject.toml           Vercel Python entrypoint/build configuration
vercel.json
```

Vercel serves files in `public/` from its CDN, so the configured build command copies the maintained frontend source there before deployment. Locally, Flask serves the same files from `frontend/`.

## Prerequisites

- Python 3.11+
- Git (for source control)
- Optional: PostgreSQL for production-like local testing; Vercel CLI 48.2.10+ for local Vercel emulation/deployment

## Local setup (Windows PowerShell)

From the project directory:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
Copy-Item .env.example .env
```

Set unique local secrets in `.env` before using the app beyond local development. The example fallback secrets are for local development only. By default, the database is `database/college.db`; set `DATABASE_URL` to override it.

Apply the committed initial migration:

```powershell
python -m flask --app backend.server db upgrade
```

For a brand-new project without the checked-in `migrations/` directory, initialize it once with `python -m flask --app backend.server db init` and generate the first revision with `python -m flask --app backend.server db migrate -m "Initial college management schema"`. For subsequent model changes, create a revision with `python -m flask --app backend.server db migrate -m "Describe the schema change"` and apply it with `python -m flask --app backend.server db upgrade`. Review generated migrations before applying them to production. Do not use `AUTO_CREATE_TABLES=true` in production.

Create the first administrator through the CLI; the CLI requires a 12-character minimum password and does not expose a public admin-registration endpoint:

```powershell
$env:COLLEGE_ADMIN_NAME = "Campus Administrator"
$env:COLLEGE_ADMIN_EMAIL = "admin@your-college.edu"
$env:COLLEGE_ADMIN_PASSWORD = "use-a-unique-password-of-at-least-12-characters"
flask create-admin
Remove-Item Env:COLLEGE_ADMIN_PASSWORD
```

For ongoing use, keep credentials in the ignored `.env` file rather than shell history. Remove the bootstrap values after creating the account.

Start the application:

```powershell
python run.py
```

Open `http://127.0.0.1:5000`. Student self-registration is available from the sign-in screen. Faculty and administrators must be provisioned by an administrator.

### SQLite notes

- `DATABASE_URL` is optional locally. Its default points to `database/college.db`.
- Database files are ignored by Git.
- SQLite is not a suitable production database for Vercel Functions because function filesystems are not persistent or shared between instances.

## Configuration

Copy `.env.example` to `.env`. Important settings:

| Variable | Purpose |
|---|---|
| `FLASK_ENV` | Use `development` locally and `production` when deployed. |
| `SECRET_KEY` | Flask signing secret; provide a long, unique production value. |
| `JWT_SECRET_KEY` | Signs authentication cookies; use a different strong production value. |
| `DATABASE_URL` | SQLAlchemy URL. Leave empty for the local SQLite default; use a managed PostgreSQL URL in production. |
| `CORS_ORIGINS` | Comma-separated allowed origins for credentialed API calls. The default is local development. |
| `FRONTEND_URL` | Documented frontend origin; the default deployment serves frontend and API on the same origin. |
| `RATELIMIT_STORAGE_URI` | Flask-Limiter storage URI. `memory://` is local-only; use a shared Redis-compatible service for multi-instance production limits. |
| `AUTO_CREATE_TABLES` | Optional local convenience; leave `false` and use migrations for normal workflows. |
| `COLLEGE_ADMIN_*` | Temporary bootstrap variables consumed by `flask create-admin`. |

Production/preview startup fails unless `FLASK_ENV` (or Vercel's `VERCEL_ENV`) identifies the deployment, both secrets are at least 32 characters, and a non-SQLite `DATABASE_URL` is configured. `postgres://` and `postgresql://` URLs are normalized to Psycopg 3.

## Database: managed PostgreSQL

1. Create a managed PostgreSQL database with TLS enabled and allow connections from the deployment environment.
2. Store its private connection URL in the deployment's `DATABASE_URL` secret. Do not put credentials in source control or in the browser.
3. Configure `FLASK_ENV=production`, unique `SECRET_KEY` and `JWT_SECRET_KEY`, and the required allowed origins in the hosting environment.
4. Install dependencies and apply reviewed migrations against the target database:

   ```powershell
   $env:DATABASE_URL = "postgresql://..."
   $env:FLASK_ENV = "production"
   flask --app backend.server db upgrade
   ```

5. Verify the deployment at `/health`; it returns `200` with `{"status":"ok","database":"connected"}` only when the database query succeeds.

Use the provider's pooled connection URL if available. The SQLAlchemy pool is intentionally small for serverless deployments. Production rate limiting also needs shared storage; the in-memory default is per process and is not a distributed limit.

## Authentication and authorization

- Student registration is public; the request cannot choose a role.
- Faculty/admin accounts are created by an administrator.
- Passwords are stored as Werkzeug password hashes; password hashes are never serialized.
- Responses set a restrictive content-security policy, frame and MIME-sniffing protections, and a 1 MB request-body limit.
- Login sets a JWT in an HTTP-only cookie and a CSRF cookie. Mutating requests must send the CSRF cookie value in `X-CSRF-TOKEN`.
- Logout revokes the JWT and clears its cookies. Access cookies expire after eight hours.
- Queries are scoped by role: students only see their own registrations, attendance, and results; faculty only see assigned course records and students; administrators can manage all records.
- Admins can create/manage users and academic records. Students can register themselves for courses but cannot change another student's registration.
- Destructive operations return `409` if the record is still referenced. Deleting your own account is blocked.

Do not expose an admin-registration endpoint or store production credentials in frontend code. For a frontend hosted on a different origin, configure `CORS_ORIGINS` precisely and configure cookie `SameSite`/`Secure` behavior for that cross-site topology; same-origin hosting is the supported default.

## REST API

All API routes are under `/api/v1`. Authenticated requests use the secure cookie established by login. Mutating requests require `X-CSRF-TOKEN` from `csrf_access_token`.

| Endpoint | Methods | Access / purpose |
|---|---|---|
| `/health` | GET | Public process and database connectivity check |
| `/api/v1/auth/register` | POST | Public student registration |
| `/api/v1/auth/login` | POST | Set authentication cookies |
| `/api/v1/auth/me` | GET | Current authenticated account |
| `/api/v1/auth/logout` | POST | Revoke and clear current authentication |
| `/api/v1/dashboard` | GET | Role-specific summary |
| `/api/v1/users` | GET, POST | Admin list/create; faculty can list enrolled students; student sees self |
| `/api/v1/departments` | GET, POST | Browse; admin CRUD |
| `/api/v1/courses` | GET, POST | Browse; admin CRUD; assigned faculty can update title/description |
| `/api/v1/enrollments` | GET, POST | Admin CRUD; student can create their own registration |
| `/api/v1/attendance` | GET, POST | Admin/faculty manage; students read their own |
| `/api/v1/examinations` | GET, POST | Admin/faculty manage assigned courses; students read |
| `/api/v1/results` | GET, POST | Admin/faculty manage assigned courses; students read their own |
| `/api/v1/notices` | GET, POST | Read by intended audience; admin CRUD |

Every academic resource also supports `GET /{resource}/{id}`, `PATCH /{resource}/{id}`, and `DELETE /{resource}/{id}` subject to role authorization. Collection endpoints accept `page`, `per_page` (1–100), `q`, and resource-specific field filters. Responses use `data` and paginated collections include `meta`:

```json
{
  "data": [{"id": 8, "code": "CS101", "title": "Foundations of Computing"}],
  "meta": {"page": 1, "per_page": 20, "total": 1, "pages": 1}
}
```

Successful creation returns `201`; reads and updates return `200`; deletion returns `204`. Invalid input returns `400`, unauthenticated requests `401`, forbidden actions `403`, missing records `404`, uniqueness/referential conflicts `409`, and unexpected database failures `500`. Error responses use `{"error":"..."}`.

### Main request fields

- **Registration:** `email`, `password` (10+ characters), `full_name`, optional `student_number`.
- **User (admin):** `email`, `password`, `full_name`, `role` (`student`, `faculty`, `admin`), optional student/faculty number and `department_id`.
- **Department:** `name`, `code`, optional `description`.
- **Course:** `code`, `title`, `department_id`, optional `description`, `credits` (1–30), `faculty_id`.
- **Enrollment:** `student_id` (omitted for self-registration), `course_id`, `academic_year`, `term`; status is set to `enrolled` for student registrations.
- **Attendance:** `enrollment_id`, ISO `date`, status (`present`, `absent`, `late`, `excused`), optional `notes`.
- **Examination:** `course_id`, `title`, ISO `exam_date`, positive `total_marks`.
- **Result:** `examination_id`, `student_id`, `marks` (0 through total marks), optional `grade`, `remarks`. The student must be enrolled in the course.
- **Notice:** `title`, `body`, audience (`all`, `students`, `faculty`, `admins`).

## Postman

Import `postman/College-Management.postman_collection.json` and `postman/Local.postman_environment.json`. Set the environment's admin email/password after creating an admin. The collection covers health, login, authenticated reads, admin department CRUD, validation failures, logout, and cookie-CSRF handling. Postman must accept cookies for the configured host.

To run it using Newman:

```powershell
npm install --global newman
newman run postman/College-Management.postman_collection.json `
  -e postman/Local.postman_environment.json `
  --env-var "admin_email=admin@your-college.edu" `
  --env-var "admin_password=your-admin-password"
```

## Tests

```powershell
pip install -r requirements.txt
python -m pytest
```

The test suite uses an isolated in-memory SQLite database and checks registration, login cookies, authorization, role-scoped reads/writes, validation, CRUD, pagination, health, and logout revocation. Browser-level UI automation is not included.

## Vercel deployment

The project is configured for Vercel's current Python runtime:

- `pyproject.toml` selects `backend.server:app` and runs `build.py`.
- Runtime dependencies are declared in `pyproject.toml` for Vercel; keep them aligned with the root `requirements.txt` used for local setup and tests.
- `build.py` copies the maintained frontend into `public/`, which Vercel serves from its CDN.
- `backend/server.py` exports the Flask WSGI application; `/api/v1/*` and `/health` run through the Python function, and frontend requests use same-origin relative URLs.
- `vercel.json` provides the Vercel configuration schema. No custom API rewrite is required for the Flask framework preset.
- `vercel.json` also applies baseline security headers to CDN-served frontend assets; the Flask app sets the equivalent headers for local/function responses.

Deployment steps:

1. Push the project to a Git repository and import it into Vercel (or use Vercel CLI 48.2.10+).
2. Add production `FLASK_ENV`, `DATABASE_URL`, `SECRET_KEY`, and `JWT_SECRET_KEY` environment variables. Set `CORS_ORIGINS` to the exact public site origin; keep the frontend and API on the same Vercel domain.
3. Configure a managed PostgreSQL instance; never configure SQLite for a production deployment.
4. Apply migrations against production PostgreSQL before serving traffic, using a controlled deployment job or local CLI with protected credentials. Do not run migration commands automatically in every serverless startup.
5. Deploy and verify `/health`, login, and an authenticated workflow. Do not consider the database workflow validated until the deployed environment has been tested.

Vercel's Python runtime supports Flask/WSGI applications, but a deployed function is not a persistent server: local filesystem writes and SQLite are not durable/shared; background workers and long-lived processes need separate services. This app does not claim a completed production deployment or an external database connection from this workspace.

Current references: [Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python), [Deploy a Flask app](https://vercel.com/docs/frameworks/backend/flask).

## GitHub and security operations

1. Create a private or public repository as appropriate and push the source without `.env`, database files, or credentials.
2. Protect the production branch and review migration files before deployment.
3. Rotate `SECRET_KEY`, `JWT_SECRET_KEY`, database credentials, and bootstrap passwords through the hosting provider if exposed.
4. For production rate limiting, configure shared Redis-compatible storage with `RATELIMIT_STORAGE_URI`; `memory://` is not shared across instances.
5. Review role access rules and retention requirements with the institution before importing real student records.

## Troubleshooting

- **`flask` command not found:** activate `.venv` and reinstall `requirements.txt`.
- **Missing tables:** run `flask --app backend.server db upgrade` after creating the initial migration.
- **Production startup fails:** check `FLASK_ENV=production`, PostgreSQL `DATABASE_URL`, and both secret variables.
- **PostgreSQL connection errors:** verify the URL, TLS mode, database allowlist, and provider connection-pooler settings.
- **401 after login:** allow cookies for the application origin and avoid switching between `localhost` and `127.0.0.1`.
- **403 on a mutation:** preserve the `csrf_access_token` cookie and send its value in `X-CSRF-TOKEN`; also verify the account's role and course assignment.
- **Postman cookie issues:** use the Postman desktop app or enable its cookie jar for the same `base_url` host.
