import asyncio
import json
import os
import re
from typing import Annotated, Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Path, WebSocket, WebSocketDisconnect, status
from tortoise.exceptions import DoesNotExist

from app import logging, schemas
from app.models.EncodingTask import EncodingTask as EncodingTaskModel
from app.models.RecordedProgram import RecordedProgram
from app.models.User import User
from app.routers.UsersRouter import GetCurrentUser
from app.streams.TSReplaceEncodingTask import TSReplaceEncodingTask
from app.schemas import EncodingTask


class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(connection)

    async def broadcast_json(self, data: Dict[str, Any] | List[Any]):
        await self.broadcast(json.dumps(data, ensure_ascii=False))

manager = ConnectionManager()

router = APIRouter(
    tags = ['TSReplace'],
    prefix = '/api/tsreplace',
)

# 実行中のタスクを管理する辞書
_running_tasks: Dict[str, TSReplaceEncodingTask] = {}
_last_broadcast_states: Dict[str, Dict[str, Any]] = {}
broadcast_task: Any = None


async def broadcast_progress_updates():
    """実行中のタスクの進捗を定期的に監視し、変更があればブロードキャストする"""
    logging.info('Started WebSocket progress broadcasting task.')
    while True:
        try:
            # 接続がない場合はタスクを一旦終了
            if not manager.active_connections:
                logging.info('No active WebSocket connections. Stopping progress broadcasting task.')
                global broadcast_task
                broadcast_task = None
                break

            tasks_to_broadcast = []

            for task_id, task in list(_running_tasks.items()):
                current_status = task.encoding_task.status
                current_progress = round(task.encoding_task.progress, 1)

                # 前回の状態と比較
                last_state = _last_broadcast_states.get(task_id)
                if last_state is None or last_state['status'] != current_status or last_state['progress'] != current_progress:
                    # 番組タイトルを取得
                    video_title = 'Unknown Video'
                    try:
                        if task.encoding_task.rec_file_id > 0:
                            from app.models.RecordedVideo import RecordedVideo
                            try:
                                recorded_video = await RecordedVideo.get(id=task.encoding_task.rec_file_id)
                                # recorded_program_idから直接RecordedProgramを取得
                                recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                                video_title = recorded_program.title or 'Unknown Video'
                            except DoesNotExist:
                                # RecordedVideoが見つからない場合、output_file_pathから新しいRecordedVideoを検索
                                # エンコード完了後にファイル名に_1などが追加される可能性があるため、ベース名から検索
                                if task.encoding_task.output_file_path:
                                    import pathlib
                                    output_path = pathlib.Path(task.encoding_task.output_file_path)
                                    # まず正確なパスで検索
                                    recorded_video = await RecordedVideo.get_or_none(file_path=task.encoding_task.output_file_path)
                                    # ベース名を事前に計算（後で使用するため）
                                    stem = output_path.stem
                                    base_stem = re.sub(r'_\d+$', '', stem)  # _1, _2などを除去
                                    if not recorded_video:
                                        # 見つからない場合、ベース名（_h264_1.ts -> _h264.ts）から検索
                                        base_path = output_path.parent / f"{base_stem}{output_path.suffix}"
                                        recorded_video = await RecordedVideo.get_or_none(file_path=str(base_path))
                                    if not recorded_video:
                                        # まだ見つからない場合、ファイル名に_h264, _h265, _av1を含むRecordedVideoを検索
                                        base_name_pattern = base_stem
                                        all_videos = await RecordedVideo.filter(file_path__contains=base_name_pattern).all()
                                        # _h264, _h265, _av1を含むファイルを優先
                                        for video in all_videos:
                                            if '_h264' in video.file_path or '_h265' in video.file_path or '_av1' in video.file_path:
                                                recorded_video = video
                                                break
                                        if not recorded_video and all_videos:
                                            recorded_video = all_videos[0]
                                    if recorded_video:
                                        recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                                        video_title = recorded_program.title or 'Unknown Video'
                                    else:
                                        logging.debug(f'RecordedVideo not found for task {task_id}: rec_file_id={task.encoding_task.rec_file_id}, output_file_path={task.encoding_task.output_file_path}. Title will be available after scan.')
                                else:
                                    logging.debug(f'RecordedVideo not found for task {task_id}: rec_file_id={task.encoding_task.rec_file_id}, output_file_path is None. Title will be available after scan.')
                    except Exception as e:
                        logging.warning(f'Failed to get video title for task {task_id}: {e}')

                    task_info = {
                        'task_id': task_id,
                        'video_id': task.encoding_task.rec_file_id,
                        'video_title': video_title,
                        'codec': task.encoding_task.codec,
                        'encoder_type': task.encoding_task.encoder_type,
                        'status': current_status,
                        'progress': current_progress,
                        'error_message': task.encoding_task.error_message,
                        'created_at': task.encoding_task.created_at.isoformat() if task.encoding_task.created_at else None,
                        'started_at': task.encoding_task.started_at.isoformat() if task.encoding_task.started_at else None,
                        'completed_at': task.encoding_task.completed_at.isoformat() if task.encoding_task.completed_at else None,
                    }
                    tasks_to_broadcast.append(task_info)
                    _last_broadcast_states[task_id] = {'status': current_status, 'progress': current_progress}

            if tasks_to_broadcast:
                await manager.broadcast_json({'type': 'progress_update', 'tasks': tasks_to_broadcast})

            # 完了/失敗/キャンセルしたタスクも _last_broadcast_states に保持する（エラー履歴含めて残す）
            # タスクは削除せずに保持する

        except Exception as ex:
            logging.error(f'[broadcast_progress_updates] Error: {ex}', exc_info=ex)

        # 1秒待機
        await asyncio.sleep(1)

