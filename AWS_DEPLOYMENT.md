# AWS deployment checklist

This repository is deployment-ready source code, not an automatically provisioned AWS stack. Create and secure the AWS resources in your account before using these steps.

## Suggested architecture

- **Compute:** Amazon EC2 running the included Gunicorn `Procfile`/Docker image, or Elastic Beanstalk.
- **Database:** Amazon RDS for PostgreSQL in private subnets. Restrict inbound PostgreSQL traffic to the application security group.
- **Object storage:** Private S3 bucket for external-source JSON snapshots.
- **Monitoring:** CloudWatch Logs for application logs; create alarms for 5xx responses, CPU/memory metrics where available, and instance health.
- **Networking:** HTTPS via an Application Load Balancer or managed ingress, security groups with minimum required ports, and no public RDS access.

## Required environment variables

```dotenv
APP_ENV=production
SECRET_KEY=<long-random-secret-from-a-secret-manager>
DATABASE_URL=postgresql+psycopg://<user>:<password>@<private-rds-host>:5432/<database>
DEMO_MODE=false
AWS_REGION=ap-south-1
S3_BUCKET_NAME=<private-s3-bucket>
CLOUDWATCH_LOG_GROUP=/floodguard/sentinel
CLOUDWATCH_LOG_STREAM=application
LOG_LEVEL=INFO
INITIAL_STAFF_PASSWORD=<unique-initial-password>
```

Do not commit these values or put AWS access keys in `.env` on a server. Prefer an EC2 instance profile/task role. Grant only the permissions required for the chosen bucket prefix and existing CloudWatch log group.

## Deployment outline

1. Create an RDS PostgreSQL instance, private subnets, backups and security-group rules.
2. Create a private S3 bucket with default encryption, public access blocked and lifecycle policy for `floodguard/source-snapshots/`.
3. Create a CloudWatch log group and alarms. Grant the app role write access to that group and the specific S3 prefix.
4. Build and deploy the app with Python 3.12 or the included Dockerfile. Set the environment variables using the deployment platform's secure configuration.
5. Configure HTTPS and a health check against `/health`.
6. Verify `/health`, login permissions, data-source timestamps, logs, S3 snapshots and database backups.
7. Rotate initial staff credentials immediately. The current initial account creation is intended for first-run classroom deployment; production user provisioning and password reset workflows should be added before public exposure.

## Limitations

- This repository does not include CloudFormation/Terraform and cannot create resources without AWS account access.
- The database models currently use `db.create_all()`; use a migration system before changing schemas in a live database.
- Open-Meteo values are modelled weather context; Copernicus results are satellite product metadata. Neither integration by itself constitutes an official flood warning or validated flood prediction.
- DHM is linked as the authoritative source but is not automatically ingested by this application.
