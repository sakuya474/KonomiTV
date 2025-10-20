import errno
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Annotated, cast

from PIL import Image
import puremagic
from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from app import logging
from app.config import Config
from app.schemas import Capture


# ルーター
router = APIRouter(
    tags = ['Captures'],
    prefix = '/api/captures',
)


@router.get(
    '',
    summary = 'キャプチャ画像一覧 API',
    response_model = list[Capture],
)
async def CapturesListAPI():
    """
    保存されているキャプチャ画像を年月単位で返す。<br><br>
    画像のEXIFメタデータから撮影日時を優先的に取得し、取得できない場合はファイル名からパースします。
    """

    # 返却するキャプチャリスト
    captures: list[Capture] = []

    # キャプチャ保存フォルダ配下のすべてのファイルを走査
    for upload_folder in Config().capture.upload_folders:
        if not Path(upload_folder).exists():
            continue
        for file in Path(upload_folder).glob('*'):
            if file.is_file() and file.suffix.lower() in ['.jpg', '.jpeg', '.png']:
                # ファイル名から情報をパース
                time = None
                channel_name = None
                program_title = None

                # 画像のメタデータ (EXIF) から撮影日時を取得
                if file.suffix.lower() in ['.jpg', '.jpeg']:
                    try:
                        with Image.open(file) as img:
                            # EXIF データを取得
                            exif_data = img.getexif()
                            if exif_data:
                                # DateTimeOriginal (撮影日時) タグ (36867) を探す
                                datetime_original_str = exif_data.get(36867)
                                if datetime_original_str and isinstance(datetime_original_str, str):
                                    # 'YYYY:MM:DD HH:MM:SS' 形式の文字列をパース
                                    time = datetime.strptime(datetime_original_str, '%Y:%m:%d %H:%M:%S')
                                else:
                                    # DateTime (ファイル変更日時) タグ (306) を探す
                                    datetime_str = exif_data.get(306)
                                    if datetime_str and isinstance(datetime_str, str):
                                        time = datetime.strptime(datetime_str, '%Y:%m:%d %H:%M:%S')
                    except Exception:
                        # Pillow で開けない、EXIF がない、パースできないなどのエラーは無視
                        pass

                # うまくいかなかったらファイル名から獲得
                if time is None:
                    # ex: Capture_20250630-183909.jpg
                    match = re.match(r'Capture_(\d{8}-\d{6})', file.name)
                    if match:
                        try:
                            time = datetime.strptime(match.group(1), '%Y%m%d-%H%M%S')
                        except ValueError:
                            pass

                captures.append(Capture(
                    path=str(file),
                    name=file.name,
                    size=file.stat().st_size,
                    url=f'/captures/{file.name}',
                    time=time,
                    program_title=program_title,
                    channel_name=channel_name,
                ))

    # ファイル名でソート
    captures.sort(key=lambda x: x.name, reverse=True)

    return captures


@router.get(
    '/{capture_name}',
    summary = 'キャプチャ画像取得 API',
    response_class = FileResponse,
)
async def CaptureAPIGetAPI(capture_name: str):
    """
    指定されたキャプチャ画像を取得する。
    """

    # upload_folders の中からファイルを探す
    for upload_folder in Config().capture.upload_folders:
        filepath = Path(upload_folder) / capture_name
        if filepath.exists():
            return FileResponse(filepath)

    # ファイルが見つからなかった場合は 404
    raise HTTPException(
        status_code = status.HTTP_404_NOT_FOUND,
        detail = 'Capture not found',
    )


