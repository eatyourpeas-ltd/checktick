---
title: Getting Started
category: getting-started
priority: 1
---

Welcome to CheckTick! This guide will help you get started with creating surveys, understanding account types, and using the API.

## Table of Contents

- [What is CheckTick?](#what-is-checktick)
- [Account Types](#account-types) - Individual vs Organisation
- [Quick Start](#quick-start) - Create your first survey
- [Using the API](#using-the-api) - Programmatic access
- [Next Steps](#next-steps)

---

## What is CheckTick?

CheckTick is a secure, privacy-focused survey platform designed for:

- Healthcare research
- Clinical audits
- Patient feedback
- Quality improvement projects
- Educational assessments

### Key Features

- **Secure**: Optional encryption, audit trails, GDPR-compliant
- **Flexible**: Custom questions, conditional logic, multi-language
- **Data governance**: Automatic retention policies, access controls
- **API access**: Programmatic survey creation and data export
- **Self-hosted**: Run on your own infrastructure (optional)

---

## Account Types

CheckTick offers two account types, each suited to different use cases.

### Individual Accounts

**What is it?**
A personal account for solo users.

**Best for**:
- Individual researchers
- Solo practitioners
- Personal projects
- Students
- Small-scale surveys

**Features**:
- Create unlimited surveys
- Collect unlimited responses (subject to server limits)
- Optional encryption (personal passphrase)
- Full API access
- Export data (CSV, JSON, Excel)

**Limitations**:
- No team collaboration (can't assign other users)
- Single owner per survey
- No organisation-level encryption
- No shared survey groups

**Pricing**: Free (for self-hosted) or see hosted pricing

---

### Organisation Accounts

**What is it?**
A team account for groups, organisations, or institutions.

**Best for**:
- Healthcare organisations
- Research teams
- Educational institutions
- Clinical departments
- Multi-user projects

**Features**:
- Everything in Individual accounts, plus:
- **Team collaboration**: Multiple users with different roles
- **Organisation-level encryption**: Centralized data protection
- **Shared survey groups**: Organize surveys by project/department
- **User management**: Assign owners, editors, viewers, data custodians
- **Centralized audit logs**: Track all team activity
- **Group ownership**: Surveys can be owned by organisation

**User roles in organisations**:

| Role | Create Surveys | View Data | Download Data | Manage Users |
|------|---------------|-----------|---------------|--------------|
| **Organisation Owner** | ✅ | ✅ | ✅ | ✅ |
| **Survey Owner** | ✅ | ✅ (own surveys) | ✅ (own surveys) | ✅ (own surveys) |
| **Editor** | ✅ (if permitted) | ❌ | ❌ | ❌ |
| **Viewer** | ❌ | ❌ | ❌ | ❌ |
| **Data Custodian** | ❌ | ❌ | ✅ (assigned surveys) | ❌ |

**Pricing**: Contact for organisation pricing

---

### Choosing Between Individual and Organisation

| Factor | Individual | Organisation |
|--------|-----------|-------------|
| **Team size** | Just you | 2+ people |
| **Data sharing** | Manual export/sharing | Built-in collaboration |
| **Access control** | Single owner | Role-based permissions |
| **Encryption** | Personal passphrase | Organisation-wide passphrase |
| **Audit requirements** | Basic logs | Comprehensive audit trails |
| **Cost** | Free (self-hosted) | Organisation pricing |

**Can I upgrade later?**
Yes, you can convert an individual account to an organisation account. Your existing surveys will be migrated.

---

## Quick Start

### Step 1: Create an Account

1. Go to your CheckTick instance (e.g., `https://checktick.example.com`)
2. Click "Sign Up"
3. Choose account type:
   - **Individual**: Just fill in your details
   - **Organisation**: Provide organisation name and details
4. Verify your email
5. Log in

### Step 2: Create Your First Survey

1. Click "Create Survey" button
2. Enter survey details:
   - **Name**: E.g., "Patient Satisfaction Survey"
   - **Description**: Brief overview of purpose
   - **Survey Type**: Choose template or start from scratch

3. Add questions:
   - Click "Add Question"
   - Choose question type:
     - Text (short answer)
     - Text Area (long answer)
     - Multiple Choice
     - Checkboxes
     - Dropdown
     - Number
     - Date
     - Scale (1-5, 1-10, etc.)
     - File Upload
   - Set question options:
     - Required vs. optional
     - Help text
     - Conditional logic (show if...)

4. Organize questions:
   - Drag and drop to reorder
   - Group related questions into sections
   - Add page breaks for multi-page surveys

5. Configure settings:
   - **Access**: Public, private, or link-only
   - **Timing**: Start and end dates
   - **Responses**: Allow multiple submissions or one per user
   - **Thank you message**: Custom completion message

6. Preview your survey:
   - Click "Preview" to test
   - Submit test responses
   - Verify logic and flow

7. Publish:
   - Click "Publish Survey"
   - Copy the survey link
   - Share with participants

### Step 3: Collect Responses

**Sharing your survey**:

- **Public link**: Share URL directly
- **Email invitation**: Send personalized invitations
- **QR code**: Generate QR code for print materials
- **Embed**: Embed in website or portal

**Monitoring progress**:

- View response count on dashboard
- Check completion rate
- Monitor daily submissions
- Set up email notifications for new responses

### Step 4: View and Analyze Data

1. Go to survey dashboard
2. Click "View Responses"
3. See response summary:
   - Total responses
   - Completion rate
   - Average time to complete
   - Response timeline chart

4. Individual responses:
   - Browse responses one by one
   - Filter and search
   - Delete individual responses (if needed)

5. Aggregate data:
   - View charts and graphs
   - See response distribution
   - Calculate averages and totals

### Step 5: Export Data

1. Close survey (required before export):
   - Click "Close Survey"
   - Confirm closure (responses locked)

2. Click "Export Data"
3. Choose format:
   - **CSV**: For Excel, R, Python, SPSS
   - **JSON**: For programmatic processing
   - **Excel**: Formatted workbook with multiple sheets

4. Enter purpose (data governance requirement):
   - E.g., "Annual report analysis"

5. If encryption enabled:
   - Enter passphrase to decrypt

6. Download file
7. Store securely (see Data Governance guide)

---

## Using the API

CheckTick provides a comprehensive REST API for programmatic access.

### Why Use the API?

- **Automation**: Create surveys programmatically
- **Integration**: Connect to other systems
- **Batch operations**: Create multiple surveys at once
- **Custom workflows**: Build custom data collection tools
- **Data export**: Automate data downloads
- **Analysis pipelines**: Feed data directly to analysis tools

### API Authentication

CheckTick uses **API tokens** for authentication.

#### Creating an API Token

1. Log in to CheckTick
2. Go to Account Settings → API
3. Click "Create API Token"
4. Name your token (e.g., "Python script", "R analysis")
5. Copy token (shown only once!)
6. Store securely (password manager, environment variable)

**Example token**: `ct_1234567890abcdef1234567890abcdef`

**Security notes**:
- Never commit tokens to git
- Don't share tokens
- Rotate tokens periodically
- Revoke tokens when no longer needed

#### Using Your Token

Include token in `Authorization` header:

```bash
curl -H "Authorization: Token ct_your_token_here" \
     https://checktick.example.com/api/v1/surveys/
```

Or in Python:

```python
import requests

headers = {
    'Authorization': 'Token ct_your_token_here'
}

response = requests.get(
    'https://checktick.example.com/api/v1/surveys/',
    headers=headers
)
```

### API Endpoints

#### List Surveys

```bash
GET /api/v1/surveys/
```

**Response**:
```json
{
  "count": 5,
  "next": null,
  "previous": null,
  "results": [
    {
      "id": "uuid-1234",
      "name": "Patient Satisfaction Survey",
      "slug": "patient-satisfaction-survey",
      "status": "published",
      "created_at": "2025-01-15T10:00:00Z",
      "response_count": 23
    }
  ]
}
```

#### Get Survey Details

```bash
GET /api/v1/surveys/{survey_slug}/
```

**Response**:
```json
{
  "id": "uuid-1234",
  "name": "Patient Satisfaction Survey",
  "description": "Collecting patient feedback",
  "status": "published",
  "created_at": "2025-01-15T10:00:00Z",
  "questions": [
    {
      "id": "q1",
      "text": "How satisfied are you?",
      "type": "scale",
      "required": true,
      "options": {
        "min": 1,
        "max": 5
      }
    }
  ]
}
```

#### Create Survey

```bash
POST /api/v1/surveys/
Content-Type: application/json

{
  "name": "New Survey",
  "description": "Survey description",
  "questions": [
    {
      "text": "What is your name?",
      "type": "text",
      "required": true
    },
    {
      "text": "How satisfied are you?",
      "type": "scale",
      "required": true,
      "options": {
        "min": 1,
        "max": 5,
        "labels": {
          "1": "Very dissatisfied",
          "5": "Very satisfied"
        }
      }
    }
  ]
}
```

**Response**: Created survey object

#### Submit Response

```bash
POST /api/v1/surveys/{survey_slug}/responses/
Content-Type: application/json

{
  "data": {
    "q1_name": "John Smith",
    "q2_satisfaction": 5
  }
}
```

**Response**: Created response object

#### Export Data

```bash
GET /api/v1/surveys/{survey_slug}/export/?format=csv
```

**Parameters**:
- `format`: `csv`, `json`, or `xlsx`
- `purpose`: Required - reason for export

**Response**: File download (CSV, JSON, or Excel)

**Note**: Survey must be closed before export.

### API Examples

#### Python: Create and Publish Survey

```python
import requests

API_BASE = 'https://checktick.example.com/api/v1'
TOKEN = 'ct_your_token_here'

headers = {
    'Authorization': f'Token {TOKEN}',
    'Content-Type': 'application/json'
}

# Create survey
survey_data = {
    'name': 'Diabetes Patient Feedback',
    'description': 'Collecting feedback from diabetes clinic',
    'questions': [
        {
            'text': 'What is your age?',
            'type': 'number',
            'required': True
        },
        {
            'text': 'How long have you had diabetes?',
            'type': 'text',
            'required': True
        },
        {
            'text': 'Rate your clinic experience (1-5)',
            'type': 'scale',
            'required': True,
            'options': {
                'min': 1,
                'max': 5
            }
        }
    ]
}

response = requests.post(
    f'{API_BASE}/surveys/',
    json=survey_data,
    headers=headers
)

survey = response.json()
print(f"Survey created: {survey['slug']}")

# Publish survey
requests.post(
    f'{API_BASE}/surveys/{survey["slug"]}/publish/',
    headers=headers
)

print(f"Survey URL: https://checktick.example.com/s/{survey['slug']}")
```

#### Python: Export Survey Data

```python
import requests
import pandas as pd
from io import StringIO

API_BASE = 'https://checktick.example.com/api/v1'
TOKEN = 'ct_your_token_here'

headers = {
    'Authorization': f'Token {TOKEN}'
}

# Close survey first
survey_slug = 'patient-satisfaction-survey'

requests.post(
    f'{API_BASE}/surveys/{survey_slug}/close/',
    headers=headers
)

# Export data
params = {
    'format': 'csv',
    'purpose': 'Data analysis for quality improvement report'
}

response = requests.get(
    f'{API_BASE}/surveys/{survey_slug}/export/',
    params=params,
    headers=headers
)

# Load into pandas
df = pd.read_csv(StringIO(response.text))
print(df.head())
print(f"Total responses: {len(df)}")
```

#### R: Fetch and Analyze Data

```r
library(httr)
library(jsonlite)
library(dplyr)

API_BASE <- 'https://checktick.example.com/api/v1'
TOKEN <- 'ct_your_token_here'

# Export data
response <- GET(
  paste0(API_BASE, '/surveys/patient-satisfaction-survey/export/'),
  query = list(
    format = 'json',
    purpose = 'Statistical analysis'
  ),
  add_headers(Authorization = paste('Token', TOKEN))
)

data <- content(response, as = 'parsed')

# Convert to dataframe
df <- data$responses %>%
  lapply(function(r) as.data.frame(r$data)) %>%
  bind_rows()

# Analyze
summary(df)
mean(df$satisfaction_rating)
```

#### Bash: Automated Survey Creation

```bash
#!/bin/bash

API_BASE="https://checktick.example.com/api/v1"
TOKEN="ct_your_token_here"

# Create survey
curl -X POST "$API_BASE/surveys/" \
  -H "Authorization: Token $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Weekly Audit Survey",
    "questions": [
      {
        "text": "Number of patients seen",
        "type": "number",
        "required": true
      },
      {
        "text": "Any incidents?",
        "type": "boolean",
        "required": true
      }
    ]
  }' | jq '.'
```

### API Rate Limits

To prevent abuse, the API has rate limits:

- **Individual accounts**: 100 requests/hour
- **Organisation accounts**: 1,000 requests/hour

Rate limit headers in response:
```
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1642589400
```

If rate limit exceeded:
```json
{
  "error": "Rate limit exceeded",
  "retry_after": 3600
}
```

### API Versioning

CheckTick uses URL versioning:
- Current version: `/api/v1/`
- Future versions will use `/api/v2/`, etc.

Old API versions are supported for at least 12 months after new version release.

### API Documentation

Full API documentation available at:
- **Interactive docs**: `https://checktick.example.com/api/docs/`
- **OpenAPI spec**: `https://checktick.example.com/api/schema/`
- **PDF guide**: See [API Documentation](api.md)

---

## Next Steps

### Tutorials

- [Creating Surveys](surveys.md) - Detailed survey creation guide
- [Data Governance](data-governance.md) - Understanding data protection
- [Encryption](encryption.md) - Setting up data encryption
- [Collections](collections.md) - Organizing surveys into groups
- [API Guide](using-the-api.md) - Comprehensive API tutorial

### Advanced Features

- **Conditional Logic**: Show questions based on previous answers
- **Prefilled Data**: Import datasets for prepopulated surveys
- **Multi-language**: Create surveys in multiple languages
- **Email Notifications**: Get notified of new responses
- **Custom Themes**: Customize survey appearance
- **OIDC SSO**: Single sign-on integration
- **Webhooks**: Real-time response notifications

### Self-Hosting

Want to run CheckTick on your own infrastructure?

- [Self-Hosting Quickstart](self-hosting-quickstart.md)
- [Production Deployment](self-hosting-production.md)
- [Database Configuration](self-hosting-database.md)
- [Backup and Restore](self-hosting-backup.md)

### Getting Help

- **Documentation**: [docs.checktick.example.com](https://github.com/eatyourpeas/checktick/tree/main/docs)
- **GitHub Issues**: [Report bugs or request features](https://github.com/eatyourpeas/checktick/issues)
- **Discussions**: [Ask questions](https://github.com/eatyourpeas/checktick/discussions)
- **Email**: support@checktick.example.com (for hosted instances)

---

## Common Workflows

### Workflow 1: Simple Patient Feedback Survey

1. Create individual account
2. Create survey with 5-10 questions
3. Generate QR code
4. Print QR code on posters in clinic
5. Patients scan and complete survey
6. After 1 month, close survey
7. Export CSV data
8. Analyze in Excel/SPSS
9. Delete survey after analysis complete

**Time**: 30 minutes setup, 5 minutes export

---

### Workflow 2: Multi-Site Research Study

1. Create organisation account
2. Add team members (researchers at each site)
3. Create survey with research questions
4. Enable organisation encryption
5. Share survey link with each site
6. Sites collect responses
7. Principal investigator exports data monthly
8. Data manager analyzes centrally
9. After study completion, extend retention for 2 years

**Time**: 2 hours setup, 30 minutes monthly export

---

### Workflow 3: Automated Weekly Audit

1. Create API token
2. Write Python script to create survey weekly
3. Schedule script with cron
4. Clinicians receive email with survey link
5. Complete audit survey each week
6. Script exports data Friday night
7. Automated report generated and emailed
8. Old surveys deleted after 6 months

**Time**: 4 hours initial setup, fully automated thereafter

---

## Frequently Asked Questions

### Is CheckTick free?

- **Self-hosted**: Yes, completely free and open-source
- **Hosted**: Contact for pricing

### How many responses can I collect?

- No hard limit
- Depends on server capacity
- Typical installations handle 100,000+ responses without issues

### Is my data secure?

- Optional encryption (AES-256)
- Audit trails for all data access
- Automatic data retention policies
- GDPR and NHS compliance features
- Regular security updates

### Can I use CheckTick for clinical data?

Yes, CheckTick is designed for healthcare:
- Meets NHS Data Security and Protection Toolkit requirements
- Supports Caldicott Principles
- GDPR-compliant
- Optional encryption for sensitive data
- Research ethics committee approved (at many institutions)

**Important**: You are responsible for ensuring your specific use case complies with applicable regulations.

### Can I migrate from SurveyMonkey/Google Forms/etc.?

Yes! While there's no automatic migration tool:
1. Export your old survey questions
2. Recreate survey structure in CheckTick
3. Import historical data via API (if needed)

### Can I customize the look of surveys?

Yes:
- Custom themes (colors, fonts, logos)
- Custom CSS (for self-hosted instances)
- White-label options
- Embedding in your own website

See [Themes Guide](themes.md)

### Does CheckTick work on mobile?

Yes, fully responsive:
- Surveys work on any device
- Touch-friendly interfaces
- QR code scanning
- Mobile-optimized forms

### Can I schedule survey availability?

Yes:
- Set start and end dates
- Schedule automatic publication
- Automatic closure after end date
- Timezone support

### What languages are supported?

CheckTick supports 13 languages:
- English, Arabic, Chinese, Welsh, German, Spanish, French, Hindi, Italian, Polish, Portuguese, Urdu

See [Internationalisation Guide](i18n.md)

---

## Summary

You now know:
- ✅ The difference between Individual and Organisation accounts
- ✅ How to create your first survey
- ✅ How to collect and export data
- ✅ How to use the API for automation
- ✅ Where to find more help

**Ready to get started?**

1. Create an account
2. Build your first survey
3. Share with participants
4. Analyze your data

Welcome to CheckTick! 🎉