def _generate_output_file_path(input_file_path: str, codec: str) -> str:
    """入力ファイルパスから出力ファイルパスを生成する"""
    from pathlib import Path

    input_path = Path(input_file_path)
    stem = input_path.stem.replace(' （', '（')
    output_filename = f"{stem}_{codec}{input_path.suffix}"
    return str(input_path.parent / output_filename)


def register_auto_encoding_task(tsreplace_task: 'TSReplaceEncodingTask') -> None:
    """自動エンコードタスクをWebSocket通知システムに登録する"""
    import asyncio

    task_id = tsreplace_task.encoding_task.task_id

    # タスクを管理辞書に追加（重複チェック）
    if task_id in _running_tasks:
        logging.warning(f'[register_auto_encoding_task] Task {task_id} already exists in _running_tasks, replacing with new task')
    _running_tasks[task_id] = tsreplace_task

    # WebSocketブロードキャストタスクが実行されていない場合は開始
    global broadcast_task
    if broadcast_task is None and manager.active_connections:
        broadcast_task = asyncio.create_task(broadcast_progress_updates())


def cleanup_auto_encoding_task(task_id: str) -> None:
    """
    自動エンコードタスクをクリーンアップする（無効化: タスクは削除せずに保持する）

    Args:
        task_id: タスクID
    """
    # タスクは削除せずに保持する（エラー履歴含めて残す）
    # 完了後もタスクリストに残し、エラー履歴含めて最終状態をクライアントが取得できるようにする
    logging.debug(f'cleanup_auto_encoding_task called for {task_id}, but keeping task in list for history')
    # if task_id in _running_tasks:
    #     del _running_tasks[task_id]
    # if task_id in _last_broadcast_states:
    #     del _last_broadcast_states[task_id]


