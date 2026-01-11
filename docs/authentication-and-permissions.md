---
title: Authentication & Permissions
category: security
priority: 1
---

This document explains how users authenticate and what they can access in the system (SSR UI and API). It also describes the role model and how authorization is enforced in code.

## Authentication

CheckTick supports multiple authentication methods for healthcare environments:

### Traditional Authentication

- Web UI uses Django session authentication with CSRF protection.
- API uses JWT (Bearer) authentication via SimpleJWT. Obtain a token pair using username/password, then include the access token in the `Authorization: Bearer <token>` header.
- Anonymous users can access public participant survey pages (SSR) when a survey is live. They cannot access the builder or any API objects.
- Usernames are equal to email addresses. Use your email as the username when logging in or obtaining tokens.

### Healthcare SSO (Single Sign-On)

CheckTick integrates with OIDC providers for seamless clinician authentication:

#### Supported Providers

- **Google OAuth**: For clinicians with personal Google accounts
- **Microsoft Azure AD**: For hospital staff with organizational Microsoft 365 accounts
- **Multi-provider support**: Same user can authenticate via multiple methods

#### Key Features

- **Email-based linking**: OIDC accounts automatically link to existing users via email address
- **Preserved encryption**: SSO users maintain the same encryption security as traditional users
- **Dual authentication**: Users can switch between SSO and password authentication
- **Organization flexibility**: Supports both personal and organizational accounts
- **External user support**: Handles Azure AD guest accounts and external clinicians

#### User Experience

Clinicians can choose their preferred authentication method:

1. **SSO Login**: Click "Sign in with Google" or "Sign in with Microsoft"
2. **Traditional Login**: Use email and password
3. **Account Linking**: Same email automatically links OIDC and traditional accounts
4. **Encryption Integration**: All users get the same encryption protection regardless of authentication method

#### Enterprise Setup

For detailed setup instructions including cloud console configuration, environment variables, and troubleshooting, see:

**📋 [OIDC SSO Setup Guide](oidc-sso-setup.md)**

This comprehensive guide covers:

- Step-by-step Azure AD and Google Cloud setup
- Production environment configuration
- Security considerations and best practices
- Troubleshooting common issues

## Identity and roles

There are six key models in `checktick_app.surveys.models`:

- Organization: a container for users and surveys.
- OrganizationMembership: links a user to an organization with a role.
  - Roles: ADMIN, CREATOR, VIEWER
- Team: a collaboration unit for small groups, optionally hosted within an organization.
- TeamMembership: links a user to a team with a role.
  - Roles: ADMIN, CREATOR, VIEWER
- Survey: owned by a user and optionally associated with an organization or team.
- SurveyMembership: links a user to a specific survey with a role.
  - Roles: CREATOR, EDITOR, VIEWER

### Account Tiers

CheckTick uses a seven-tier account system:

- **FREE tier**: Individual users with up to 3 active surveys. Cannot share surveys or invite collaborators.
- **PRO tier**: Individual users with unlimited surveys. Can add editors (up to 10 collaborators per survey) but no viewer role.
- **TEAM tiers** (Small/Medium/Large): Small group collaboration (5/10/20 members) with team-based surveys and role-based access.
- **ORGANIZATION tier**: Large team collaboration with unlimited collaborators and full role-based access (Admin, Creator, Viewer).
- **ENTERPRISE tier**: All ORGANIZATION features plus custom branding, SSO/OIDC, and self-hosted options.

For detailed tier features, see [Account Types & Tiers](getting-started-account-types.md).

### Organization Roles

Organization-level role semantics:

- **Owner**: The user who created the organization. Full administrative access.
- **Org ADMIN**: Can view/edit all surveys that belong to their organization. Can manage organization members, teams, and survey collaborators.
- **Org CREATOR**: Can create surveys within the organization. Can view/edit their own surveys.
- **Org VIEWER**: Read-only access to organization surveys. Cannot create or edit surveys.
- **Participant** (no membership): Can only submit responses via public links; cannot access builder or API survey objects.

### Team Roles

Team-level role semantics (for Team tier accounts):

- **Team Owner**: The user who created the team. Equivalent to Team ADMIN with ownership rights.
- **Team ADMIN**: Can manage team members (add/remove, change roles). Can view/edit all team surveys. Can manage team settings.
- **Team CREATOR**: Can create surveys within the team. Can view/edit their own surveys and collaborate on team surveys.
- **Team VIEWER**: Read-only access to team surveys. Cannot create or edit surveys.

