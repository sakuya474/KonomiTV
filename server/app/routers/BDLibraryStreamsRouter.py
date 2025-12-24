import os
import os
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import FileResponse

from app.constants import QUALITY, QUALITY_TYPES
from app.models.BDLibrary import BDLibrary

router = APIRouter(
    tags=['Streams'],
    prefix='/api/streams/bd-library',
)

async def ValidateBDID(bd_id: Annotated[int, Path(description='BDライブラリのID')]) -> BDLibrary:
    bd = await BDLibrary.get_or_none(id=bd_id)
    if bd is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Specified bd_id was not found')
    return bd

def ValidateQuality(quality: Annotated[str, Path(description='画質')]) -> QUALITY_TYPES:
    if quality not in QUALITY:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail='Invalid quality')
    return quality

# 1. playlist.m3u8返却API（先に記述）
@router.get('/{bd_id}/{quality}/playlist.m3u8', summary='BD HLS プレイリスト返却API', response_class=Response)
async def BDHLSPlaylistAPI(
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    bd: BDLibrary = Depends(ValidateBDID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    m3u8_path = os.path.join(bd.path, quality, 'playlist.m3u8')
    if not os.path.exists(m3u8_path):
        raise HTTPException(status_code=404, detail='playlist.m3u8 not found')

    # プレイリストファイルを読み込み、TSファイルのURLにsession_idを追加
    with open(m3u8_path, 'r', encoding='utf-8') as f:
        playlist_content = f.read()

    # .tsファイルの行にsession_idパラメータを追加
    lines = playlist_content.split('\n')
    modified_lines = []
    for line in lines:
        if line.endswith('.ts'):
            # TSファイル名にsession_idパラメータを追加
            modified_line = f"{line}?session_id={session_id}"
            modified_lines.append(modified_line)
        else:
            modified_lines.append(line)

    modified_playlist = '\n'.join(modified_lines)

    return Response(
        content=modified_playlist,
        media_type='application/vnd.apple.mpegurl',
        headers={'Cache-Control': 'no-store'}
    )

# 2. TSファイル返却API（後に記述）
@router.get('/{bd_id}/{quality}/{ts_filename}', summary='BD HLS TSファイル返却API', response_class=Response)
async def BDHLSTsFileAPI(
    ts_filename: Annotated[str, Path(description='TSファイル名')],
    session_id: Annotated[str, Query(description='セッション ID（クライアント側で適宜生成したランダム値を指定する）。')],
    bd: BDLibrary = Depends(ValidateBDID),
    quality: QUALITY_TYPES = Depends(ValidateQuality),
):
    if '/' in ts_filename or '\\' in ts_filename or '..' in ts_filename:
        raise HTTPException(status_code=400, detail='Invalid ts_filename')

    ts_path = os.path.join(bd.path, quality, ts_filename)

    if not os.path.exists(ts_path):
        raise HTTPException(status_code=404, detail=f'{ts_filename} not found at {ts_path}')
    return FileResponse(ts_path, media_type='video/mp2t', headers={'Cache-Control': 'no-store'})

