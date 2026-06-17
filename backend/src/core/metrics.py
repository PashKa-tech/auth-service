from prometheus_client import Counter, Histogram, Gauge

# Prometheus Metrics definition

LOGIN_COUNTER = Counter(
    "auth_login_total",
    "Total login attempts",
    ["status", "tenant_id"]
)

REFRESH_COUNTER = Counter(
    "auth_token_refresh_total",
    "Total token refresh attempts",
    ["status"]
)

REQUEST_LATENCY = Histogram(
    "auth_request_duration_seconds",
    "HTTP request latency in seconds",
    ["endpoint"]
)

ACTIVE_SESSIONS = Gauge(
    "auth_active_sessions_gauge",
    "Number of active sessions",
    ["tenant_id"]
)