Teams can exist:

- **Standalone**: Independent teams (not part of an organization)
- **Organization-hosted**: Teams within an organization (managed by org admins)

**Access Hierarchy**: Organization admin > Team admin > Team creator > Team viewer

### Survey Collaboration Roles

**Note**: Survey collaboration is available for organization and team surveys. Individual users on PRO tier can add editors only (no viewer role).

Individual surveys within organizations can have collaborators with specific roles through SurveyMembership:

| Role | Content Editing | User Management | Survey Creation |
|------|----------------|-----------------|-----------------|
| **CREATOR** | Yes | Yes | Yes |
| **EDITOR** | Yes | No | No |
| **VIEWER** | No | No | No |

- **CREATOR**: Full access to survey content and collaborator management. Can edit questions, groups, and manage other users' access to the survey.
- **EDITOR**: Can modify survey content (questions, groups, settings) but cannot manage collaborators or create new surveys.
- **VIEWER**: Read-only access to surveys for monitoring and preview purposes.

Single-organisation admin model:

- A user can be an ADMIN of at most one organisation. The user management hub (`/surveys/manage/users/`) focuses on that single organisation context for each admin user.

### Survey Collaboration Features

Collaboration features are tier-dependent:

**FREE Tier:**

- Cannot share surveys or invite collaborators
- Survey management is solo only

**PRO Tier:**

- Can add editors to surveys (up to 10 collaborators per survey)
- No viewer role available
- Limited collaboration model

**TEAM Tiers (Small/Medium/Large):**

- Team-based collaboration with role management
- Team admins can manage members and assign roles (ADMIN, CREATOR, VIEWER)
- Survey creators within teams can share surveys with team members
- Limited to team size (5/10/20 members depending on tier)
- Dashboard integration: Team management interface for admins

**ORGANIZATION & ENTERPRISE Tiers:**

- Full collaboration features available
- Survey CREATORs can add users by email and assign roles (CREATOR, EDITOR, VIEWER)
- Unlimited collaborators per survey
- Role management: CREATORs can change collaborator roles or remove access
- Dashboard integration: "Manage collaborators" button shows for organization surveys
- Permission boundaries: EDITORs can modify content but cannot manage users

This enables teams to collaborate on survey design while maintaining clear boundaries between content editing and access control.

## Enforcement in server-side views (SSR)

The central authorization checks live in `checktick_app/surveys/permissions.py`:

### Survey Permissions

- `can_view_survey(user, survey)` — True if user is the survey owner, an ADMIN of the survey's organization, a member of the survey's team, or has survey membership (CREATOR, EDITOR, or VIEWER)
- `can_edit_survey(user, survey)` — True if user is the survey owner, an ADMIN of the survey's organization, a team member with ADMIN or CREATOR role, or has survey membership as CREATOR or EDITOR
- `can_manage_survey_users(user, survey)` — True if the survey belongs to an organization or team AND user is the survey owner, an ADMIN of the survey's organization, a team ADMIN, or has survey membership as CREATOR. Returns False for individual user surveys (surveys without organization or team).
- `require_can_view(user, survey)` — Raises 403 if not allowed
- `require_can_edit(user, survey)` — Raises 403 if not allowed

### Team Permissions

- `can_view_team_survey(user, survey)` — True if user can view a team survey (team membership or organization admin)
- `can_edit_team_survey(user, survey)` — True if user can edit a team survey (team admin/creator or organization admin)
- `can_manage_team(user, team)` — True if user is team owner, team admin, or organization admin (for org-hosted teams)
- `can_add_team_member(user, team)` — True if user can manage team AND team is under capacity
- `can_create_survey_in_team(user, team)` — True if user is team member with CREATOR or ADMIN role AND team is under survey limit
- `get_user_team_role(user, team)` — Returns the user's role in the team (ADMIN, CREATOR, VIEWER, or None)

### Team Decorators

For view protection, use these decorators from `checktick_app/surveys/decorators.py`:

- `@team_member_required(role=None)` — Requires team membership, optionally with specific role (ADMIN, CREATOR, VIEWER)
- `@team_admin_required` — Requires team ADMIN role
- `@team_creator_required` — Requires team CREATOR or ADMIN role

All builder/dashboard/preview endpoints call these helpers before proceeding. Unauthorized requests receive HTTP 403.

## Enforcement in the API (DRF)

The API mirrors the same rules using a DRF permission class and scoped querysets:

