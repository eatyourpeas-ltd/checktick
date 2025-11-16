# Self-Hosting: Scheduled Tasks

CheckTick requires scheduled tasks for data governance operations, housekeeping, and external data syncing. This guide explains how to set up these tasks on different hosting platforms.

## Overview

CheckTick uses four scheduled tasks:

### 1. Data Governance (Required for GDPR)

The `process_data_governance` management command runs daily to:

1. **Send deletion warnings** - Email notifications 30 days, 7 days, and 1 day before automatic deletion
2. **Soft-delete expired surveys** - Automatically soft-delete surveys that have reached their retention period
3. **Hard-delete surveys** - Permanently delete surveys 30 days after soft deletion

**Legal Requirement**: This task is required for GDPR compliance. Failure to run it may result in data being retained longer than legally allowed.

### 2. Survey Progress Cleanup (Recommended)

The `cleanup_survey_progress` management command runs daily to:

1. **Delete expired progress records** - Removes incomplete survey progress older than 30 days
2. **Free up database storage** - Keeps the database lean by removing stale session data

**Recommended**: While not legally required, this prevents database bloat and improves performance. Progress records are only needed while users are actively completing surveys.

### 3. External Dataset Sync (Recommended)

The `sync_external_datasets` management command runs daily to:

1. **Update hospital lists** - Syncs hospitals, NHS trusts, and other organizational data from RCPCH API
2. **Maintain accuracy** - Ensures dropdown options reflect current NHS organizational structure
3. **Enable offline use** - Stores data locally so surveys work without API dependency

**Recommended**: Run this daily to keep external datasets fresh. Datasets are used in prefilled dropdown fields. Without periodic sync, data may become stale (hospitals close, trusts merge, etc.).

**Initial Setup**: Just run the sync command once to populate datasets (creates records automatically):

```bash
# One-time: Create datasets and populate data (takes 2-3 minutes)
python manage.py sync_external_datasets
```

### 4. NHS Data Dictionary Sync (Recommended)

The `sync_nhs_dd_datasets` management command runs weekly to:

1. **Scrape standardized lists** - Fetches codes and values from NHS Data Dictionary website
2. **Update existing datasets** - Keeps NHS DD datasets current with official sources
3. **Maintain accuracy** - Ensures dropdown options match authoritative NHS standards

**Recommended**: Run this weekly to keep NHS DD datasets fresh. See [NHS Data Dictionary Datasets](nhs-data-dictionary-datasets.md) for the full list of scraped datasets.

**Initial Setup**: Just run the sync command once to populate datasets (creates records automatically):

```bash
# One-time: Create datasets and scrape data (takes 1-2 minutes)
python manage.py sync_nhs_dd_datasets
```

**Maintenance**:

```bash
# Check which datasets would be synced
python manage.py sync_nhs_dd_datasets --dry-run

# Force re-scrape all datasets (even if recently scraped)
python manage.py sync_nhs_dd_datasets --force

# Sync a single dataset
python manage.py sync_nhs_dd_datasets --dataset smoking_status_code
```

## Prerequisites

- CheckTick deployed and running
- Email configured (for sending deletion warnings)
- Access to your hosting platform's scheduling features

---

## Platform-Specific Setup

### Northflank (Recommended)

Northflank provides native cron job support, making this the simplest option.

#### 1. Create Data Governance Cron Job

1. Go to your Northflank project
2. Click **"Add Service"** → **"Cron Job"**
3. Configure the job:
   - **Name**: `checktick-data-governance`
   - **Docker Image**: Use the same image as your web service (e.g., `ghcr.io/eatyourpeas/checktick:latest`)
   - **Schedule**: `0 2 * * *` (runs at 2 AM UTC daily)
   - **Command**: `python manage.py process_data_governance`

#### 2. Create Survey Progress Cleanup Cron Job

1. Click **"Add Service"** → **"Cron Job"** again
2. Configure the job:
   - **Name**: `checktick-progress-cleanup`
   - **Docker Image**: Use the same image as your web service
   - **Schedule**: `0 3 * * *` (runs at 3 AM UTC daily, after data governance)
   - **Command**: `python manage.py cleanup_survey_progress`

