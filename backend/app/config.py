"""
Application configuration using python-decouple
"""
from decouple import config
from typing import List


class Settings:
    # Database
    DATABASE_URL: str = config("DATABASE_URL", default="sqlite:///./obatek.db")

    # JWT Settings
    SECRET_KEY: str = config("SECRET_KEY", default="dev-secret-key-change-in-production")
    ALGORITHM: str = config("ALGORITHM", default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = config(
        "ACCESS_TOKEN_EXPIRE_MINUTES", default=1440, cast=int
    )
    REFRESH_TOKEN_EXPIRE_DAYS: int = config(
        "REFRESH_TOKEN_EXPIRE_DAYS", default=7, cast=int
    )

    # Google Maps API
    GOOGLE_MAPS_API_KEY: str | None = config("GOOGLE_MAPS_API_KEY", default=None)

    # CORS
    CORS_ORIGINS: List[str] = config(
        "CORS_ORIGINS",
        default="http://localhost:5173,http://localhost:3000",
        cast=lambda v: [s.strip() for s in v.split(",")],
    )

    # File uploads
    UPLOAD_DIR: str = config("UPLOAD_DIR", default="uploads")
    MAX_FILE_SIZE_MB: int = config("MAX_FILE_SIZE_MB", default=10, cast=int)

    # Office address for distance calculations
    OFFICE_ADDRESS: str = config(
        "OFFICE_ADDRESS",
        default="244 Bell Street North, K1R 5T7, Ottawa, Ontario, Canada"
    )

    # Company card digits (comma-separated list of last 4 digits)
    # Receipts paid with these cards won't be reimbursed to workers
    COMPANY_CARD_DIGITS: str = config("COMPANY_CARD_DIGITS", default="5564")


settings = Settings()