- **Listing**: returns only the surveys the user can see (their own, any in orgs where they are ADMIN, any in teams they belong to, plus surveys they are members of via SurveyMembership). Anonymous users see an empty list.
- **Retrieve**: allowed only if `can_view_survey` is true.
- **Create**: authenticated users can create surveys. The creator becomes the owner.
- **Update/Delete/Custom actions**: allowed only if `can_edit_survey` is true (CREATOR and EDITOR roles for survey members, or team ADMIN/CREATOR).

User management operations (adding/removing collaborators) require `can_manage_survey_users` permission, which is restricted to:

- Organization or team surveys only (surveys with organization or team)
- Survey CREATORs, organization ADMINs, team ADMINs, and survey owners
- **Individual users (surveys without organization or team) will receive 403 Forbidden when attempting to manage memberships**

Error behavior:

- 401 Unauthorized: missing/invalid/expired JWT
- 403 Forbidden: logged in but insufficient permissions on the object (including individual users attempting to share surveys)

## Dataset Permissions

Datasets (prefilled dropdown options) have different permission models depending on their type:

### Dataset Types and Ownership

- **NHS Data Dictionary (NHS DD)**: Global, read-only datasets managed by the platform. Cannot be edited or deleted.
- **External API datasets**: Global datasets synced from external sources. Read-only for all users.
- **User-created datasets**: Created by individual users or organization members, can be personal or organization-owned, and optionally published globally.

### Individual User Dataset Permissions

Individual users (without organization membership) can:

- **Create datasets**: Create personal datasets
- **Edit own datasets**: Modify datasets they created
- **Delete own datasets**: Remove their datasets (unless published with dependents)
- **Publish globally**: Share their datasets with all users
- **Create custom versions**: Customize any global dataset

> **Note**: Dataset creation and publishing is available to all tiers. Future versions may require PRO tier for advanced dataset features.

### Organization Dataset Roles

For organization-owned datasets:

| Role | View | Create | Edit | Delete | Publish Globally | Create Custom Version |
|------|------|--------|------|--------|------------------|----------------------|
| **ADMIN** | Yes | Yes | Yes | Yes* | Yes | Yes |
| **CREATOR** | Yes | Yes | Yes | Yes* | Yes | Yes |
| **VIEWER** | Yes | No | No | No | No | No |

*Cannot delete if published globally and other organizations have created custom versions from it

### Global Dataset Operations

Any authenticated user can:

- View all global datasets (NHS DD, external API, and published user datasets)
- Create custom versions from any global dataset

### Publishing Datasets

Individual users, ADMINs and CREATORs can publish their datasets globally:

1. **Publish action**: Makes a dataset available to all users
2. **Attribution preserved**: Creator/organization ownership is retained after publishing
3. **Protection**: Published datasets with dependents (custom versions from others) cannot be deleted
4. **Editability**: Original creator/organization can still edit published datasets

### Custom Versions

Authenticated users can create custom versions from any global dataset:

- **Source flexibility**: Can customize NHS DD datasets, external API datasets, or other users' published datasets
- **Independence**: Custom versions are independent - changes don't affect the parent
- **Personal or org-owned**: Custom versions belong to the creating user (individual) or their organization
- **Full control**: Custom versions can be edited, deleted, and even published globally

### Enforcement in the API

Dataset API (`/api/datasets-v2/`) enforces these rules:

- **Listing**: Returns global datasets plus user's organization datasets (if in an org) plus user's personal datasets
- **Retrieve**: Allowed if user can view the dataset
- **Create**: Allowed for all authenticated users (will require pro account in future)
- **Update/Delete**: Requires being the creator (individual) or ADMIN/CREATOR in dataset's organization
- **Publish**: Requires being the creator (individual) or ADMIN/CREATOR in dataset's organization
- **Create custom version**: Allowed for all authenticated users (will require pro account in future)

For detailed usage and examples, see [Dataset Sharing and Customization](dataset-sharing-and-customization.md).

Additional protections:

- Object-level permissions are enforced for detail endpoints (retrieve/update/delete) and custom actions like `seed`. Authenticated users will receive 403 (Forbidden) if they don't have rights on an existing object, rather than 404.
- Querysets are scoped to reduce exposure: list endpoints only return what you're allowed to see (owned + org-admin).
- Throttling is enabled (AnonRateThrottle, UserRateThrottle). See `REST_FRAMEWORK.DEFAULT_THROTTLE_RATES` in `settings.py`.
- CORS is disabled by default (`CORS_ALLOWED_ORIGINS = []`). Enable explicit origins before using the API cross-site.

