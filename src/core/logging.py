import logging
import json
import sys
from datetime import datetime, timezone
from src.core.context import get_request_id, get_tenant_id
from src.config import settings

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
            "tenant_id": str(get_tenant_id()) if get_tenant_id() else None,
        }
        
        # Include exception info if available
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
            
        return json.dumps(log_data)

def setup_logging():
    root_logger = logging.getLogger()
    
    # Clear existing handlers
    if root_logger.handlers:
        for handler in root_logger.handlers:
            root_logger.removeHandler(handler)
            
    handler = logging.StreamHandler(sys.stdout)
    
    if settings.ENV == "development":
        # Pretty logging for local development
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] (ReqID: %(request_id)s, TenantID: %(tenant_id)s) %(name)s: %(message)s"
        )
        # We need a custom filter to inject request_id and tenant_id into record when formatting
        class ContextFilter(logging.Filter):
            def filter(self, record):
                record.request_id = get_request_id() or "-"
                record.tenant_id = str(get_tenant_id()) if get_tenant_id() else "-"
                return True
        handler.addFilter(ContextFilter())
    else:
        # Structured JSON for testing and production
        formatter = JSONFormatter()
        
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)
    
    # Set logging level
    log_level = logging.DEBUG if settings.ENV == "development" else logging.INFO
    root_logger.setLevel(log_level)
    
    # Set noisy loggers to WARNING
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING if settings.ENV != "development" else logging.INFO)

logger = logging.getLogger("auth_service")