@router.post(
    '',
    summary = 'キャプチャ画像アップロード API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def CaptureUploadAPI(
    image: Annotated[UploadFile, File(description='アップロードするキャプチャ画像 (JPEG or PNG)。')],
):
    """
    クライアント側でキャプチャした画像をサーバーにアップロードする。<br>
    アップロードされた画像は、サーバー設定で指定されたフォルダに保存される。<br>
    同期ファイル I/O を伴うため敢えて同期関数として実装している。
    """

    # 画像が JPEG または PNG かをチェック
    ## 万が一悪意ある攻撃者から危険なファイルを送り込まれないように
    mimetype: str = puremagic.magic_stream(image.file)[0].mime_type
    if mimetype != 'image/jpeg' and mimetype != 'image/png':
        logging.error('[CapturesRouter][CaptureUploadAPI] Invalid image file was uploaded.')
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Please upload JPEG or PNG image',
        )

    # シークを元に戻す（重要）
    ## puremagic を使った時点でファイルはシークされているため、戻さないと 0 バイトになる
    image.file.seek(0)

    # 先頭から順に保存容量が空いている保存先フォルダを探す
    upload_folders: list[Path] = [Path(folder) for folder in Config().capture.upload_folders]
    for index, upload_folder in enumerate(upload_folders):

        # 万が一保存先フォルダが存在しない場合は次の保存先フォルダを探す
        if not upload_folder.exists():
            continue

        # 保存先フォルダの空き容量が 10MB 未満なら、最後のフォルダでなければ次の保存先フォルダを探す
        upload_folder_disk_usage = shutil.disk_usage(upload_folder)
        if upload_folder_disk_usage.free < 10 * 1024 * 1024 and index < len(upload_folders) - 1:
            continue

        # ディレクトリトラバーサル対策のためのチェック
        ## ref: https://stackoverflow.com/a/45190125/17124142
        filename = Path(cast(str, image.filename))
        try:
            upload_folder.joinpath(filename).resolve().relative_to(upload_folder.resolve())
        except ValueError:
            logging.error('[CapturesRouter][CaptureUploadAPI] Invalid filename was specified.')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Specified filename is invalid',
            )

        # 保存するファイルパス
        filepath = upload_folder / filename

        # 既にファイルが存在していた場合は上書きしないようにリネーム
        ## ref: https://note.nkmk.me/python-pathlib-name-suffix-parent/
        count = 1
        while filepath.exists():
            filepath = upload_folder / f'{filename.stem}-{count}{filename.suffix}'
            count += 1

        # キャプチャを保存
        try:
            with open(filepath, mode='wb') as buffer:
                shutil.copyfileobj(image.file, buffer)
        except PermissionError:
            logging.error('[CapturesRouter][CaptureUploadAPI] Permission denied to save the file.')
            raise HTTPException(
                status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail = 'Permission denied to save the file',
            )
        except OSError as ex:
            is_disk_full_error = False
            if hasattr(ex, 'winerror'):
                is_disk_full_error = ex.winerror == 112  # type: ignore
            if hasattr(ex, 'errno'):
                is_disk_full_error = ex.errno == errno.ENOSPC
            if is_disk_full_error is True:
                logging.error('[CapturesRouter][CaptureUploadAPI] No space left on the device.')
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'No space left on the device',
                )
            else:
                logging.error('[CapturesRouter][CaptureUploadAPI] Unexpected OSError:', exc_info=ex)
                raise HTTPException(
                    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail = 'Unexpected error occurred while saving the file',
                )

        # キャプチャのアップロードに成功したら 204 No Content を返す
        return

    # 保存先フォルダが見つからなかった場合はエラー
    logging.error('[CapturesRouter][CaptureUploadAPI] No available folder to save the file.')
    raise HTTPException(
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail = 'No available folder to save the file',
    )


@router.delete(
    '/{capture_name}',
    summary = 'キャプチャ画像削除 API',
    status_code = status.HTTP_204_NO_CONTENT,
)
def CaptureDeleteAPI(capture_name: str):
    """
    指定されたキャプチャ画像を削除する。
    """

    # ファイル名に / や .. が含まれている場合はエラー
    if '/' in capture_name or '..' in capture_name:
        raise HTTPException(
            status_code = status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail = 'Specified capture_name is invalid',
        )

    # upload_folders の中からファイルを探して削除
    for upload_folder in Config().capture.upload_folders:
        filepath = Path(upload_folder) / capture_name
        if filepath.exists():
            try:
                os.remove(filepath)
            except Exception as ex:
                logging.error(f'[CapturesRouter][CaptureDeleteAPI] Failed to delete capture: {filepath}', exc_info=ex)
                raise HTTPException(
                    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail = 'Failed to delete capture',
                )
            return

    # ファイルが見つからなかった場合は 404
    raise HTTPException(
        status_code = status.HTTP_404_NOT_FOUND,
        detail = 'Capture not found',
    )
