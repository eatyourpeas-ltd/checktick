---
title: Django Administration
category: self-hosting
priority: 8
---

The Django administration interface provides superuser-level access to data and settings that are not available through the Platform Admin (`/platform-admin/`). This document describes what is available there, how access works, and which functions are exclusive to it.

## Access

The Django admin is available at `/admin/`.

> **Important:** The Django admin login form is disabled. Visiting `/admin/` without an active superuser session returns a **404 Not Found** — the interface does not reveal its existence to unauthenticated or non-superuser users.

To access the admin you must:

1. Log in to CheckTick through the normal application login (`/accounts/login/`)
2. Your account must have `is_superuser = True` and `is_active = True`
3. Navigate to `/admin/` — you will be granted access directly

To create your first superuser:

```bash
docker compose exec web python manage.py createsuperuser
```

---

## Platform Admin vs Django Admin

CheckTick has two administration interfaces:

| Interface | URL | Access | Purpose |
|---|---|---|---|
| **Platform Admin** | `/platform-admin/` | Superusers | Day-to-day organisation and user management |
| **Django Admin** | `/admin/` | Superusers | Low-level data access, financial exports, and tasks with no Platform Admin equivalent |

The Platform Admin covers most operational tasks. The Django admin should be used only for the specific functions listed below.

---

## Functions Exclusive to Django Admin

The following features are only available through the Django admin and have no equivalent in the Platform Admin.

### VAT / Payment Records

**URL:** `/admin/core/payment/`

| Feature | Description |
|---|---|
| View all payment records | Invoice number, date, user, tier, amount, VAT, status |
| `export_to_csv` action | Export selected records to a PII-stripped CSV for HMRC VAT returns |
| `export_quarter_to_csv` action | Export a full quarter of invoices in one action |
| Amount display fields | `amount_ex_vat`, `vat_amount`, `amount_inc_vat` — all sortable |

> **For VAT compliance:** The CSV export action is the primary mechanism for producing records suitable for HMRC VAT submissions. There is no equivalent export in the Platform Admin.

---

### User Profiles and Account Tiers

**URL:** `/admin/core/userprofile/`

Allows manual adjustment of a user's account tier, subscription status, payment provider, and the date the tier was last changed. This is the only interface for these fields.

| Field | Purpose |
|---|---|
| `account_tier` | Upgrade or downgrade a user's plan manually |
| `subscription_status` | Override subscription state (e.g. active, past_due, cancelled) |
| `payment_provider` | Record which payment provider manages the subscription |
| `tier_changed_at` | Audit timestamp for tier changes |

---

### User Email and Language Preferences

**URLs:** `/admin/core/useremailpreferences/` and `/admin/core/userlanguagepreference/`

Allows inspection and manual editing of per-user notification settings and language preferences. There is no equivalent view in the Platform Admin or user-facing settings.

---

### Site Branding

**URL:** `/admin/core/sitebranding/`

The singleton branding record can only be created or edited here (or via the `/branding/` UI and the `configure_branding` management command). The Django admin enforces the singleton pattern — it prevents adding a second record and disallows deletion.

See [Theme Configuration](self-hosting-themes.md) for the recommended approach using the branding UI.

---

### Data Export Audit Trail

**URL:** `/admin/surveys/dataexport/`

Lists all data export records: which survey was exported, who created the export, the response count, whether it was encrypted, and the download status. This is the only UI for inspecting export records.

| Permission | Behaviour |
|---|---|
| View / filter | All superusers |
| Add / change | Disabled — exports are created through the survey interface only |
| Delete | Superusers only — use with care |

---

### Dataset Publishing and NHS Data Dictionary Enforcement

**URL:** `/admin/surveys/dataset/`

| Feature | Description |
|---|---|
| `publish_datasets` action | Mark selected datasets as published and set `published_at` |
| `create_custom_version_action` | Generate a customisable copy of a global dataset for an organisation |
| NHS DD read-only guard | Datasets sourced from the NHS Data Dictionary become fully read-only — all fields are locked to prevent accidental modification of upstream data |

Dataset browsing for end users is available through the surveys interface; the publishing workflow and NHS DD guard are Django admin only.

---

### Raw Survey and Question Editing

**URLs:** `/admin/surveys/survey/` and inline question editing

Provides a direct editing interface for surveys and their questions, bypassing the normal survey builder. Intended as a superuser support and debugging fallback — for example, to fix a malformed question or unlock a survey stuck in an unexpected state.