#### 3. Create External Dataset Sync Cron Job

1. Click **"Add Service"** → **"Cron Job"** again
2. Configure the job:
   - **Name**: `checktick-dataset-sync`
   - **Docker Image**: Use the same image as your web service
   - **Schedule**: `0 4 * * *` (runs at 4 AM UTC daily)
   - **Command**: `python manage.py sync_external_datasets`

#### 4. Create NHS DD Sync Cron Job

1. Click **"Add Service"** → **"Cron Job"** again
2. Configure the job:
   - **Name**: `checktick-nhs-dd-sync`
   - **Docker Image**: Use the same image as your web service
   - **Schedule**: `0 5 * * 0` (runs at 5 AM UTC every Sunday - weekly)
   - **Command**: `python manage.py sync_nhs_dd_datasets`

#### 5. Copy Environment Variables

All cron jobs need the same environment variables as your web service:

1. In Northflank, go to your web service → **Environment**
2. Copy all environment variables
3. Go to each cron job service → **Environment**
4. Paste the variables

**Critical variables needed:**

- `DATABASE_URL`
- `SECRET_KEY`
- `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD` (for data governance)
- `DEFAULT_FROM_EMAIL` (for data governance)
- `SITE_URL` (for email links in data governance)
- `EXTERNAL_DATASET_API_URL`, `EXTERNAL_DATASET_API_KEY` (for dataset sync - optional, defaults to RCPCH API)

#### 5. Deploy and Test

1. Deploy all cron job services
2. Test them manually via Northflank dashboard: **Jobs** → **Run Now**
3. Check logs to verify successful execution
4. Monitor the **History** tab for scheduled runs

**Important**: For external dataset sync, run the initial setup command once:

```bash
# In your web service terminal (via Northflank shell or kubectl exec)
python manage.py sync_external_datasets
```

**Northflank Advantages:**

- ✅ No extra containers running 24/7
- ✅ Easy manual testing via UI
- ✅ Built-in logging and monitoring
- ✅ No additional cost (same compute as web service, but only active for ~1-5 minutes daily)

---

### Docker Compose (Local/VPS)

If you're self-hosting with Docker Compose on a VPS or dedicated server, use the system's cron.

#### 1. Create Cron Scripts

Create `/usr/local/bin/checktick-data-governance.sh`:

```bash
#!/bin/bash
# CheckTick Data Governance Cron Job
# Runs daily at 2 AM UTC

# Set working directory
cd /path/to/your/checktick-app

# Run the management command
docker compose exec -T web python manage.py process_data_governance >> /var/log/checktick/data-governance.log 2>&1

# Exit with the command's exit code
exit $?
```

Create `/usr/local/bin/checktick-progress-cleanup.sh`:

```bash
#!/bin/bash
# CheckTick Survey Progress Cleanup Cron Job
# Runs daily at 3 AM UTC

# Set working directory
cd /path/to/your/checktick-app

# Run the cleanup command
docker compose exec -T web python manage.py cleanup_survey_progress >> /var/log/checktick/progress-cleanup.log 2>&1

# Exit with the command's exit code
exit $?
```

Create `/usr/local/bin/checktick-dataset-sync.sh`:

```bash
#!/bin/bash
# CheckTick External Dataset Sync Cron Job
# Runs daily at 4 AM UTC

# Set working directory
cd /path/to/your/checktick-app

# Run the sync command
docker compose exec -T web python manage.py sync_external_datasets >> /var/log/checktick/dataset-sync.log 2>&1

# Exit with the command's exit code
exit $?
```

Make them executable:

```bash
chmod +x /usr/local/bin/checktick-data-governance.sh
chmod +x /usr/local/bin/checktick-progress-cleanup.sh
chmod +x /usr/local/bin/checktick-dataset-sync.sh
```

#### 2. Add to System Crontab

```bash
sudo crontab -e
```

Add these lines:

```cron
# CheckTick Data Governance - Daily at 2 AM UTC
0 2 * * * /usr/local/bin/checktick-data-governance.sh

# CheckTick Survey Progress Cleanup - Daily at 3 AM UTC
0 3 * * * /usr/local/bin/checktick-progress-cleanup.sh

# CheckTick External Dataset Sync - Daily at 4 AM UTC
0 4 * * * /usr/local/bin/checktick-dataset-sync.sh
```

