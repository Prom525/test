from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Public/runtime URLs - environment specific, therefore required.
    PUBLIC_API_URL: str
    PUBLIC_WEB_URL: str
    PROMATI_API_BASE_URL: str
    CORS_ALLOWED_ORIGINS: str = ""

    # Database
    DATABASE_URL: str

    # MinIO
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "files"
    MINIO_BUCKET_RFQ: str = "rfq-artifacts"
    MINIO_SECURE: bool = False

    # Qdrant
    QDRANT_URL: str
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION: str = "rag_docs_openai_1536"

    # Internal services
    EDOCR2_URL: str
    TECHREVIEW_URL: str

    # Keycloak - authentication is enabled in a later phase.
    KEYCLOAK_ISSUER: str
    KEYCLOAK_JWKS_URL: str
    KEYCLOAK_AUDIENCE: str = "api"

    # OpenAI
    OPENAI_API_KEY: str | None = None
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_CHAT_MODEL: str | None = None
    OPENAI_VISION_MODEL: str | None = None

    # Temporary org-admin Basic Auth, until Keycloak roles replace it.
    ORG_ADMIN_USER: str
    ORG_ADMIN_PASSWORD: str

    # RFQ runtime paths
    RFQ_PDF_DIR: str
    RFQ_UPLOAD_DIR: str

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            value.strip()
            for value in self.CORS_ALLOWED_ORIGINS.split(",")
            if value.strip()
        ]


settings = Settings()