@router.post(
    '/encode',
    summary = '手動エンコード開始 API',
    response_description = 'エンコードタスクの情報。',
    response_model = schemas.TSReplaceEncodingResponse,
)
async def StartManualEncodingAPI(
    request: schemas.TSReplaceManualEncodingRequest,
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定された録画番組の手動エンコードを開始する。<br>
    エンコード方式（ソフトウェア/ハードウェア）とコーデック（H.264/HEVC）を指定できる。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されている必要がある。
    """

    try:
        # 録画番組の存在確認
        recorded_program = await RecordedProgram.get(id=request.video_id).select_related('recorded_video')

        # 入力ファイルパスを決定
        # 再エンコード済みの場合、元ファイルが存在する場合は元ファイルを使用、削除されている場合はエンコード済みファイルを使用
        recorded_video = recorded_program.recorded_video
        
        # エンコード済みファイルが実際に存在するかチェック
        has_encoded_file = recorded_video.is_tsreplace_encoded and recorded_video.encoded_file_path and os.path.exists(recorded_video.encoded_file_path)
        
        if has_encoded_file:
            # エンコード済みファイルが存在する場合
            # 元ファイルが存在するかチェック
            if os.path.exists(recorded_video.file_path):
                # 元ファイルが存在する場合、元ファイルから再エンコード
                input_file_path = recorded_video.file_path
                logging.info(f'[StartManualEncodingAPI] Re-encoding from original file (already encoded video) [video_id: {request.video_id}]')
            else:
                # 元ファイルが削除されている場合、エンコード済みファイルから再エンコード（画質劣化の可能性あり）
                input_file_path = recorded_video.encoded_file_path
                logging.warning(f'[StartManualEncodingAPI] Re-encoding from encoded file (original file deleted) [video_id: {request.video_id}] - Quality degradation may occur')
        else:
            # エンコード済みファイルが存在しない場合、未エンコードとして扱う
            # データベースにis_tsreplace_encoded=Trueが設定されていても、実際のファイルが存在しない場合は未エンコードとして扱う
            if recorded_video.is_tsreplace_encoded and recorded_video.encoded_file_path:
                logging.warning(f'[StartManualEncodingAPI] is_tsreplace_encoded is True but encoded file does not exist, treating as unencoded [video_id: {request.video_id}, encoded_file_path: {recorded_video.encoded_file_path}]')
            # 未エンコードの場合、通常通り元ファイルを使用
            input_file_path = recorded_video.file_path

        # 出力ファイルパスを生成
        output_file_path = _generate_output_file_path(input_file_path, request.codec)

        # TSReplaceEncodingTaskを作成（内部でEncodingTaskが作成される）
        tsreplace_task = TSReplaceEncodingTask(
            input_file_path=input_file_path,
            output_file_path=output_file_path,
            codec=request.codec,
            encoder_type=request.encoder_type,
            quality_preset=request.quality_preset,
            delete_original=request.delete_original
        )

        # エンコードタスクのrec_file_idを設定
        tsreplace_task.encoding_task.rec_file_id = recorded_program.recorded_video.id

        # タスクIDを取得（TSReplaceEncodingTask内部で生成されたものを使用）
        task_id = tsreplace_task.encoding_task.task_id

        # タスクを管理辞書に追加（重複チェック）
        if task_id in _running_tasks:
            logging.warning(f'[StartManualEncodingAPI] Task {task_id} already exists in _running_tasks, replacing with new task')
        _running_tasks[task_id] = tsreplace_task

        # バックグラウンドでエンコード実行
        async def execute_and_cleanup():
            try:
                await tsreplace_task.execute()
            finally:
                # 完了後もタスクリストに残し、エラー履歴含めて最終状態をクライアントが取得できるようにする
                # タスクは削除せずに保持する（エラー履歴含めて残す）
                logging.info(f'Encoding task {task_id} completed, keeping in task list for history')

        asyncio.create_task(execute_and_cleanup())

        return schemas.TSReplaceEncodingResponse(
            success=True,
            task_id=task_id,
            detail='エンコードタスクを開始しました。',
        )

    except DoesNotExist:
        logging.error(f'[StartManualEncodingAPI] Specified video_id was not found [video_id: {request.video_id}]')
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='Specified video_id was not found',
        )
    except Exception as ex:
        logging.error(f'[StartManualEncodingAPI] Failed to start manual encoding [video_id: {request.video_id}]:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to start manual encoding: {ex!s}',
        )


@router.get(
    '/status/{task_id}',
    summary = 'エンコード状況取得 API',
    response_description = 'エンコードタスクの状況。',
    response_model = schemas.TSReplaceEncodingStatusResponse,
)
async def GetEncodingStatusAPI(
    task_id: Annotated[str, Path(description='エンコードタスクの ID 。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定されたエンコードタスクの状況を取得する。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されている必要がある。
    """

    try:
        # 実行中のタスクから状況を取得
        if task_id not in _running_tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Specified task_id was not found',
            )

        task = _running_tasks[task_id]

        return schemas.TSReplaceEncodingStatusResponse(
            success=True,
            task_id=task_id,
            status=task.encoding_task.status,
            progress=task.encoding_task.progress,
            detail=task.encoding_task.error_message or 'Processing',
            created_at=task.encoding_task.created_at,
            started_at=task.encoding_task.started_at,
            completed_at=task.encoding_task.completed_at,
            error_message=task.encoding_task.error_message,
        )

    except HTTPException:
        raise
    except Exception as ex:
        logging.error(f'[GetEncodingStatusAPI] Failed to get encoding status [task_id: {task_id}]:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get encoding status: {ex!s}',
        )


