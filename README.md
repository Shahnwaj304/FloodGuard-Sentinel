# FloodGuard Sentinel

FloodGuard Sentinel is a Flask-based cloud application prototype for Nepal Himalayan flood and multi-hazard situational awareness. It combines current modelled weather context, a real Copernicus Sentinel catalogue search, staff review workflows, and links to official warning authorities.

## What is live vs. what is not

### Integrated external data

- **Open-Meteo Forecast API:** current modelled temperature, relative humidity, precipitation, rain and wind at configured monitoring coordinates. Responses are cached for 15 minutes and the UI shows model time and request time.
- **Copernicus Data Space STAC API:** queries Sentinel-1 GRD and Sentinel-2 L2A product metadata intersecting a bounding box around Nepal for the most recent 30 days. It shows product IDs and acquisition metadata when returned by the API.
- **DHM:** linked as the authoritative source for official forecasts and warnings. This project does not claim an automated DHM API integration or copy official warning messages into the app.

Weather model output is not a river-gauge reading or validated flood prediction. Satellite catalogue results are metadata, not processed flood maps or confirmed flood detections. The application does not issue official warnings or send emergency notifications. If external services fail, the application shows an unavailable state instead of fabricated values.

### Staff workflows

- Role-protected staff login and observation entry.
- Risk assessments require a written rationale and are explicitly labelled as internal workflow records.
- Application alerts are saved as drafts and are not sent to the public.
- New databases seed staff accounts, configured monitoring locations and preparedness guidance only. They do not seed sample observations, risk assessments or alerts.
- When `DEMO_MODE=false`, legacy rows marked as demo are removed at startup and demo rows are excluded from public lists.

## Local setup (macOS/Linux)

Python 3.10+ is recommended. Python 3.14 may work, but use the version supported by your deployment platform and dependencies.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` before running:

```dotenv
SECRET_KEY=replace-with-a-long-random-secret
DATABASE_URL=sqlite:///floodguard.db
DEMO_MODE=false
AWS_REGION=ap-south-1
S3_BUCKET_NAME=
CLOUDWATCH_LOG_GROUP=
CLOUDWATCH_LOG_STREAM=floodguard-app
LOG_LEVEL=INFO
INITIAL_STAFF_PASSWORD=replace-with-a-unique-initial-password
```

Then run:

```bash
python run.py
```

Open `http://127.0.0.1:5000`.

### Existing local database note

The app removes old records with `is_demo=true` when it starts with `DEMO_MODE=false`. Back up your database before first startup if you want to retain old illustrative records for reference. This does not delete configured locations or staff-entered records marked non-demo.

## Staff accounts

On a fresh database, the app creates `admin`, `satellite`, and `risk` accounts. Their initial password comes from `INITIAL_STAFF_PASSWORD`; if that variable is absent, the development fallback is `Demo123!Change`. Set a unique value before creating a production database, then rotate credentials and deactivate accounts that are not needed. Do not expose development credentials on a public deployment.

## Tests

```bash
python -m pytest -v
```

The test suite does not require live internet access. External integrations are skipped during tests so that test results remain repeatable.

## AWS deployment and cloud services

The project includes optional integration hooks; they become active only after AWS resources and permissions are configured in your AWS account.

### Compute

Run the Flask application behind Gunicorn on an AWS compute service such as EC2 or Elastic Beanstalk. `Procfile` and `Dockerfile` are included as deployment starting points. Use HTTPS through a load balancer or managed ingress, and set `DEBUG` off in production.

### Database

Use Amazon RDS for PostgreSQL. Set `DATABASE_URL` to a private RDS endpoint using a SQLAlchemy PostgreSQL URL. Restrict the database security group to the application security group. Back up the database before schema or data changes.

### S3 storage

When `S3_BUCKET_NAME` is set, successful external-source response snapshots are archived as JSON under `floodguard/source-snapshots/`. The application uses the AWS SDK credential chain; on AWS, prefer an instance/task role rather than static access keys. Use a private bucket, least-privilege `s3:PutObject` permissions, encryption, and lifecycle rules.

### CloudWatch monitoring

Set `CLOUDWATCH_LOG_GROUP` to an existing log group to enable the optional CloudWatch log handler. The app expects the runtime IAM role to have the required CloudWatch Logs write permissions. Create the log group and alarms in AWS before enabling this setting. Logs remain local when the variable is blank.

### Security and availability checklist

- Generate a strong `SECRET_KEY` and unique staff credentials.
- Keep `.env` out of version control and never put AWS credentials in the source.
- Use IAM roles and least privilege.
- Configure RDS backups, S3 lifecycle, CloudWatch alarms, HTTPS and security groups.
- Add database migrations before future model changes; `db.create_all()` does not migrate existing tables.
- Verify live feed availability and data licences in the deployment region.

This source package does **not** provision AWS resources or mean the app has already been deployed. Deployment, IAM, database provisioning and monitoring configuration must be completed in your AWS account.