#### 3. Create Log Directory

```bash
sudo mkdir -p /var/log/checktick
sudo chown $USER:$USER /var/log/checktick
```

#### 4. Test the Scripts

```bash
# Test data governance
/usr/local/bin/checktick-data-governance.sh
tail -f /var/log/checktick/data-governance.log

# Test progress cleanup
/usr/local/bin/checktick-progress-cleanup.sh
tail -f /var/log/checktick/progress-cleanup.log

# Test dataset sync
/usr/local/bin/checktick-dataset-sync.sh
tail -f /var/log/checktick/dataset-sync.log
```

**Important**: For external dataset sync, run the initial setup once:

```bash
cd /path/to/your/checktick-app
docker compose exec web python manage.py sync_external_datasets
```

---

### Kubernetes

If you're running CheckTick in Kubernetes, use a CronJob resource.

#### Create a CronJob manifest:

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: checktick-data-governance
  namespace: checktick
spec:
  schedule: "0 2 * * *"  # 2 AM UTC daily
  concurrencyPolicy: Forbid  # Don't run if previous job still running
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: data-governance
            image: ghcr.io/eatyourpeas/checktick:latest
            command:
            - python
            - manage.py
            - process_data_governance
            envFrom:
            - configMapRef:
                name: checktick-config
            - secretRef:
                name: checktick-secrets
            resources:
              requests:
                memory: "256Mi"
                cpu: "100m"
              limits:
                memory: "512Mi"
                cpu: "500m"
```

Apply the manifest:

```bash
kubectl apply -f checktick-cronjob.yaml
```

Test manually:

```bash
# Trigger a manual run
kubectl create job --from=cronjob/checktick-data-governance manual-test-1

# Check logs
kubectl logs -l job-name=manual-test-1
```

---

### AWS ECS/Fargate

Use AWS EventBridge (CloudWatch Events) to trigger scheduled ECS tasks.

#### 1. Create EventBridge Rule

```bash
aws events put-rule \
  --name checktick-data-governance-daily \
  --schedule-expression "cron(0 2 * * ? *)" \
  --description "Run CheckTick data governance tasks daily at 2 AM UTC"
```

#### 2. Add ECS Task as Target

```bash
aws events put-targets \
  --rule checktick-data-governance-daily \
  --targets "Id"="1","Arn"="arn:aws:ecs:region:account:cluster/checktick-cluster","RoleArn"="arn:aws:iam::account:role/ecsEventsRole","EcsParameters"="{TaskDefinitionArn=arn:aws:ecs:region:account:task-definition/checktick-web:latest,LaunchType=FARGATE,NetworkConfiguration={awsvpcConfiguration={Subnets=[subnet-xxx],SecurityGroups=[sg-xxx],AssignPublicIp=ENABLED}},TaskCount=1,PlatformVersion=LATEST}"
```

#### 3. Override Task Command

In your task definition, set the command override:

```json
{
  "overrides": {
    "containerOverrides": [
      {
        "name": "checktick-web",
        "command": ["python", "manage.py", "process_data_governance"]
      }
    ]
  }
}
```

---

### Heroku

Heroku provides the **Scheduler** add-on for running periodic tasks.

#### 1. Add Scheduler Add-on

```bash
heroku addons:create scheduler:standard
```

#### 2. Configure Job

```bash
heroku addons:open scheduler
```

In the web interface:
- **Command**: `python manage.py process_data_governance`
- **Frequency**: Daily at 2:00 AM (UTC)

---

### Railway

Railway doesn't have native cron support, so use an external service or run a background worker.

#### Option 1: Use GitHub Actions (Recommended)

Create `.github/workflows/data-governance-cron.yml`:

```yaml
name: Data Governance Cron

on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
  workflow_dispatch:  # Allow manual trigger

jobs:
  run-data-governance:
    runs-on: ubuntu-latest
    steps:
      - name: Trigger Railway Command
        run: |
          curl -X POST \
            -H "Authorization: Bearer ${{ secrets.RAILWAY_API_TOKEN }}" \
            -H "Content-Type: application/json" \
            -d '{"command": "python manage.py process_data_governance"}' \
            https://backboard.railway.app/graphql/v2