@router.delete(
    '/cancel/{task_id}',
    summary = 'エンコードキャンセル API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def CancelEncodingAPI(
    task_id: Annotated[str, Path(description='エンコードタスクの ID 。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定されたエンコードタスクをキャンセルする。<br>
    実行中のエンコード処理は安全に停止され、一時ファイルは削除される。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されている必要がある。
    """

    try:
        # 実行中のタスクをキャンセル
        if task_id not in _running_tasks:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Specified task_id was not found or cannot be cancelled',
            )

        task = _running_tasks[task_id]
        await task.cancel()

        # キャンセル後すぐにタスクを削除せず、状態が 'cancelled' になるのを待つ
        logging.info(f'[CancelEncodingAPI] Successfully cancelled encoding task [task_id: {task_id}]')

    except HTTPException:
        raise
    except Exception as ex:
        logging.error(f'[CancelEncodingAPI] Failed to cancel encoding [task_id: {task_id}]:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to cancel encoding: {ex!s}',
        )


@router.delete(
    '/task/{task_id}',
    summary = 'エンコードタスク削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
async def DeleteEncodingTaskAPI(
    task_id: Annotated[str, Path(description='エンコードタスクの ID 。')],
    current_user: Annotated[User, Depends(GetCurrentUser)],
):
    """
    指定されたエンコードタスクをデータベースから削除する。<br>
    実行中のタスクは削除できない（先にキャンセルする必要がある）。<br>
    JWT エンコードされたアクセストークンがリクエストの Authorization: Bearer に設定されている必要がある。
    """

    try:
        # 実行中のタスクは削除できない
        if task_id in _running_tasks:
            task = _running_tasks[task_id]
            if task.encoding_task.status in ['queued', 'processing']:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail='Cannot delete running or queued task. Please cancel it first.',
                )

        # データベースからタスクを削除
        try:
            db_task = await EncodingTaskModel.get(task_id=task_id)
            await db_task.delete()
            logging.info(f'[DeleteEncodingTaskAPI] Successfully deleted encoding task from database [task_id: {task_id}]')
        except DoesNotExist:
            logging.info(f'[DeleteEncodingTaskAPI] Task not found in database [task_id: {task_id}]')

        # メモリ上のタスクも削除
        if task_id in _running_tasks:
            del _running_tasks[task_id]
        if task_id in _last_broadcast_states:
            del _last_broadcast_states[task_id]

    except HTTPException:
        raise
    except Exception as ex:
        logging.error(f'[DeleteEncodingTaskAPI] Failed to delete encoding task [task_id: {task_id}]:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to delete encoding task: {ex!s}',
        )


@router.get(
    '/queue',
    summary = 'エンコードキュー取得 API',
    response_description = 'エンコードキューの状況。',
    response_model = schemas.TSReplaceEncodingQueueResponse,
)
async def GetEncodingQueueAPI():
    """
    現在のエンコードキューの状況を取得する。<br>
    実行中・待機中・完了済みのエンコードタスクの一覧を返す。<br>
    認証は不要です。
    """

    try:
        processing_tasks = []
        queued_tasks = []
        completed_tasks = []
        failed_tasks = []

        # 重複を防ぐために、既に追加されたタスクIDを追跡
        added_task_ids = set()

        # データベースからすべてのタスクを取得（同じtask_idの場合は最新のもののみ）
        # まず、すべてのタスクを取得してから、task_idでグループ化して最新のものだけを保持
        all_db_tasks = await EncodingTaskModel.all().order_by('-created_at')
        task_ids_from_db = set()

        # task_idでグループ化し、最新のものだけを保持
        db_tasks_dict = {}
        duplicate_count = 0
        for db_task in all_db_tasks:
            task_id = db_task.task_id
            if task_id not in db_tasks_dict:
                db_tasks_dict[task_id] = db_task
            else:
                # 既に存在する場合、created_atが新しい方を保持
                duplicate_count += 1
                existing_task = db_tasks_dict[task_id]
                if db_task.created_at and existing_task.created_at:
                    if db_task.created_at > existing_task.created_at:
                        db_tasks_dict[task_id] = db_task
                        logging.warning(f'Duplicate task_id in database: {task_id}, keeping newer one (created_at: {db_task.created_at} vs {existing_task.created_at})')
                    elif db_task.created_at == existing_task.created_at:
                        # created_atが同じ場合、idが大きい方を保持（より新しいレコード）
                        if db_task.id > existing_task.id:
                            db_tasks_dict[task_id] = db_task
                            logging.warning(f'Duplicate task_id in database: {task_id}, same created_at, keeping one with larger id ({db_task.id} vs {existing_task.id})')
                elif db_task.created_at:
                    db_tasks_dict[task_id] = db_task
                    logging.warning(f'Duplicate task_id in database: {task_id}, keeping one with created_at')
                elif db_task.id > existing_task.id:
                    # created_atが両方Noneの場合、idが大きい方を保持
                    db_tasks_dict[task_id] = db_task
                    logging.warning(f'Duplicate task_id in database: {task_id}, both have no created_at, keeping one with larger id ({db_task.id} vs {existing_task.id})')

        if duplicate_count > 0:
            logging.warning(f'Found {duplicate_count} duplicate task_id(s) in database, kept only the latest ones')

        db_tasks = list(db_tasks_dict.values())

        for db_task in db_tasks:
            task_ids_from_db.add(db_task.task_id)

            # 重複チェック: 既に追加されたタスクIDはスキップ
            if db_task.task_id in added_task_ids:
                logging.warning(f'Duplicate task_id detected in database: {db_task.task_id}, skipping')
                continue

            # 番組タイトルを取得
            video_title = 'Unknown Video'
            try:
                if db_task.rec_file_id > 0:
                    from app.models.RecordedVideo import RecordedVideo
                    try:
                        recorded_video = await RecordedVideo.get(id=db_task.rec_file_id)
                        # recorded_program_idから直接RecordedProgramを取得
                        recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                        video_title = recorded_program.title or 'Unknown Video'
                    except DoesNotExist:
                        # RecordedVideoが見つからない場合、output_file_pathから新しいRecordedVideoを検索
                        # エンコード完了後にファイル名に_1などが追加される可能性があるため、ベース名から検索
                        if db_task.output_file_path:
                            import pathlib
                            output_path = pathlib.Path(db_task.output_file_path)
                            # まず正確なパスで検索
                            recorded_video = await RecordedVideo.get_or_none(file_path=db_task.output_file_path)
                            # ベース名を事前に計算（後で使用するため）
                            stem = output_path.stem
                            base_stem = re.sub(r'_\d+$', '', stem)  # _1, _2などを除去
                            if not recorded_video:
                                # 見つからない場合、ベース名（_h264_1.ts -> _h264.ts）から検索
                                base_path = output_path.parent / f"{base_stem}{output_path.suffix}"
                                recorded_video = await RecordedVideo.get_or_none(file_path=str(base_path))
                            if not recorded_video:
                                # まだ見つからない場合、ファイル名に_h264, _h265, _av1を含むRecordedVideoを検索
                                base_name_pattern = base_stem
                                all_videos = await RecordedVideo.filter(file_path__contains=base_name_pattern).all()
                                # _h264, _h265, _av1を含むファイルを優先
                                for video in all_videos:
                                    if '_h264' in video.file_path or '_h265' in video.file_path or '_av1' in video.file_path:
                                        recorded_video = video
                                        break
                                if not recorded_video and all_videos:
                                    recorded_video = all_videos[0]
                            if recorded_video:
                                recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                                video_title = recorded_program.title or 'Unknown Video'
                            else:
                                logging.debug(f'RecordedVideo not found for task {db_task.task_id}: rec_file_id={db_task.rec_file_id}, output_file_path={db_task.output_file_path}. Title will be available after scan.')
                        else:
                            logging.debug(f'RecordedVideo not found for task {db_task.task_id}: rec_file_id={db_task.rec_file_id}, output_file_path is None. Title will be available after scan.')
            except Exception as e:
                logging.warning(f'Failed to get video title for task {db_task.task_id}: {e}')

            task_info = {
                'task_id': db_task.task_id,
                'video_id': db_task.rec_file_id,
                'video_title': video_title,
                'codec': db_task.codec,
                'encoder_type': db_task.encoder_type,
                'status': db_task.status,
                'progress': db_task.progress / 100.0 if db_task.progress >= 0 else 0.0,  # データベースは0-100、APIは0.0-1.0
                'created_at': db_task.created_at,
                'started_at': db_task.started_at,
                'completed_at': db_task.completed_at,
                'error_message': db_task.error_message
            }

            if db_task.status == 'processing':
                processing_tasks.append(task_info)
            elif db_task.status == 'queued':
                queued_tasks.append(task_info)
            elif db_task.status == 'completed':
                completed_tasks.append(task_info)
            elif db_task.status in ['failed', 'cancelled']:
                failed_tasks.append(task_info)

            # 追加されたタスクIDを記録
            added_task_ids.add(db_task.task_id)

        # メモリ上のタスクでデータベースにないものも追加（実行中のタスク）
        # メモリ上のタスクは最新の状態を反映しているため、データベースのタスクより優先する
        for task_id, task in _running_tasks.items():
            # 重複チェック: 既に追加されたタスクIDはスキップ（メモリ上のタスクを優先するため、データベースのタスクを上書き）
            if task_id in added_task_ids:
                # データベースから追加されたタスクを削除して、メモリ上のタスクで置き換える
                # まず、既存のタスクを各リストから削除
                for task_list in [processing_tasks, queued_tasks, completed_tasks, failed_tasks]:
                    task_list[:] = [t for t in task_list if t['task_id'] != task_id]
                logging.debug(f'Task {task_id} already added from database, replacing with memory task (latest state)')

            # 番組タイトルを取得
            video_title = 'Unknown Video'
            try:
                if task.encoding_task.rec_file_id > 0:
                    from app.models.RecordedVideo import RecordedVideo
                    try:
                        recorded_video = await RecordedVideo.get(id=task.encoding_task.rec_file_id)
                        # recorded_program_idから直接RecordedProgramを取得
                        recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                        video_title = recorded_program.title or 'Unknown Video'
                    except DoesNotExist:
                        # RecordedVideoが見つからない場合、output_file_pathから新しいRecordedVideoを検索
                        # エンコード完了後にファイル名に_1などが追加される可能性があるため、ベース名から検索
                        if task.encoding_task.output_file_path:
                            import pathlib
                            output_path = pathlib.Path(task.encoding_task.output_file_path)
                            # まず正確なパスで検索
                            recorded_video = await RecordedVideo.get_or_none(file_path=task.encoding_task.output_file_path)
                            # ベース名を事前に計算（後で使用するため）
                            stem = output_path.stem
                            base_stem = re.sub(r'_\d+$', '', stem)  # _1, _2などを除去
                            if not recorded_video:
                                # 見つからない場合、ベース名（_h264_1.ts -> _h264.ts）から検索
                                base_path = output_path.parent / f"{base_stem}{output_path.suffix}"
                                recorded_video = await RecordedVideo.get_or_none(file_path=str(base_path))
                            if not recorded_video:
                                # まだ見つからない場合、ファイル名に_h264, _h265, _av1を含むRecordedVideoを検索
                                base_name_pattern = base_stem
                                all_videos = await RecordedVideo.filter(file_path__contains=base_name_pattern).all()
                                # _h264, _h265, _av1を含むファイルを優先
                                for video in all_videos:
                                    if '_h264' in video.file_path or '_h265' in video.file_path or '_av1' in video.file_path:
                                        recorded_video = video
                                        break
                                if not recorded_video and all_videos:
                                    recorded_video = all_videos[0]
                            if recorded_video:
                                recorded_program = await RecordedProgram.get(id=recorded_video.recorded_program_id)
                                video_title = recorded_program.title or 'Unknown Video'
                            else:
                                logging.warning(f'Failed to find RecordedVideo for task {task_id}: rec_file_id={task.encoding_task.rec_file_id}, output_file_path={task.encoding_task.output_file_path}')
                        else:
                            logging.warning(f'Failed to find RecordedVideo for task {task_id}: rec_file_id={task.encoding_task.rec_file_id}, output_file_path is None')
            except Exception as e:
                logging.warning(f'Failed to get video title for task {task_id}: {e}')

            task_info = {
                'task_id': task_id,
                'video_id': task.encoding_task.rec_file_id,
                'video_title': video_title,
                'codec': task.encoding_task.codec,
                'encoder_type': task.encoding_task.encoder_type,
                'status': task.encoding_task.status,
                'progress': task.encoding_task.progress,
                'created_at': task.encoding_task.created_at,
                'started_at': task.encoding_task.started_at,
                'completed_at': task.encoding_task.completed_at,
                'error_message': task.encoding_task.error_message
            }

            if task.encoding_task.status == 'processing':
                processing_tasks.append(task_info)
            elif task.encoding_task.status == 'queued':
                queued_tasks.append(task_info)
            elif task.encoding_task.status == 'completed':
                completed_tasks.append(task_info)
            elif task.encoding_task.status in ['failed', 'cancelled']:
                failed_tasks.append(task_info)

            # 追加されたタスクIDを記録
            added_task_ids.add(task_id)

        # 最終的な重複チェック: 各リスト内での重複を排除
        def deduplicate_task_list(task_list: list) -> list:
            seen_ids = set()
            result = []
            for task in task_list:
                if task['task_id'] not in seen_ids:
                    seen_ids.add(task['task_id'])
                    result.append(task)
                else:
                    logging.warning(f'Duplicate task_id in final list: {task["task_id"]}, skipping')
            return result

        processing_tasks = deduplicate_task_list(processing_tasks)
        queued_tasks = deduplicate_task_list(queued_tasks)
        completed_tasks = deduplicate_task_list(completed_tasks)
        failed_tasks = deduplicate_task_list(failed_tasks)

        return schemas.TSReplaceEncodingQueueResponse(
            success=True,
            processing_tasks=processing_tasks,
            queued_tasks=queued_tasks,
            completed_tasks=completed_tasks,
            failed_tasks=failed_tasks,
        )

    except Exception as ex:
        logging.error('[GetEncodingQueueAPI] Failed to get encoding queue:', exc_info=ex)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Failed to get encoding queue: {ex!s}',
        )


@router.websocket('/progress/{task_id}')
async def EncodingProgressWebSocket(
    websocket: WebSocket,
    task_id: str,
):
    """
    指定されたエンコードタスクの進捗をWebSocketでリアルタイム配信する。<br>
    エンコード進捗、状態変更、完了通知をリアルタイムで受信できる。
    """

    await websocket.accept()

    try:
        # タスクの存在確認
        if task_id not in _running_tasks:
            await websocket.close(code=1008, reason='Task not found')
            return

        task = _running_tasks[task_id]

        # 初期状態を送信
        await websocket.send_json({
            'type': 'status',
            'task_id': task_id,
            'status': task.encoding_task.status,
            'progress': task.encoding_task.progress,
            'detail': task.encoding_task.error_message or 'Processing',
            'created_at': task.encoding_task.created_at.isoformat() if task.encoding_task.created_at else None,
            'started_at': task.encoding_task.started_at.isoformat() if task.encoding_task.started_at else None,
            'completed_at': task.encoding_task.completed_at.isoformat() if task.encoding_task.completed_at else None,
            'error_message': task.encoding_task.error_message,
        })

        # 進捗監視ループ
        last_progress = -1
        last_status = None

        while True:
            try:
                # タスクの現在の状態を取得
                current_status = task.encoding_task.status
                current_progress = task.encoding_task.progress

                # 状態や進捗が変化した場合、または定期的に更新を送信
                progress_changed = abs(current_progress - last_progress) >= 0.1  # 0.1%以上の変化
                status_changed = current_status != last_status

                if status_changed or progress_changed or last_progress == -1:
                    await websocket.send_json({
                        'type': 'status',
                        'task_id': task_id,
                        'status': current_status,
                        'progress': current_progress,
                        'detail': task.encoding_task.error_message or 'Processing',
                        'created_at': task.encoding_task.created_at.isoformat() if task.encoding_task.created_at else None,
                        'started_at': task.encoding_task.started_at.isoformat() if task.encoding_task.started_at else None,
                        'completed_at': task.encoding_task.completed_at.isoformat() if task.encoding_task.completed_at else None,
                        'error_message': task.encoding_task.error_message,
                    })

                    last_progress = current_progress
                    last_status = current_status

                # 完了・失敗・キャンセル時は接続を閉じる
                if current_status in ['completed', 'failed', 'cancelled']:
                    break

                # クライアントからのメッセージを待機（ping/pong用）
                try:
                    message = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)  # より短い間隔で監視
                    if message == 'ping':
                        await websocket.send_text('pong')
                except asyncio.TimeoutError:
                    # タイムアウトは正常（0.5秒ごとに進捗をチェック）
                    pass

            except WebSocketDisconnect:
                break

    except WebSocketDisconnect:
        logging.info(f'[EncodingProgressWebSocket] WebSocket disconnected for task_id: {task_id}')
    except Exception as ex:
        logging.error(f'[EncodingProgressWebSocket] Error in WebSocket connection for task_id {task_id}:', exc_info=ex)
        try:
            await websocket.close(code=1011, reason=f'Internal server error: {ex!s}')
        except:
            pass
    finally:
        # WebSocket終了処理
        logging.info(f'[EncodingProgressWebSocket] WebSocket connection closed for task_id: {task_id}')


@router.websocket('/progress')
async def encoding_progress_websocket_multiplexed(websocket: WebSocket):
    """
    全てのエンコードタスクの進捗を単一のWebSocketでリアルタイムに多重配信する。
    """
    global broadcast_task
    await manager.connect(websocket)

    # バックグラウンドタスクが実行されていなければ開始
    if broadcast_task is None or broadcast_task.done():
        broadcast_task = asyncio.create_task(broadcast_progress_updates())

    try:
        while True:
            # クライアントが接続している間、メッセージの受信を待機
            message = await websocket.receive_text()
            if message == 'ping':
                await websocket.send_text('pong')
    except WebSocketDisconnect:
        logging.info('Client disconnected from multiplexed progress WebSocket.')
    finally:
        manager.disconnect(websocket)