### Account Deletion Restrictions

For security and data integrity, account deletion is strictly controlled:

- **User accounts**: Only superusers can delete user accounts via Django Admin (`/admin/auth/user/`)
- **Organizations**: Only superusers can delete organizations via Django Admin (`/admin/surveys/organization/`)
- **Regular users cannot delete their own accounts** to prevent data loss and maintain security

This protects against:

- Accidental deletion of surveys shared with other users
- Malicious or compromised account actions
- Loss of audit trails and organizational data
- Cascade deletion effects that impact multiple users

Survey creators and organization admins retain full control over survey access and membership management, but cannot perform destructive account-level operations.

### Platform Admin Functions

Platform superusers have access to additional administrative interfaces for compliance and monitoring:

| Interface | URL | Purpose |
|-----------|-----|---------|
| Django Admin | `/admin/` | User/organization management |
| Platform Admin | `/platform-admin/` | Platform analytics and oversight |
| **Platform Logs** | `/platform-admin/logs/` | Audit and infrastructure log review |

The **Platform Logs** dashboard is essential for DPST compliance, enabling:

- Quarterly log reviews with the Data Protection Officer (DPO)
- Security incident investigation and forensics
- Correlation of application events with infrastructure logs
- Monitoring of authentication patterns and admin actions

All Platform Admin access is logged in the audit trail. See [Audit Logging and Notifications](audit-logging-and-notifications.md) for dashboard details.

### Using the API with curl (JWT)

1. Obtain a token pair (access and refresh):

```sh
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"username": "<USER>", "password": "<PASS>"}' \
  https://localhost:8000/api/token
```

1. Call the API with the access token:

```sh
ACCESS=<paste_access_token>
curl -s -H "Authorization: Bearer $ACCESS" https://localhost:8000/api/surveys/
```

1. Refresh the access token when it expires:

```sh
curl -s -X POST -H "Content-Type: application/json" \
  -d '{"refresh": "<REFRESH_TOKEN>"}' \
  https://localhost:8000/api/token/refresh
```

## Participants and sensitive data

- Public participant pages are SSR and respect survey live windows. Submissions are accepted without an account.
- Sensitive demographics are encrypted per-survey using an AES-GCM key derived for that survey. The key is shown once upon survey creation. Viewing decrypted demographics requires the survey key (handled server-side and not exposed via API).

## Error Pages and User Experience

CheckTick provides styled error pages for common authentication and permission failures, ensuring users receive helpful feedback when access is denied or issues occur:

### Custom Error Templates

- **403 Forbidden**: Displayed when authenticated users lack permission to access a resource. Shows clear messaging about access restrictions and provides navigation options back to safe areas.
- **404 Not Found**: Friendly page-not-found experience with suggestions to return to the dashboard or home page.
- **405 Method Not Allowed**: Technical error page for HTTP method mismatches.
- **500 Internal Server Error**: Reassuring message when server errors occur, encouraging users to try again or contact support.
- **Account Lockout**: Displayed after 5 failed login attempts (via django-axes). Informs users of the 1-hour cooldown period and offers password reset options.

All error templates extend the base template and use DaisyUI components, maintaining consistent branding and styling throughout the application. They include helpful actions like "Back to Dashboard", "Go to Home Page", and "Reset Password" to guide users toward resolution.

### Testing Error Pages in Development

When `DEBUG=True`, developers can preview all error pages at `/debug/errors/` to verify styling and user experience. These debug routes are automatically disabled in production (when `DEBUG=False`).

### Brute Force Protection

The django-axes integration tracks failed login attempts and locks accounts after 5 failures. The lockout period is 1 hour, after which users can attempt to log in again. The custom lockout template (`403_lockout.html`) provides clear guidance during this period.

## Security Summary

CheckTick implements defence-in-depth security across multiple layers:

### Authentication Security

| Feature | Implementation | Details |
|---------|----------------|---------|
| **Session Security** | Django sessions | CSRF protection, Secure/HttpOnly cookies in production |
| **JWT Authentication** | SimpleJWT | 30-minute access tokens, 7-day refresh tokens |
| **SSO/OIDC** | Google OAuth, Azure AD | Email-based linking, supports external/guest accounts |
| **Brute Force Protection** | django-axes | Account lockout after 5 failed attempts (1-hour cooldown) |
| **Password Policy** | Django validators | Strong password requirements enforced |

### Encryption & Data Protection

