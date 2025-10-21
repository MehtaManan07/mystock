from pydantic_settings import BaseSettings
from pydantic import Field
import os
from pathlib import Path


class Config(BaseSettings):
    # PostgreSQL Database Configuration
    database_url: str = Field(default="", alias="DB_URL")
    pg_password: str = Field(default="", alias="PG_PASSWORD")
    pg_host: str = Field(default="", alias="PG_HOST")
    pg_database: str = Field(default="", alias="PG_DATABASE")
    pg_user: str = Field(default="", alias="PG_USER")
    pg_port: int = Field(default=5432, alias="PG_PORT")
    pg_ssl_mode: str = Field(default="require", alias="PG_SSL_MODE")
    pg_ssl_cert_path: str = Field(
        default=str(Path(__file__).parent.parent.parent / "ca.pem"),
        alias="PG_SSL_CERT_PATH",
    )
    pg_ssl_verify: bool = Field(default=False, alias="PG_SSL_VERIFY")

    # JWT Configuration
    jwt_secret: str = Field(default="", alias="JWT_SECRET")

    # AWS Configuration
    aws_region: str = Field(default="", alias="MY_AWS_REGION")
    aws_access_key_id: str = Field(default="", alias="MY_AWS_ACCESS_KEY_ID")
    aws_secret_access_key: str = Field(default="", alias="MY_AWS_SECRET_ACCESS_KEY")

    is_production: bool = (
        os.getenv("ENVIRONMENT", "development").lower() == "production"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instantiate the settings
config = Config()
