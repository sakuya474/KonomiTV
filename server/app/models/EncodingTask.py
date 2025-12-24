
# Type Hints を指定できるように
# ref: https://stackoverflow.com/a/33533514/17124142
from __future__ import annotations

from datetime import datetime
from typing import cast

from tortoise import fields
from tortoise.fields import Field as TortoiseField
from tortoise.models import Model as TortoiseModel


class EncodingTask(TortoiseModel):

    # データベース上のテーブル名
    class Meta(TortoiseModel.Meta):
        table: str = 'encoding_tasks'

    # タスクID（UUID形式、主キー）
    task_id = fields.CharField(255, pk=True)

    # 録画ファイルID
    rec_file_id = fields.IntField()

    # 入力ファイルパス
    input_file_path = fields.TextField()

    # 出力ファイルパス
    output_file_path = fields.TextField()

    # 使用するコーデック
    codec = fields.CharField(10)  # 'h264' or 'hevc'

    # エンコーダーの種類
    encoder_type = fields.CharField(20)  # 'software' or 'hardware'

    # エンコード品質プリセット
    quality_preset = fields.CharField(50, default='medium')

    # タスクの状態
    status = fields.CharField(20, default='queued')  # 'queued', 'processing', 'completed', 'failed', 'cancelled'

    # 進捗率（0.0-1.0）
    progress = fields.FloatField(default=0.0)

    # タスク作成日時
    created_at = fields.DatetimeField(auto_now_add=True)

    # エンコード開始日時
    started_at = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))

    # エンコード完了日時
    completed_at = cast(TortoiseField[datetime | None], fields.DatetimeField(null=True))

    # エラーメッセージ
    error_message = cast(TortoiseField[str | None], fields.TextField(null=True))

    # リトライ回数
    retry_count = fields.IntField(default=0)

    # 最大リトライ回数
    max_retry_count = fields.IntField(default=3)

    # 元ファイルサイズ（バイト）
    original_file_size = cast(TortoiseField[int | None], fields.BigIntField(null=True))

    # エンコード後ファイルサイズ（バイト）
    encoded_file_size = cast(TortoiseField[int | None], fields.BigIntField(null=True))

    # エンコード処理時間（秒）
    encoding_duration = cast(TortoiseField[float | None], fields.FloatField(null=True))

    # 更新日時
    updated_at = fields.DatetimeField(auto_now=True)