---

### Survey Progress and Response Inspection

**URLs:** `/admin/surveys/surveyprogress/` and `/admin/surveys/surveyresponse/`

Read-only debugging views showing incomplete survey sessions (progress records with expiry timestamps) and submitted responses. Useful for diagnosing user-reported issues. There are no equivalent views in the Platform Admin or any user-facing interface.

---

### Collection Definitions

**URL:** `/admin/surveys/collectiondefinition/`

Allows inspection and editing of collection structures (repeating groups) and their items. This is a low-level debugging tool with no front-end management equivalent.

---

## Functions with Platform Admin Equivalents

The following Django admin sections exist but are fully or largely covered by the Platform Admin at `/platform-admin/`. Prefer the Platform Admin for day-to-day use.

| Django Admin | Platform Admin Equivalent |
|---|---|
| Organisation CRUD | `/platform-admin/organizations/` |
| Generate checkout / invite links | `/platform-admin/organizations/<id>/invite/` |
| Send invite emails | `/platform-admin/organizations/<id>/send-invite/` |
| Toggle organisation active/inactive | `/platform-admin/organizations/<id>/toggle-active/` |
| Recovery request management | `/surveys/recovery/` (Platform Recovery Console) |
| Identity verification approve/reject | Handled through the Platform Recovery Console |
| Organisation statistics | `/platform-admin/stats/` |
| AuditLog viewing | `/platform-admin/logs/` — the AuditLog is **not** in the Django admin; the platform logs view is the only UI for it |

---

## Full Django Admin Feature Reference

The table below covers every registered ModelAdmin for reference.

| Model | Admin URL | Key Features | Django Admin Only? |
|---|---|---|---|
| `SiteBranding` | `/admin/core/sitebranding/` | Singleton branding record; singleton and delete guards | Partially — also editable at `/branding/` |
| `UserEmailPreferences` | `/admin/core/useremailpreferences/` | Per-user notification flags | ✅ Yes |
| `UserLanguagePreference` | `/admin/core/userlanguagepreference/` | Per-user language setting | ✅ Yes |
| `UserProfile` | `/admin/core/userprofile/` | Account tier, subscription, payment provider | ✅ Yes |
| `Payment` | `/admin/core/payment/` | Invoice records; VAT CSV export actions | ✅ Yes |
| `DataSet` | `/admin/surveys/dataset/` | Publish action; NHS DD read-only guard | ✅ Yes (publishing) |
| `Organization` | `/admin/surveys/organization/` | Full CRUD + member inline | Platform Admin preferred |
| `QuestionGroup` | `/admin/surveys/questiongroup/` | Basic listing | ✅ Yes |
| `Survey` | `/admin/surveys/survey/` | Raw survey + question inline editing | ✅ Yes |
| `SurveyResponse` | `/admin/surveys/surveyresponse/` | Response inspection | ✅ Yes |
| `SurveyProgress` | `/admin/surveys/surveyprogress/` | Session/progress inspection | ✅ Yes |
| `CollectionDefinition` | `/admin/surveys/collectiondefinition/` | Collection structure + items inline | ✅ Yes |
| `PublishedQuestionGroup` | `/admin/surveys/publishedquestiongroup/` | Template status/field editing | Partially |
| `RecoveryRequest` | `/admin/surveys/recoveryrequest/` | Bulk approve/reject/execute actions | Platform Admin preferred |
| `IdentityVerification` | `/admin/surveys/identityverification/` | Bulk verify/reject actions | Platform Admin preferred |
| `RecoveryAuditEntry` | `/admin/surveys/recoveryauditentry/` | Immutable audit log — read-only, no add/delete | Inline in recovery admin |
| `DataExport` | `/admin/surveys/dataexport/` | Export audit trail; superuser-only delete | ✅ Yes |

---

## Security Notes

- The Django admin login form is disabled. A 404 is returned to any user who is not already authenticated as a superuser — the admin URL is not publicly advertised and does not prompt for credentials.
- Access is restricted to accounts with both `is_active = True` and `is_superuser = True`. Staff-only accounts (`is_staff = True`) are not granted access.
- All actions in the Django admin are performed under the authenticated superuser's session and are subject to the same audit logging as other application actions.
- Superuser accounts should use strong, unique passwords and, where possible, should have two-factor authentication enabled.
