from rest_framework.throttling import AnonRateThrottle


class ThrottleLogin(AnonRateThrottle):
    scope = "login"