| Feature | Implementation | Details |
|---------|----------------|---------|
| **Field-Level Encryption** | AES-256-GCM | Per-survey keys for sensitive demographics |
| **Whole-Response Encryption** | AES-256-GCM with Vault | Encrypted storage for complete survey responses |
| **Key Management** | HashiCorp Vault | Self-hosted in the UK for data sovereignty |
| **Key Recovery** | Multi-party approval | Dual-admin approval with time delays |
| **SSO User Passphrases** | Required for encryption | SSO users must set passphrase for decryption access |

#### UK Data Sovereignty

CheckTick self-hosts its own HashiCorp Vault instance within the UK to ensure all encryption keys and sensitive data remain under UK jurisdiction. This approach:

- **Keeps data local**: All encryption keys stored on UK infrastructure
- **No third-party cloud dependency**: Keys never leave CheckTick-controlled systems
- **GDPR compliant**: Full control over data residency and processing
- **NHS-ready**: Meets NHS data handling requirements

For detailed encryption documentation, see:

- [Encryption for Users](encryption-for-users.md) - How encryption works for each subscription tier
- [Encryption Technical Reference](encryption-technical-reference.md) - Developer implementation guide
- [Vault Integration](vault.md) - Key management and Vault deployment

### Rate Limiting

| Scope | Limit | Purpose |
|-------|-------|---------|
| **Anonymous API** | 60/minute | Protect public endpoints |
| **Authenticated API** | 120/minute | Standard user operations |
| **Recovery Create** | 3/hour | Prevent recovery request spam |
| **Recovery Approval** | 10/hour | Limit admin approval actions |
| **Recovery View** | 60/minute | Standard recovery status checks |

### Role-Based Access Control (RBAC)

**Organization Roles**: Owner, Admin, Creator, Viewer
**Team Roles**: Owner, Admin, Creator, Viewer
**Survey Roles**: Creator, Editor, Viewer

See [Account Types & Tiers](getting-started-account-types.md) for tier-specific permissions.

### Permission Functions

Core permission checks in `checktick_app/surveys/permissions.py`:

| Function | Purpose |
|----------|---------|
| `can_view_survey` | View access to surveys |
| `can_edit_survey` | Edit access to surveys |
| `can_manage_survey_users` | Manage survey collaborators |
| `can_manage_org_users` | Manage organization members |
| `can_create_datasets` | Create new datasets |
| `can_edit_dataset` | Edit existing datasets |
| `can_close_survey` | Close/archive surveys |
| `can_export_survey_data` | Export survey responses |
| `can_extend_retention` | Extend data retention periods |
| `can_manage_legal_hold` | Manage legal hold status |
| `can_manage_data_custodians` | Manage data custodian assignments |
| `can_soft_delete_survey` | Soft delete surveys |
| `can_hard_delete_survey` | Permanent survey deletion |
| `can_publish_question_group` | Publish question templates |
| `can_import_published_template` | Import published templates |
| `can_delete_published_template` | Delete published templates |
| `can_view_team_survey` | View team surveys |
| `can_edit_team_survey` | Edit team surveys |
| `can_manage_team` | Manage team settings/members |
| `can_add_team_member` | Add members to teams |
| `can_create_survey_in_team` | Create surveys within teams |

### Additional Security Measures

- **Content Security Policy (CSP)**: django-csp for XSS protection
- **Static Asset Security**: WhiteNoise with secure headers
- **CORS**: Disabled by default, explicit origin allowlist required
- **Account Deletion**: Superuser-only to prevent data loss
- **Audit Logging**: Recovery operations logged with tamper-proof hash chain

## Developer guidance

- Use the helpers in `surveys/permissions.py` from any new views.
- When adding API endpoints, prefer DRF permission classes that delegate to these helpers and always scope querysets by the current user.
- Return 403 (not 404) for authorization failures to avoid leaking resource existence to authenticated users; for anonymous API users, DRF may return 401 for unsafe methods.

## Standards Compliance Mapping

| Requirement | Implementation |
| :--- | :--- |
| **Identity Federation** | OIDC integration for Microsoft Entra ID and Google Workspace. |
| **MFA Support** | Supported via federated providers and mandatory TOTP for local admin accounts. |
| **Password Strength** | Enforced via Django Auth Validators (Min 12 chars, blocklists). |
| **Brute Force Protection** | `django-axes` account lockout (5 attempts / 1-hour cooldown). |
| **Session Security** | Secure, HttpOnly, and SameSite cookies enforced; HSTS active. |
