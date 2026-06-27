import logging
import re


class RedactionFilter(logging.Filter):
    """
    Redact common credentials and personally identifiable information (PII)
    from log messages before they leave the application.

    This filter is intended as a safety net. The primary defence is that
    application code should never log request bodies, decrypted survey data
    or secrets.
    """

    KEY_VALUE_PATTERNS = [
        # ------------------------------------------------------------------
        # Patient identifiers
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(nhs_number|hospital_number|mrn|patient_id)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        re.compile(
            r'(?i)\b(first_name|surname|last_name|family_name|given_name|middle_name)\b\s*[:=]\s*[\'"]?([^,\'"}]+)'
        ),
        re.compile(
            r'(?i)\b(date_of_birth|dob|birth_date)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        re.compile(
            r'(?i)\b(sex|gender|ethnicity|postcode|email|phone|mobile|address)\b\s*[:=]\s*[\'"]?([^,\'"}]+)'
        ),
        # ------------------------------------------------------------------
        # Authentication / credentials
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(password|passwd|username|user|secret|token|access_token|refresh_token|api_key|authorization|bearer|cookie|sessionid|csrftoken)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        # ------------------------------------------------------------------
        # Vault
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(vault_token|vault_secret_id|vault_role_id|vault_password)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        # ------------------------------------------------------------------
        # Microsoft Graph / Azure
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(client_secret|client_id|tenant_id|application_id)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        # ------------------------------------------------------------------
        # SMTP / Mailgun
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(smtp_password|smtp_username|mailgun_api_key)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
        # ------------------------------------------------------------------
        # CheckTick/OpenObserve
        # ------------------------------------------------------------------
        re.compile(
            r'(?i)\b(logs_key|logs_access_key|openobserve_key|openobserve_password)\b\s*[:=]\s*[\'"]?([^,\'"\s}]+)'
        ),
    ]

    VALUE_PATTERNS = [
        # Email addresses
        (
            re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
            "[EMAIL REDACTED]",
        ),
        # Bearer tokens in HTTP headers
        (
            re.compile(r"(?i)\bBearer\s+[A-Za-z0-9\-._~+/]+=*"),
            "Bearer [REDACTED]",
        ),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()

        # Preserve the field name
        for pattern in self.KEY_VALUE_PATTERNS:
            msg = pattern.sub(r"\1=[REDACTED]", msg)

        # Stand-alone values
        for pattern, replacement in self.VALUE_PATTERNS:
            msg = pattern.sub(replacement, msg)

        record.msg = msg
        record.args = ()

        return True
