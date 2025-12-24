from tortoise import BaseDBAsyncClient


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "encoding_tasks" (
    "task_id" VARCHAR(255) NOT NULL PRIMARY KEY,
    "rec_file_id" INT NOT NULL,
    "input_file_path" TEXT NOT NULL,
    "output_file_path" TEXT NOT NULL,
    "codec" VARCHAR(10) NOT NULL,
    "encoder_type" VARCHAR(20) NOT NULL,
    "quality_preset" VARCHAR(50) NOT NULL DEFAULT 'medium',
    "status" VARCHAR(20) NOT NULL DEFAULT 'queued',
    "progress" REAL NOT NULL DEFAULT 0,
    "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "started_at" TIMESTAMP,
    "completed_at" TIMESTAMP,
    "error_message" TEXT,
    "retry_count" INT NOT NULL DEFAULT 0,
    "max_retry_count" INT NOT NULL DEFAULT 3,
    "original_file_size" BIGINT,
    "encoded_file_size" BIGINT,
    "encoding_duration" REAL,
    "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "encoding_tasks";"""
