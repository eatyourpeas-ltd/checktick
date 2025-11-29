---
title: Dependencies
category: api
priority: 20
---

# Updating Paddle.js

CheckTick self-hosts the Paddle.js SDK with Subresource Integrity (SRI) verification for enhanced security. This document describes how to update the Paddle.js file when a new version is released.

## Why Self-Host with SRI?

- **Security**: Prevents CDN compromise or third-party modifications
- **Integrity**: SRI hash ensures the file hasn't been tampered with
- **Compliance**: Better for healthcare/sensitive data applications
- **Control**: No dependency on external CDN availability

## Update Process

### 1. Check for Updates

Visit the Paddle.js release notes to see if a new version is available:
- [Paddle.js v2 Documentation](https://developer.paddle.com/paddlejs/overview)
- [Paddle Changelog](https://developer.paddle.com/changelog)

### Step 2: Download the Latest Version

```bash
# Navigate to project root
cd /path/to/checktick

# Download latest Paddle.js v2
curl -o checktick_app/static/js/paddle.js https://cdn.paddle.com/paddle/v2/paddle.js
```

### Step 3: Generate New SRI Hash

```bash
# Generate SHA-384 hash for integrity verification
openssl dgst -sha384 -binary checktick_app/static/js/paddle.js | openssl base64 -A
```

This will output a hash like:
```
aglX2UoXZDBOAz6UEdPtOtWeOeg905NPyCh27ZRhNJv7Gi+D0cAZfJsOAPyHusOr
```

### Step 4: Update base.html

Edit `checktick_app/templates/base.html` and update the integrity attribute:

```html
<script src="{% static 'js/paddle.js' %}"
        integrity="sha384-YOUR_NEW_HASH_HERE"
        crossorigin="anonymous"></script>
```

### Step 5: Test Locally

```bash
# Restart the development server
docker compose down
docker compose up -d

# Open http://localhost:8000/pricing/
# Check browser console for "Paddle initialized in sandbox mode"
# Test checkout button functionality
```

### Step 6: Verify in Production

After deploying:
1. Check browser console for successful Paddle initialization
2. Test checkout flow on pricing page
3. Verify no CSP or integrity errors in console

## Current Version Info

- **File**: `checktick_app/static/js/paddle.js`
- **Size**: 51,598 bytes (51 KB)
- **Current Hash**: `sha384-aglX2UoXZDBOAz6UEdPtOtWeOeg905NPyCh27ZRhNJv7Gi+D0cAZfJsOAPyHusOr`
- **Last Updated**: January 2025
- **Source**: https://cdn.paddle.com/paddle/v2/paddle.js

## Troubleshooting

### SRI Hash Mismatch Error

If you see a console error like:
```
Failed to find a valid digest in the 'integrity' attribute for resource...
```

This means:
1. The file was modified after generating the hash, OR
2. The hash in base.html doesn't match the file

**Solution**: Regenerate the hash (step 3) and update base.html (step 4).

### Paddle Not Loading

If Paddle.js fails to load:
1. Check that `checktick_app/static/js/paddle.js` exists
2. Run `docker compose exec web python manage.py collectstatic --noinput`
3. Verify the file is accessible at `/static/js/paddle.js` in browser
4. Check browser console for integrity or CORS errors

### Checkout Not Working

If the checkout button doesn't open Paddle overlay:

1. Open browser console and check for errors
2. Verify `data-paddle-token` is present on `<body>` tag
3. Check that `PAYMENT_CLIENT_TOKEN` is set in environment
4. Ensure you're using the correct environment (sandbox vs production)

## Automated Updates (GitHub Action)

CheckTick includes a GitHub Action that automatically checks for Paddle.js updates weekly.

### How It Works

1. **Weekly Check**: Runs every Monday at 9am UTC (configurable in `.github/workflows/update-paddle-js.yml`)
2. **Download Latest**: Fetches the latest Paddle.js from the CDN
3. **Compare Hashes**: Checks if the SRI hash has changed
4. **Create PR**: If updated, automatically creates a pull request with:
   - The new `paddle.js` file
   - The new SRI hash in the PR description
   - A testing checklist
   - Labels for dependencies, security, and payment

### Manual Trigger

You can also trigger the check manually:

1. Go to **Actions** tab in GitHub
2. Select **Check Paddle.js Updates** workflow
3. Click **Run workflow**

### After the PR is Created

1. Review the PR and test the checkout flow on a staging environment
2. If tests pass, manually update `checktick_app/templates/base.html` with the new SRI hash from the PR description
3. Commit the base.html change to the PR branch
4. Merge the PR

### Modifying the Schedule

Edit `.github/workflows/update-paddle-js.yml`:

```yaml
on:
  schedule:
    # Run weekly on Mondays at 9am UTC
    - cron: '0 9 * * 1'
```

Common schedules:

- Daily: `'0 9 * * *'`
- Weekly (Monday): `'0 9 * * 1'`
- Monthly (1st): `'0 9 1 * *'`

## Manual Update Process

If you prefer to update manually or need to update urgently:

### Step 1: Check for Updates
