from tortoise import BaseDBAsyncClient

async def upgrade(db: BaseDBAsyncClient) -> str:
    return '''
        -- BDライブラリマイリストテーブルにuser_idカラムを追加
        ALTER TABLE "bd_library_mylist" ADD COLUMN "user_id" INTEGER;

        -- BDライブラリ視聴履歴テーブルにuser_idカラムを追加
        ALTER TABLE "bd_library_history" ADD COLUMN "user_id" INTEGER;

        -- 既存のデータに対してデフォルトのuser_idを設定（管理者ユーザーID: 1）
        UPDATE "bd_library_mylist" SET "user_id" = 1 WHERE "user_id" IS NULL;
        UPDATE "bd_library_history" SET "user_id" = 1 WHERE "user_id" IS NULL;

        -- user_idカラムをNOT NULLに変更
        -- SQLiteではALTER COLUMNでNOT NULLを設定できないため、テーブルを再作成する必要がある
        -- この部分は手動で対応する必要があります
    '''

async def downgrade(db: BaseDBAsyncClient) -> str:
    return '''
        -- user_idカラムを削除
        -- SQLiteではDROP COLUMNがサポートされていないため、手動で対応する必要があります
    '''

