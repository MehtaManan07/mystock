from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import os
from pathlib import Path


# Get project root directory
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Config(BaseSettings):
    # Database Configuration
    # Default: SQLite in ./data/inventory.db
    # For PostgreSQL, set DB_URL to: postgresql+asyncpg://user:pass@host/db
    database_url: str = Field(
        default=f"sqlite+aiosqlite:///{PROJECT_ROOT}/data/inventory.db",
        alias="DB_URL"
    )

    # JWT Configuration
    jwt_secret: str = Field(default="", alias="JWT_SECRET")

    # AWS Configuration (legacy, for S3)
    aws_region: str = Field(default="", alias="MY_AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="MY_AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="MY_AWS_SECRET_ACCESS_KEY")
    s3_bucket_name: str = Field(default="", alias="S3_BUCKET_NAME")
    s3_invoice_prefix: str = Field(default="invoices/", alias="S3_INVOICE_PREFIX")

    # Redis Configuration
    redis_host: str = Field(default="localhost", alias="REDIS_HOST")
    redis_port: int = Field(default=6379, alias="REDIS_PORT")
    redis_password: str = Field(default="", alias="REDIS_PASSWORD")
    redis_ssl: bool = Field(default=False, alias="REDIS_SSL")
    redis_db: int = Field(default=0, alias="REDIS_DB")
    redis_decode_responses: bool = Field(default=True, alias="REDIS_DECODE_RESPONSES")

    # Environment Configuration
    environment: str = Field(default="development", alias="ENVIRONMENT")
    
    secret_key: str = Field(default="", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="ALGORITHM")
    # Token expiration: 7 days for development, override in .env for production
    access_token_expire_minutes: int = Field(default=10080, alias="ACCESS_TOKEN_EXPIRE_MINUTES")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite database."""
        return self.database_url.startswith("sqlite")

    @property
    def sqlite_db_path(self) -> Path | None:
        """Get the SQLite database file path, or None if not using SQLite."""
        if not self.is_sqlite:
            return None
        # Parse path from sqlite URL: sqlite+aiosqlite:///path/to/db.db
        # Handle both relative (///) and absolute (////) paths
        url = self.database_url
        if ":///" in url:
            path = url.split(":///", 1)[1]
            return Path(path)
        return None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instantiate the settings
config = Config()

# Ensure data directory exists for SQLite
if config.is_sqlite and config.sqlite_db_path:
    config.sqlite_db_path.parent.mkdir(parents=True, exist_ok=True)
