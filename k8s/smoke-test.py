"""
Live staging smoke test — runbook Phase 1 round-trip (throwaway data).

Run inside a running checktick-web pod (kubectl exec); uses the pod's env
(DATABASE_URL, Vault AppRole, SNOMED_DB_PATH) against the real staging
Postgres, Vault, and pod-local snomed.db. Mirrors the runbook smoke gate:

  login (real view + real 2FA) -> create encrypted survey (real view)
  -> add text + SNOMED dropdown questions (real builder view)
  -> publish -> anonymous submission (real take view)
  -> owner unlock with password (real view) -> export CSV decrypt
  -> Vault KV escrow write/read/delete (real VaultClient)
  -> AuditLog written -> cleanup (user delete cascades survey/responses)

Questions are created through the real builder view; publish is an ORM write
(the publish-settings form is not on the migration risk surface).
Prints only step names/ids/counts — never credentials or response content.
"""

import os
import secrets

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "checktick_app.settings")
django.setup()

# Imports after django.setup() are load-bearing: models/settings require it.
from django.contrib.auth import get_user_model  # noqa: E402
from django.test import Client  # noqa: E402
from django.urls import reverse  # noqa: E402
from django_otp.plugins.otp_totp.models import TOTPDevice  # noqa: E402

from checktick_app.surveys.models import AuditLog, Survey, SurveyResponse  # noqa: E402
from checktick_app.surveys.snomed_resolver import (  # noqa: E402
    get_options,
    options_as_dict,
)
from checktick_app.surveys.utils import is_submission_blob  # noqa: E402
from checktick_app.surveys.vault_client import get_vault_client  # noqa: E402

results = []


