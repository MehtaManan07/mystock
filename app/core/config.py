from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
import os
from pathlib import Path


class Config(BaseSettings):
    # PostgreSQL Database Configuration
    database_url: str = Field(default="", alias="DB_URL")

    # JWT Configuration
    jwt_secret: str = Field(default="", alias="JWT_SECRET")

    # AWS Configuration
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# Instantiate the settings
config = Config()
