from rest_framework.throttling import AnonRateThrottle


class AuthRateThrottle(AnonRateThrottle):
    """Rate limit anonymous auth endpoints by client IP.

    The rate is configured with REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["auth"]
    (default 10/min) and can be tuned with AUTH_THROTTLE_RATE.
    """

    scope = "auth"