def check(step, name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    results.append((status, f"{step} {name}"))
    print(f"[{status}] {step} — {name}" + (f" ({detail})" if detail else ""))
    return bool(cond)


suffix = secrets.token_hex(4)
email = f"smoke-{suffix}@smoke.invalid"
account_pw = f"Acct-{secrets.token_hex(8)}!"
survey_pw = f"Surv-{secrets.token_hex(8)}!"
recovery_words = ["abandon"] * 11 + ["about"]
recovery_phrase = " ".join(recovery_words)
marker = f"SMOKE-{secrets.token_hex(6)}"

User = get_user_model()
user = None
survey = None
vault_path = None

try:
    # ---- 0. Throwaway account (password user + confirmed email + TOTP) ----
    user = User.objects.create_user(username=email, email=email, password=account_pw)
    profile = getattr(user, "profile", None)
    if profile is None:
        from checktick_app.core.models import UserProfile

        profile = UserProfile.objects.create(user=user)
    profile.email_confirmed = True
    profile.save(update_fields=["email_confirmed"])
    device = TOTPDevice.objects.create(user=user, name="smoke", confirmed=True)
    check(0, "throwaway user created", user.pk is not None, f"id={user.id}")

    # ---- 1. Login via the REAL view: password -> 2FA verify -> session ----
    # SERVER_NAME must be in ALLOWED_HOSTS (the test client defaults to
    # "testserver", which the live deployment rejects).
    c = Client(SERVER_NAME="staging.checktick.uk")
    r = c.post(reverse("login"), {"username": email, "password": account_pw})
    at_verify = (
        r.status_code == 302 and reverse("core:two_factor_verify") in r["Location"]
    )
    check(1, "login view redirects to 2FA verify", at_verify)
    # Generate the current TOTP code from the device's stored key
    # (django-otp ships the oath module; the device model has bin_key).
    from django_otp.oath import TOTP

    totp = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift)
    token = str(totp.token()).zfill(device.digits)
    r = c.post(reverse("core:two_factor_verify"), {"token": token})
    check(2, "2FA token verification logs in", r.status_code == 302)
    r = c.get(reverse("core:home"))
    check(
        3,
        "home renders for confirmed-email 2FA user",
        r.status_code == 200 and r.request["PATH_INFO"].endswith("/home"),
    )

    # ---- 2. Create encrypted survey via the REAL view ----
    r = c.post(
        reverse("surveys:create"),
        {
            "name": f"Smoke Survey {suffix}",
            "encryption_option": "option2",
            "password": survey_pw,
            "recovery_phrase": recovery_phrase,
        },
    )
    check(
        4,
        "survey create redirects to dashboard",
        r.status_code == 302 and "dashboard" in r["Location"],
    )
    survey = Survey.objects.get(owner=user)
    check(
        5,
        "survey has X25519 keypair + dual-path wraps",
        survey.has_submission_keypair()
        and survey.has_dual_encryption()
        and bool(survey.submission_public_key),
        f"slug={survey.slug}",
    )

    # ---- 3. Questions via the REAL builder view ----
    gid = survey.question_groups.first().id
    r = c.post(
        reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
        {
            "text": "Smoke free-text question",
            "type": "text",
            "required": "on",
            "group_id": str(gid),
        },
    )
    check(6, "builder creates text question", r.status_code == 200)
    r = c.post(
        reverse("surveys:builder_question_create", kwargs={"slug": survey.slug}),
        {
            "text": "Smoke SNOMED dropdown",
            "type": "dropdown",
            "group_id": str(gid),
            "prefilled_dataset": "snomed_qof_epilepsy_drugs",
        },
    )
    check(7, "builder binds SNOMED dataset", r.status_code == 200)
    text_q = survey.questions.filter(type="text").first()
    dd_q = survey.questions.filter(type="dropdown").first()
    check(
        8,
        "questions exist + dropdown linked to dataset",
        text_q is not None
        and dd_q is not None
        and dd_q.dataset is not None
        and dd_q.dataset.category == "snomed",
    )

    # ---- 4. SNOMED resolver against the POD-LOCAL copy (mode=ro path) ----
    opts = options_as_dict(get_options(dd_q.dataset))
    sctid = next(iter(opts))
    term = opts[sctid]
    check(
        9,
        "snomed_resolver reads pod-local snomed.db",
        len(opts) >= 3000,
        f"options={len(opts)} (release {dd_q.dataset.snomed_release_date})",
    )

    # ---- 5. Publish + anonymous submission via the REAL take view ----
    survey.status = Survey.Status.PUBLISHED
    survey.visibility = Survey.Visibility.PUBLIC
    survey.save(update_fields=["status", "visibility"])
    check(10, "survey published + public", survey.is_live())

    anon = Client(SERVER_NAME="staging.checktick.uk")
    take_url = reverse("surveys:take", kwargs={"slug": survey.slug})
    r = anon.get(take_url)
    check(
        11,
        "take renders for anonymous visitor",
        r.status_code == 200
        and sctid.encode() in r.content  # SSR'd SNOMED options
        and marker not in r.content.decode(),  # answer not echoed back
    )
    r = anon.post(take_url, {f"q_{text_q.id}": marker, f"q_{dd_q.id}": sctid})
    check(
        12,
        "submission redirects to thank-you",
        r.status_code == 302 and "thank-you" in r["Location"],
    )
    resp = SurveyResponse.objects.get(survey=survey)
    enc = bytes(resp.enc_answers) if resp.enc_answers else b""
    check(
        13,
        "response stored as ECIES submission blob (no plaintext)",
        is_submission_blob(enc) and resp.answers == {} and marker.encode() not in enc,
    )

    # ---- 6. Owner unlock via the REAL view ----
    r = c.post(
        reverse("surveys:unlock", kwargs={"slug": survey.slug}),
        {"unlock_method": "password", "password": survey_pw},
    )
    check(
        14,
        "unlock with password succeeds",
        r.status_code == 302 and bool(c.session.get("unlock_credentials")),
    )

    # ---- 7. Decrypt through the REAL export view ----
    r = c.get(reverse("surveys:export_csv", kwargs={"slug": survey.slug}))
    # StreamingHttpResponse — consume the streaming iterator
    body = (
        b"".join(r.streaming_content).decode("utf-8", "replace")
        if hasattr(r, "streaming_content")
        else r.content.decode("utf-8", "replace")
    )
    check(
        15,
        "export CSV decrypts submission",
        r.status_code == 200 and marker in body and term in body,
        "answer + SNOMED preferred term present in CSV",
    )

    # ---- 8. Recovery-path unlock (model level) ----
    kek = survey.unlock_with_recovery(recovery_phrase)
    check(16, "recovery-phrase unlock returns key material", kek is not None)

    # ---- 9. Vault KV escrow round-trip via the REAL VaultClient ----
    # Path must match the checktick-app policy grant (surveys/+/kek); the
    # users/<id>/surveys/<id>/recovery-kek escrow path used by
    # recover_user_survey_kek is NOT granted to the AppRole (POC finding,
    # recorded in the runbook) — the app-role escrow path is surveys/<id>/kek.
    vc = get_vault_client()
    kek32 = secrets.token_bytes(32)
    hier = secrets.token_bytes(32)
    vault_path = f"surveys/{survey.id}/kek"
    vc.encrypt_survey_kek(kek32, hier, vault_path)
    back = vc.decrypt_survey_kek(vault_path, hier)
    vc.delete_survey_kek(vault_path)
    check(
        17,
        "Vault KV write -> read -> unwrap -> delete",
        back == kek32,
        f"path=smoke/{survey.id}",
    )

    # ---- 10. Audit trail ----
    n_unlock = AuditLog.objects.filter(actor=user, survey=survey).count()
    n_2fa = AuditLog.objects.filter(actor=user).count()
    check(
        18,
        "AuditLog entries written (unlock + 2FA)",
        n_unlock >= 1 and n_2fa >= 2,
        f"survey-scope={n_unlock} user-scope={n_2fa}",
    )

finally:
    # ---- Cleanup: user delete cascades survey -> responses; AuditLog actor
    # is SET_NULL so the audit trail survives. Vault secret already deleted. ----
    if vault_path:
        try:
            get_vault_client().delete_survey_kek(vault_path)
        except Exception:
            pass
    if survey is not None:
        sid = survey.id
        Survey.objects.filter(id=sid).delete()
        print(f"[cleanup] survey {sid} deleted")
    if user is not None:
        user.delete()
        print("[cleanup] user deleted")

failed = [n for s, n in results if s == "FAIL"]
print()
print(f"{'=' * 60}")
if failed:
    print(f"SMOKE RESULT: FAIL ({len(failed)}/{len(results)} steps failed)")
    for n in failed:
        print(f"  FAILED: {n}")
    raise SystemExit(1)
print(f"SMOKE RESULT: PASS — {len(results)}/{len(results)} steps green")
print("Round-trip proven on staging: login+2FA, encrypted survey create,")
print("ECIES submission, password unlock, export decrypt, Vault escrow,")
print("SNOMED resolver on the pod-local copy, audit trail.")
