# Resource Planner — Background Jobs

Standalone Python scripts that trigger jobs either in-process (direct mode) or via HTTP
against the running Django server (api mode).

## Available Jobs

| Job name              | Description                                              | Recommended schedule |
|-----------------------|----------------------------------------------------------|----------------------|
| `sprint_status`       | Update `Sprint.is_active` based on today's date          | Daily 00:05          |
| `financial_year_status` | Update `FinancialYear.is_active` based on today's date | Daily 00:05          |
| `data_retention`      | Delete records older than `DATA_RETENTION_YEARS` (default 7 years) | Daily 01:00 |

---

## Modes

### direct (default)
Bootstraps Django in-process. Requires the DB and all Django dependencies in the environment.

```
python run_job.py sprint_status
python run_job.py data_retention --log-level DEBUG
```

### api
Calls the running Django server via `POST /api/v1/jobs/{name}/run/`.
Requires two environment variables:

| Variable | Description |
|---|---|
| `JOB_API_BASE_URL` | Base URL of the running server, e.g. `http://localhost:8000` |
| `JOB_SERVICE_TOKEN` | Shared secret — must match the server's `JOB_SERVICE_TOKEN` setting |

```
python run_job.py sprint_status --mode api
python run_job.py data_retention --mode api --api-url http://myserver:8000
```

The `--api-url` flag overrides `JOB_API_BASE_URL` for a single run.

---

## Server-side token setup

Set `JOB_SERVICE_TOKEN` to a strong random string in the server's environment (or `.env`):

```
JOB_SERVICE_TOKEN=change-me-use-a-long-random-string
```

The server validates `Authorization: Token <value>` on every job request. If the env var is
empty the endpoint returns 401 for all requests.

Generate a suitable token:

```powershell
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Windows Task Scheduler setup

### direct mode (server on the same machine)

1. Open **Task Scheduler** → **Create Basic Task**
2. **Name**: `RP – Sprint Status`
3. **Trigger**: Daily, 12:05 AM
4. **Action**: Start a program
   - **Program**: `C:\path\to\venv\Scripts\python.exe`
   - **Arguments**: `C:\path\to\resourceplanner\run_job.py sprint_status`
   - **Start in**: `C:\path\to\resourceplanner`
5. Repeat for `financial_year_status` and `data_retention`.

PowerShell shortcut:

```powershell
$base   = "C:\path\to\resourceplanner"
$python = "C:\path\to\venv\Scripts\python.exe"

foreach ($job in @("sprint_status", "financial_year_status", "data_retention")) {
    $action  = New-ScheduledTaskAction -Execute $python -Argument "$base\run_job.py $job" -WorkingDirectory $base
    $trigger = New-ScheduledTaskTrigger -Daily -At "01:00AM"
    Register-ScheduledTask -TaskName "RP - $job" -Action $action -Trigger $trigger -RunLevel Highest -Force
}
```

### api mode (server running elsewhere)

Set `JOB_API_BASE_URL` and `JOB_SERVICE_TOKEN` as **system** environment variables, then:

```powershell
$base   = "C:\path\to\resourceplanner"
$python = "C:\path\to\venv\Scripts\python.exe"

foreach ($job in @("sprint_status", "financial_year_status", "data_retention")) {
    $action  = New-ScheduledTaskAction -Execute $python -Argument "$base\run_job.py $job --mode api" -WorkingDirectory $base
    $trigger = New-ScheduledTaskTrigger -Daily -At "01:00AM"
    Register-ScheduledTask -TaskName "RP - $job" -Action $action -Trigger $trigger -RunLevel Highest -Force
}
```

---

## AWS Lambda (Production)

The recommended Lambda pattern is **api mode**: Lambda calls the already-running Django server
via HTTP rather than bootstrapping Django itself. This avoids cold-start overhead and keeps the
Lambda package minimal.

### Handler code

```python
# lambda_function.py
import json, os
from jobs.http_client import run_job_via_api

def lambda_handler(event, context):
    job_name = event.get('job') or event.get('job_name')
    if not job_name:
        return {'statusCode': 400, 'body': json.dumps({'error': 'missing job name'})}
    try:
        result = run_job_via_api(job_name)
        return {'statusCode': 200, 'body': json.dumps(result, default=str)}
    except RuntimeError as exc:
        return {'statusCode': 500, 'body': json.dumps({'error': str(exc)})}
```

### Required Lambda environment variables

| Variable | Example |
|---|---|
| `JOB_API_BASE_URL` | `https://app.example.com` |
| `JOB_SERVICE_TOKEN` | `<same value as server>` |

### EventBridge scheduled triggers

Create one rule per job with a **Constant JSON** input:

```json
{"job": "sprint_status"}
```

### IAM permissions

The Lambda execution role needs no database access — all DB operations happen server-side.
The role only needs network access to reach `JOB_API_BASE_URL`.
