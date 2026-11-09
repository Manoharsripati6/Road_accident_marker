# Smart Accident Black Spot Mapping System

RoadSafe is a modular Flask application for collecting accident reports, validating evidence, detecting geographic accident clusters and guiding local road-safety action. It uses SQLite and Python's standard `sqlite3` module—no database server, scientific stack, or compiled packages are required.

## Features

- Session authentication with securely hashed passwords and Administrator / General User roles.
- CSRF-protected registration, sign-in, report submission, review, edit, delete and settings forms.
- Pending → verified / rejected administrator review workflow.
- Validated accident reporting with location, coordinates, time, type, road users, severity, casualties, narrative and optional image evidence.
- SQLite storage for users, reports, reusable locations, black spots, classifications and detector settings.
- Pure-Python haversine clustering: no `scikit-learn`, NumPy or C/C++ extensions.
- Leaflet/OpenStreetMap risk map with search and severity, accident-type and risk filters.
- Dashboard, chart analytics, actual-statistic safety recommendations, location-frequency analysis and filtered CSV export.
- Configurable clustering radius and minimum evidence threshold; a single accident can never form a black spot.

## Install and run on Windows

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Open `http://127.0.0.1:5000` in a browser. The database is created automatically at `instance/accidents.db` on the first start.

## Administrator account

At startup, the application creates the configured administrator if the email does not already exist. Set these values in `.env` **before the first run**:

```dotenv
SECRET_KEY=a-long-random-secret-value
ADMIN_NAME=Road Safety Administrator
ADMIN_EMAIL=admin@roadsafe.local
ADMIN_PASSWORD=Choose-a-strong-password
```

The default development credentials are `admin@roadsafe.local` / `ChangeMe123!`. Change them before anyone else can access the app. Existing accounts are deliberately never overwritten from environment variables.

`DATABASE_PATH` is optional and defaults to `instance/accidents.db`. Set `SESSION_COOKIE_SECURE=true` when deploying over HTTPS.

## Demo data

With the virtual environment activated, run this once on an empty report database:

```powershell
flask --app app seed-demo
```

It adds six verified demonstration reports and recalculates clusters. The command refuses to add demo data if reports already exist. To initialise the schema explicitly, use:

```powershell
flask --app app init-db
```

## Black spot logic

Only `verified` reports participate. For every pair of verified locations, the application calculates their great-circle distance with the haversine formula. Reports at or within the configured radius are joined into connected components. Components smaller than the configured minimum (default: three) are ignored.

For each qualifying component, its centre is the mean latitude/longitude and its severity-weighted risk score is:

```text
(Low reports × 1) + (Medium reports × 2) + (High reports × 3) + (recorded casualties × 0.5)
```

Risk bands scale with the current minimum component size: high risk begins at 2.8 × the minimum, or when two high-severity reports occur in the same cluster; medium begins at 1.8 × the minimum; otherwise the qualifying cluster is low risk. Administrators can set a 50–5,000 metre radius and a 2–20 report minimum in **Detection settings**. Save any change to rebuild the derived `black_spots` and `risk_classifications` tables.

These thresholds are transparent defaults, not official safety standards. Validate and calibrate them against local road geometry, reporting practices and engineering policy before operational use.

## Project layout

```text
app.py                         Application factory, CSRF and CLI commands
config.py                      Environment-backed configuration
database.py                    SQLite schema and query helpers
modules/
  authentication.py            Registration, sign-in, session and role guards
  accident_reporting.py        Submission, upload validation and records
  admin.py                     Validation, edits, deletion, users and settings
  analytics.py                 Dashboard, charts, map API and analysis pages
  blackspot_detection.py       Pure-Python spatial detection and persistence
  recommendations.py           Data-driven rule-based safety actions
  reports.py                   Filters and standard-library CSV export
templates/                     Reusable Jinja pages
static/css/style.css           Responsive RoadSafe design system
static/js/map.js               Leaflet rendering and in-map filters
instance/accidents.db          Automatically generated SQLite database
```

## Operational notes

- Uploaded image types are checked by extension and MIME type and are capped at 5 MiB.
- Database access always uses parameterised SQLite queries; Jinja autoescaping protects rendered text.
- The built-in development server is for local use. Deploy behind HTTPS with a production WSGI server, a durable upload store, backups, monitoring and a managed secret before production use.
- OpenStreetMap tile and CDN access require a browser internet connection.