```

#### Option 2: Use EasyCron or Similar Service

1. Sign up for [EasyCron](https://www.easycron.com/) or similar
2. Create a webhook endpoint in your CheckTick app
3. Schedule the webhook to run daily

---

## Command Reference

### Data Governance Command

```bash
# Run data governance tasks
python manage.py process_data_governance

# Dry-run mode (show what would be done without making changes)
python manage.py process_data_governance --dry-run

# Verbose output (detailed logging)
python manage.py process_data_governance --verbose
```

**Example Output:**

```text
Starting data governance processing at 2024-10-26 02:00:00

--- Deletion Warnings ---
Sent 3 deletion warnings:
  - 30-day warnings: 2
  - 7-day warnings: 1
  - 1-day warnings: 0

--- Automatic Deletions ---
Soft deleted: 1 surveys
Hard deleted: 0 surveys

⚠️  1 surveys were deleted. Check audit logs for details.

Data governance processing completed at 2024-10-26 02:00:15
```

### Survey Progress Cleanup Command

```bash
# Clean up expired survey progress records
python manage.py cleanup_survey_progress

# Dry-run mode (show what would be deleted without making changes)
python manage.py cleanup_survey_progress --dry-run

# Verbose output (detailed logging)
python manage.py cleanup_survey_progress --verbose
```

**Example Output:**

```text
Starting survey progress cleanup...
Found 15 expired progress records (older than 30 days)
Deleted 15 expired survey progress records
Cleanup completed successfully
```

**What gets deleted:**

- Anonymous user progress (session-based) older than 30 days
- Authenticated user progress older than 30 days
- Token-based progress older than 30 days
- Only incomplete surveys (completed submissions are already deleted on submission)

---

## Testing

### Test in Development

**Data Governance:**

```bash
# Test with dry-run (safe, no changes)
docker compose exec web python manage.py process_data_governance --dry-run --verbose

# Test for real (only if you have test data)
docker compose exec web python manage.py process_data_governance --verbose
```

**Survey Progress Cleanup:**

```bash
# Test with dry-run (safe, no changes)
docker compose exec web python manage.py cleanup_survey_progress --dry-run --verbose

# Test for real (only if you have test data)
docker compose exec web python manage.py cleanup_survey_progress --verbose
```

### Test in Production

1. **First, use dry-run mode:**

   ```bash
   # Data governance
   python manage.py process_data_governance --dry-run --verbose

   # Progress cleanup
   python manage.py cleanup_survey_progress --dry-run --verbose
   ```

2. **Review the output** - it will show what surveys/progress records would be affected

3. **Run for real** (on your scheduled platform)

4. **Monitor logs** after the first scheduled run

---

## Monitoring

### Check Execution Logs

**Northflank:**

- Go to your cron job service → **History** → View logs

**Docker Compose:**

```bash
# Data governance logs
tail -f /var/log/checktick/data-governance.log

# Progress cleanup logs
tail -f /var/log/checktick/progress-cleanup.log
```

**Kubernetes:**

```bash
# Data governance
kubectl logs -l job-name=checktick-data-governance --tail=100

# Progress cleanup
kubectl logs -l job-name=checktick-progress-cleanup --tail=100
```

### Audit Trail

**Survey Deletions:**

All deletions are logged in the database. Check via Django admin:

```python
# In Django shell
python manage.py shell

from checktick_app.surveys.models import Survey
from django.utils import timezone
from datetime import timedelta

# Check recently soft-deleted surveys
Survey.objects.filter(
    deleted_at__gte=timezone.now() - timedelta(days=7)
).values('name', 'deleted_at', 'deletion_date')

# Check surveys due for deletion soon
Survey.objects.filter(
    deletion_date__lte=timezone.now() + timedelta(days=7),
    deleted_at__isnull=True
).values('name', 'deletion_date', 'retention_months')
```

**Progress Cleanup:**

Monitor the SurveyProgress table size:

```python
# In Django shell
from checktick_app.surveys.models import SurveyProgress
from django.utils import timezone
from datetime import timedelta

