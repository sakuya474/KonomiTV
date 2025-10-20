from tortoise import fields, models

class BDLibrary(models.Model):
    '''
    BDライブラリ（NAS上のBDリッピングファイル管理用）モデル
    '''

    id = fields.IntField(pk=True)
    title = fields.CharField(max_length=255)
    path = fields.CharField(max_length=1024, unique=True)
    titles = fields.JSONField()  # タイトルリスト（各タイトルのm3u8パス・チャプター情報など）
    duration = fields.IntField(null=True)  # 動画の総再生時間（秒）
    created_at = fields.DatetimeField(auto_now_add=True)
    updated_at = fields.DatetimeField(auto_now=True)

    class Meta:
        table = 'bd_library'

