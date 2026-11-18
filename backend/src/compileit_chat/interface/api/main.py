"""Production entry point: `uvicorn compileit_chat.interface.api.main:app`."""

from compileit_chat.config import Settings
from compileit_chat.container import Container
from compileit_chat.interface.api.app import ApiConfig, create_app
from compileit_chat.interface.api.log_config import configure_json_logging

settings = Settings()
configure_json_logging(settings.log_level)

app = create_app(
    Container(settings),
    ApiConfig(
        cors_origins=tuple(settings.api_cors_origins),
        rate_limit_requests=settings.api_rate_limit_requests,
        rate_limit_window_seconds=settings.api_rate_limit_window_seconds,
    ),
)
