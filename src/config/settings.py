from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """All environment variables for Field Genius Engine."""

    # Twilio (WhatsApp via Twilio)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_whatsapp_number: str = "whatsapp:+14155238886"
    twilio_whatsapp_group_id: str = ""

    # Supabase
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str = ""

    # AI
    openai_api_key: str = ""
    anthropic_api_key: str = ""

    # Outputs (optional — engine works without these)
    google_service_account_email: str | None = None
    google_private_key: str | None = None
    google_spreadsheet_id: str | None = None
    gamma_api_key: str | None = None

    # Redis (job queue)
    redis_url: str = ""  # redis://default:xxx@host:port

    # Config
    default_implementation: str = "laundry_care"
    default_language: str = "es"
    environment: str = "production"  # development | production

    # CORS (comma-separated origins)
    cors_origins: str = "http://localhost:5173,http://localhost:3000,https://field-genius-backoffice.vercel.app,https://app.xponencial.net,https://xponencial.net,https://www.xponencial.net"

    # Webhook public URL (for Twilio signature verification — don't trust headers)
    webhook_public_url: str = ""  # e.g. https://zealous-endurance-production-f9b2.up.railway.app

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


settings = Settings()  # type: ignore[call-arg]
