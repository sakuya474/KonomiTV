from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient) -> str:
    return '''
        CREATE TABLE IF NOT EXISTS "bd_library" (
            "id" INTEGER PRIMARY KEY AUTOINCREMENT,
            "title" VARCHAR(255) NOT NULL,
            "path" VARCHAR(1024) NOT NULL UNIQUE,
            "titles" JSON NOT NULL,
            "created_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            "updated_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS "bd_library_mylist" (
            "id" VARCHAR(255) PRIMARY KEY,
            "bd_id" INTEGER NOT NULL,
            "title" VARCHAR(255) NOT NULL,
            "path" VARCHAR(1024) NOT NULL,
            "added_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS "bd_library_history" (
            "id" VARCHAR(255) PRIMARY KEY,
            "bd_id" INTEGER NOT NULL,
            "title" VARCHAR(255) NOT NULL,
            "path" VARCHAR(1024) NOT NULL,
            "position" INTEGER NOT NULL,
            "duration" INTEGER NOT NULL,
            "watched_at" TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    '''

async def downgrade(db: BaseDBAsyncClient) -> str:
    return '''
        DROP TABLE IF EXISTS "bd_library_history";
        DROP TABLE IF EXISTS "bd_library_mylist";
        DROP TABLE IF EXISTS "bd_library";
    '''

