from tortoise import fields, models

class BDLibraryMylist(models.Model):
    '''
    BDマイリストモデル
    '''

    id = fields.CharField(max_length=255, pk=True)
    user_id = fields.IntField()  # ユーザーIDを追加
    bd_id = fields.IntField()
    title = fields.CharField(max_length=255)
    path = fields.CharField(max_length=1024)
    added_at = fields.DatetimeField(auto_now_add=True)

    class Meta:
        table = 'bd_library_mylist'

