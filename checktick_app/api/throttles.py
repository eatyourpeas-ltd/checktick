from rest_framework.throttling import AnonRateThrottle


class TokenObtainThrottle(AnonRateThrottle):
    """Strict per-IP throttle for the /api/token endpoint: 5 attempts per minute."""

    scope = "token_obtain"
    rate = "5/minute"
