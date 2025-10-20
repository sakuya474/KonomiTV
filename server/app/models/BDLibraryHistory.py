from tortoise import fields, models

class BDLibraryHistory(models.Model):
    '''
    BD視聴履歴モデル
    '''

    id = fields.CharField(max_length=255, pk=True)
    user_id = fields.IntField()  # ユーザーIDを追加
    bd_id = fields.IntField()
    title = fields.CharField(max_length=255)
    path = fields.CharField(max_length=1024)
    position = fields.IntField()  # 視聴位置（秒）
    duration = fields.IntField()  # 総再生時間（秒）
    watched_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = 'bd_library_history'

