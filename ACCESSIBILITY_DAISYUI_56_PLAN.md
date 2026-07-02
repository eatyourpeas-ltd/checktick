# DaisyUI 5.6 and WCAG 2.2 Implementation Plan

Temporary working plan for upgrading DaisyUI, local accessibility testing, and WCAG 2.2 alignment. Remove this file once the work is complete.

## Goals

- Upgrade DaisyUI from `5.4.7` to the latest available `5.6.x` release, pinned to `5.6`, without regressions.
- Move accessibility validation and public-facing language from WCAG 2.1 AA to WCAG 2.2 AA where appropriate.
- Enable developers to run the same accessibility tests locally that currently only run in CI.
- Ensure default DaisyUI theme usage and custom-theme validation remain safe for a medical survey platform.

## Constraints and Repository Rules

- Keep changes minimal and scoped.
- Use repository scripts in `s/` where possible.
- Do not log patient data, request bodies, decrypted survey objects, credentials, or ORM models.
- Default validation for feature work remains `s/test --no-a11y`; accessibility validation should use the new dedicated local container/workflow exposed as `s/test --a11y-only`.
- CDN/self-hosted JavaScript assets must be updated through the manifest workflow:
  - `checktick_app/cdn_assets.json` is the source of truth.
  - Use `s/update-cdn-assets` for `axe-core` updates; `axe-core` should track the latest version through the CDN asset workflow.
  - Update generated CDN docs through the existing sync/update scripts.

## TDD-Oriented Work Plan

### 1. Establish Baseline

- Inspect current DaisyUI/Tailwind package versions in `package.json` and `package-lock.json`.
- Inspect current accessibility test setup in `tests/test_accessibility.py`, CI workflows, and test scripts under `s/`.
- Inspect current Docker Compose/dev container setup to identify the best place for a dev-only accessibility container.
- Run the existing non-a11y suite first:
  - `s/test --no-a11y`
- Run existing lint baseline if needed before larger edits:
  - `s/lint`

### 2. Add Local Accessibility Test Container First

- Add a dev-only service/image capable of running browser-based accessibility tests with Chromium.
- Prefer a dedicated Compose override or service that does not affect production images.
- The image can be lighter than CI, but should match CI behavior as closely as practical for UI accessibility testing.
- Add or update a script under `s/` so developers can run accessibility tests consistently, for example:
  - `s/test --a11y-only`
  - or an explicit documented command using the new service.
- Confirm the command can run `tests/test_accessibility.py` locally in the new container.
- Commit this as an isolated infrastructure/testing change.

### 3. Update Accessibility Tests Toward WCAG 2.2

- Update `tests/test_accessibility.py` to assert WCAG 2.2 AA where supported by the installed `axe-core` version and test tooling.
- Check whether current tests explicitly reference WCAG 2.1 tags/rules and update to include WCAG 2.2 tags.
- Preserve existing coverage for core pages, forms, theme previews, and custom theme validation.
- Run accessibility tests in the new local container and fix failures caused by the tests or application markup.
- Commit test changes separately where possible.

### 4. Update `axe-core`

- Use the repository CDN asset workflow to update `axe-core` rather than editing static files or SRI hashes manually:
  - `s/update-cdn-assets --yes --key axe_core`
- Verify updates to:
  - `checktick_app/cdn_assets.json`
  - self-hosted static asset under `checktick_app/static/`
  - `docs/cdn-libraries.md`
  - relevant lock/package metadata if applicable
- If the update is security-driven, add a row to `docs/compliance/vulnerability-patch-log.md`; otherwise document as standards support.
- Run the custom-theme accessibility UI tests after updating.
- Commit the asset update separately.

### 5. Upgrade DaisyUI to 5.6.x

- Update `daisyui` in `package.json` to the latest available `5.6.x` release and refresh `package-lock.json` with npm.
- Rebuild generated CSS/theme output using the project’s existing CSS build workflow.
- Inspect and update `checktick_app/static/css/daisyui_themes.css` if generated or pinned theme output changes.
- Run targeted UI/static tests and then the default suite:
  - `s/test --no-a11y`
- Run local accessibility tests in the new container.
- Commit dependency and generated asset changes together.

### 6. Update DaisyUI Theme Configuration for WCAG 2.2

- Locate Tailwind/DaisyUI configuration and current theme definitions.
- Ensure theme usage follows DaisyUI semantic token pairs, for example:
  - `bg-primary` with `text-primary-content`
  - `bg-secondary` with `text-secondary-content`
  - `bg-accent` with `text-accent-content`
  - `bg-neutral` with `text-neutral-content`
  - `bg-base-*` with appropriate `text-base-content`
- Avoid hardcoded color combinations where semantic DaisyUI pairs are available.
- Fix any discovered mismatches in templates/components with minimal changes.
- Add or adjust tests to prevent regressions where practical.
- Run accessibility tests locally in the new container.
- Commit theme/template adjustments separately.

### 7. Update Public-Facing UI References

- Locate public home page templates and any user-facing text that references WCAG 2.1 AA.
- Update wording to WCAG 2.2 AA where accurate, using “Designed to support and tested against” for public compliance claims.
- Keep claims precise: distinguish platform defaults from user custom-theme validation.
- Run targeted template/UI tests and local accessibility tests.
- Commit copy changes separately.

### 8. Update Documentation

- Update at least:
  - `docs/accessibility.md`
  - `docs/themes.md`
  - relevant test docs if local accessibility workflow is documented elsewhere
  - CDN docs if generated by the updater
- Document the new local accessibility test workflow and its Docker/Chromium requirement.
- Document WCAG 2.2 expectations for custom themes and DaisyUI semantic color classes.
- Include troubleshooting notes for the local accessibility container.
- Commit documentation changes separately.

### 9. Final Validation

Run, in order:

1. `s/test --no-a11y`
2. `s/test --a11y-only` using the new local accessibility test container/workflow
3. `s/lint`

If time permits, compare with CI accessibility workflow configuration to confirm local and CI commands are aligned.

## Suggested Commit Boundaries

1. Add local accessibility test container/script.
2. Update accessibility tests for WCAG 2.2.
3. Update `axe-core` via CDN asset workflow.
4. Upgrade DaisyUI to 5.6.x and regenerate assets.
5. Update theme/template semantic color usage.
6. Update public WCAG references.
7. Update documentation.

## Resolved Implementation Decisions

- DaisyUI should be upgraded to the latest available `5.6.x` release and pinned to the `5.6` line.
- `axe-core` should always track the latest available version through the CDN asset workflow.
- The local accessibility container may be lighter than CI, but should match CI behavior as closely as practical for UI accessibility testing.
- Public-facing claims should use the phrasing “Designed to support and tested against” WCAG 2.2 AA to avoid overclaiming.