# Count total progress records
print(f"Total progress records: {SurveyProgress.objects.count()}")

# Count expired records (ready for cleanup)
expired = SurveyProgress.objects.filter(
    expires_at__lt=timezone.now()
)
print(f"Expired records: {expired.count()}")

# Count by type
authenticated = SurveyProgress.objects.filter(user__isnull=False).count()
anonymous = SurveyProgress.objects.filter(session_key__isnull=False).count()
token_based = SurveyProgress.objects.filter(access_token__isnull=False).count()
print(f"Authenticated: {authenticated}, Anonymous: {anonymous}, Token-based: {token_based}")
```

---

## Troubleshooting

### No Emails Being Sent

**Check email configuration:**
```bash
# Test email from Django shell
python manage.py shell
>>> from django.core.mail import send_mail
>>> send_mail('Test', 'Testing', 'from@example.com', ['to@example.com'])
```

**Common issues:**
- Missing `EMAIL_HOST` or `EMAIL_PORT` environment variables
- Incorrect SMTP credentials
- Missing `SITE_URL` (emails include survey links)

### Surveys Not Being Deleted

**Check for legal holds:**
```python
from checktick_app.surveys.models import Survey, LegalHold

# Find surveys with active legal holds
Survey.objects.filter(legal_hold__removed_at__isnull=True)
```

Surveys with active legal holds are **intentionally skipped** from automatic deletion.

### Command Fails Silently

**Run with verbose output:**
```bash
python manage.py process_data_governance --verbose
```

**Check Python errors:**
- Database connection issues
- Missing environment variables
- Permissions problems

---

## Security Considerations

### Environment Variables

The cron job needs access to:
- **Database credentials** (via `DATABASE_URL`)
- **Email credentials** (for sending notifications)
- **Django SECRET_KEY** (for encryption/signing)

**Never log sensitive environment variables!**

### Execution Isolation

- Cron jobs should run in the same network as your database
- Use read-only database credentials if possible for reporting
- Consider separate logging for scheduled tasks

---

## FAQ

**Q: What happens if the cron job fails?**

A: The next day's run will process any missed deletions. Surveys won't be deleted prematurely - only those past their `deletion_date`.

**Q: Can I change the schedule?**

A: Yes, but **daily at 2 AM UTC is recommended** for:
- Off-peak hours (less load)
- Predictable timing for users
- Allows overnight processing before business hours

**Q: What timezone does the schedule use?**

A: All schedules use **UTC**. Django's `deletion_date` is also stored in UTC, so the system is timezone-aware.

**Q: How long does the command take to run?**

A: Typically **30-60 seconds** for most deployments. Scales with:
- Number of surveys approaching deletion
- Email sending speed
- Database query performance

**Q: Can I disable automatic deletion?**

A: No - automatic deletion is **required for GDPR compliance**. However, you can:

- Apply legal holds to prevent specific surveys from being deleted
- Extend retention periods (up to 24 months)
- Export data before deletion

**Q: Why do I need the progress cleanup job?**

A: The cleanup job prevents database bloat by removing old progress records. Without it:

- Your database will grow indefinitely with incomplete survey sessions
- Performance may degrade over time
- Storage costs will increase

The cleanup is safe because it only removes progress for incomplete surveys older than 30 days.

**Q: What if someone was working on a survey and their progress gets deleted?**

A: Progress records expire after 30 days of inactivity. This is intentional:

- Most surveys are completed within hours or days, not months
- After 30 days, the session is likely abandoned
- Users can still start a new submission if needed
- Only the progress draft is deleted, not any completed submissions

**Q: Do both cron jobs need to run?**

A:

- **Data governance**: YES - legally required for GDPR compliance
- **Progress cleanup**: RECOMMENDED - prevents database bloat, but not legally required

---

## Next Steps

- [Survey Progress Tracking](./survey-progress-tracking.md) - Learn about the progress feature
- [Data Governance Overview](./data-governance-overview.md) - Understand the retention policy
- [Data Governance Retention](./data-governance-retention.md) - Learn about retention periods
- [Self-Hosting Backup](./self-hosting-backup.md) - Set up automated backups
- [Email Notifications](./email-notifications.md) - Configure email delivery
