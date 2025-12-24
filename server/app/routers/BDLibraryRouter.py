import json
import os
from datetime import datetime
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.models.BDLibrary import BDLibrary
from app.models.BDLibraryHistory import BDLibraryHistory
from app.models.BDLibraryMylist import BDLibraryMylist
from app.models.User import User
from app.routers.UsersRouter import GetCurrentAdminUser, GetCurrentUser


# Define Pydantic models for response
class BDLibraryHistoryResponseItem(BaseModel):
    id: str
    bd_id: int
    title: str
    path: str
    watched_at: datetime
    duration: int
    position: int

    class Config:
        from_attributes = True

class BDLibraryMylistResponseItem(BaseModel):
    id: str
    bd_id: int
    title: str
    path: str
    added_at: datetime
    position: int | None = None
    duration: int | None = None

    class Config:
        from_attributes = True

router = APIRouter(
    tags=['BDLibrary'],
    prefix='/api/bd-library',
)


# BDライブラリ検索条件のスキーマ
class BDLibrarySearchCondition(BaseModel):
    keyword: str = ''
    is_case_sensitive: bool = False
    is_fuzzy_search_enabled: bool = False


async def _build_bd_dict(bd: BDLibrary) -> dict:
    """BD情報にトラック情報を追加して辞書を構築する共通処理"""
    available_qualities = []
    audio = []
    subtitle = []
    tracks_path = os.path.join(bd.path, 'tracks.json')
    if os.path.isfile(tracks_path):
        with open(tracks_path, encoding='utf-8') as f:
            tracks = json.load(f)
            available_qualities = tracks.get('available_qualities', [])
            audio = tracks.get('audio', [])
            subtitle = tracks.get('subtitle', [])
    bd_dict = bd.__dict__.copy()
    bd_dict['available_qualities'] = available_qualities
    bd_dict['audio'] = audio
    bd_dict['subtitle'] = subtitle
    return bd_dict


@router.get('/', summary='BDライブラリ一覧取得')
async def list_bd_library():
    bds = await BDLibrary.all()
    bd_list = []
    for bd in bds:
        bd_list.append(await _build_bd_dict(bd))
    return bd_list

@router.post('/search', summary='BDライブラリ検索')
async def search_bd_library(search_condition: BDLibrarySearchCondition):
    """
    BDライブラリを検索する。
    """
    bds = await BDLibrary.all()
    bd_list = []

    for bd in bds:
        # 検索キーワードが空の場合は全てのBDを返す
        if not search_condition.keyword.strip():
            bd_list.append(await _build_bd_dict(bd))
        else:
            # キーワード検索
            keyword = search_condition.keyword.lower()
            title = bd.title.lower()

            if keyword in title:
                bd_list.append(await _build_bd_dict(bd))

    return bd_list

# BDマイリスト関連のエンドポイント（具体的なルートを先に定義）
@router.get('/mylist', summary='BDマイリスト一覧取得', response_model=List[BDLibraryMylistResponseItem])
async def get_bd_mylist(current_user: Annotated[User, Depends(GetCurrentUser)]):
    try:
        # 現在のユーザーのマイリストのみを取得
        mylist_list = await BDLibraryMylist.filter(user_id=current_user.id)

        # Tortoise ORMのモデルから正しくデータを抽出
        result = []
        for mylist in mylist_list:
            # BDライブラリから実際の動画時間を取得
            bd = await BDLibrary.get_or_none(id=mylist.bd_id)
            # 視聴履歴から進捗情報を取得
            history = await BDLibraryHistory.get_or_none(user_id=current_user.id, bd_id=mylist.bd_id)

            mylist_data = BDLibraryMylistResponseItem(
                id=mylist.id,
                bd_id=int(mylist.bd_id),  # 明示的にintに変換
                title=mylist.title,
                path=mylist.path,
                added_at=mylist.added_at,
                position=history.position if history else None,
                duration=bd.duration if bd else None,  # BDライブラリの実際の動画時間を使用
            )
            result.append(mylist_data)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BDLibraryMylistRequest(BaseModel):
    bd_id: int  # 整数として受け取る

@router.post('/mylist', summary='BDマイリスト追加')
async def add_bd_mylist(request: BDLibraryMylistRequest, current_user: Annotated[User, Depends(GetCurrentUser)]):
    try:
        bd_id = request.bd_id  # 既に整数なので変換不要
        bd = await BDLibrary.get_or_none(id=bd_id)
        if not bd:
            raise HTTPException(status_code=404, detail='BD not found')

        # 既存のマイリストを確認（同じユーザーで同じBD）
        existing_mylist = await BDLibraryMylist.get_or_none(user_id=current_user.id, bd_id=bd_id)
        if existing_mylist:
            raise HTTPException(status_code=409, detail='Already in mylist')

        # 新しいマイリストを作成
        mylist_id = f"{current_user.id}_{bd_id}_{int(datetime.now().timestamp() * 1000)}"
        mylist = await BDLibraryMylist.create(
            id=mylist_id,
            user_id=current_user.id,
            bd_id=bd_id,
            title=bd.title,
            path=bd.path,
            added_at=datetime.now()
        )
        return mylist.__dict__
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid bd_id format')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/mylist/{mylist_id}', summary='BDマイリスト削除')
async def remove_bd_mylist(mylist_id: str, current_user: Annotated[User, Depends(GetCurrentUser)]):
    # 現在のユーザーのマイリストのみを削除可能
    mylist = await BDLibraryMylist.get_or_none(id=mylist_id, user_id=current_user.id)
    if not mylist:
        raise HTTPException(status_code=404, detail='Mylist not found')
    await mylist.delete()
    return {'message': 'Mylist deleted'}

@router.delete('/mylist', summary='BDマイリスト全削除')
async def clear_bd_mylist(current_user: Annotated[User, Depends(GetCurrentUser)]):
    # 現在のユーザーのマイリストのみを削除
    await BDLibraryMylist.filter(user_id=current_user.id).delete()
    return {'message': 'All mylist deleted'}

# BD視聴履歴関連のエンドポイント（具体的なルートを先に定義）
@router.get('/history', summary='BD視聴履歴一覧取得', response_model=List[BDLibraryHistoryResponseItem])
async def get_bd_history(current_user: Annotated[User, Depends(GetCurrentUser)]):
    try:
        # 現在のユーザーの視聴履歴のみを取得
        history_list = await BDLibraryHistory.filter(user_id=current_user.id)

        # Tortoise ORMのモデルから正しくデータを抽出
        result = []
        for history in history_list:
            history_data = BDLibraryHistoryResponseItem(
                id=history.id,
                bd_id=int(history.bd_id),
                title=history.title,
                path=history.path,
                position=history.position,
                duration=history.duration,
                watched_at=history.watched_at,
            )
            result.append(history_data)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class BDLibraryHistoryRequest(BaseModel):
    bd_id: int  # 整数として受け取る
    position: int
    duration: int

@router.post('/history', summary='BD視聴履歴追加')
async def add_bd_history(request: BDLibraryHistoryRequest, current_user: Annotated[User, Depends(GetCurrentUser)]):
    try:
        bd_id = request.bd_id  # 既に整数なので変換不要
        bd = await BDLibrary.get_or_none(id=bd_id)
        if not bd:
            raise HTTPException(status_code=404, detail='BD not found')

        # 既存の履歴を確認（同じユーザーで同じBD）
        existing_history = await BDLibraryHistory.get_or_none(user_id=current_user.id, bd_id=bd_id)
        if existing_history:
            # 既存の履歴を更新
            existing_history.position = request.position
            existing_history.duration = request.duration
            existing_history.watched_at = datetime.now()
            await existing_history.save()
            return existing_history.__dict__
        else:
            # 新しい履歴を作成
            history_id = f"{current_user.id}_{bd_id}_{int(datetime.now().timestamp() * 1000)}"
            history = await BDLibraryHistory.create(
                id=history_id,
                user_id=current_user.id,
                bd_id=bd_id,
                title=bd.title,
                path=bd.path,
                position=request.position,
                duration=request.duration,
                watched_at=datetime.now()
            )
            return history.__dict__
    except ValueError:
        raise HTTPException(status_code=422, detail='Invalid bd_id format')
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete('/history/{history_id}', summary='BD視聴履歴削除')
async def remove_bd_history(history_id: str, current_user: Annotated[User, Depends(GetCurrentUser)]):
    # 現在のユーザーの視聴履歴のみを削除可能
    history = await BDLibraryHistory.get_or_none(id=history_id, user_id=current_user.id)
    if not history:
        raise HTTPException(status_code=404, detail='History not found')
    await history.delete()
    return {'message': 'History deleted'}

@router.delete('/history', summary='BD視聴履歴全削除')
async def clear_bd_history(current_user: Annotated[User, Depends(GetCurrentUser)]):
    # 現在のユーザーの視聴履歴のみを削除
    await BDLibraryHistory.filter(user_id=current_user.id).delete()
    return {'message': 'All history deleted'}

# BD個別情報関連のエンドポイント（パラメータ付きルートを後で定義）
@router.get('/{bd_id}', summary='単一BD情報取得')
async def get_bd(bd_id: int):
    bd = await BDLibrary.get_or_none(id=bd_id)
    if not bd:
        raise HTTPException(status_code=404, detail='Not found')
    return await _build_bd_dict(bd)

@router.get('/{bd_id}/chapters', summary='BDライブラリチャプター情報取得')
async def get_bd_chapters(bd_id: int):
    bd = await BDLibrary.get_or_none(id=bd_id)
    if not bd:
        raise HTTPException(status_code=404, detail='Not found')
    # BDのディレクトリ配下のchapters.jsonを探す
    chapters_path = os.path.join(bd.path, 'chapters.json')
    if not os.path.isfile(chapters_path):
        raise HTTPException(status_code=404, detail='chapters.json not found')
    return FileResponse(chapters_path, media_type='application/json')

@router.get('/{bd_id}/thumbnail', summary='BDライブラリサムネイル画像取得')
async def get_bd_thumbnail(bd_id: int):
    bd = await BDLibrary.get_or_none(id=bd_id)
    if not bd:
        raise HTTPException(status_code=404, detail='Not found')
    thumbnail_path = os.path.join(bd.path, 'thumbnail.jpg')
    if not os.path.isfile(thumbnail_path):
        raise HTTPException(status_code=404, detail='thumbnail.jpg not found')
    return FileResponse(thumbnail_path, media_type='image/jpeg')

@router.get('/{bd_id}/tracks', summary='BDライブラリ音声・字幕トラック情報取得')
async def get_bd_tracks(bd_id: int):
    bd = await BDLibrary.get_or_none(id=bd_id)
    if not bd:
        raise HTTPException(status_code=404, detail='Not found')
    tracks_path = os.path.join(bd.path, 'tracks.json')
    if not os.path.isfile(tracks_path):
        raise HTTPException(status_code=404, detail='tracks.json not found')
    return FileResponse(tracks_path, media_type='application/json')

@router.delete('/{bd_id}', summary='BDライブラリ削除')
async def delete_bd(bd_id: int, current_user: Annotated[User, Depends(GetCurrentAdminUser)]):
    """
    指定されたBDライブラリエントリを削除する。
    関連するマイリストエントリと視聴履歴も削除される。
    """
    bd = await BDLibrary.get_or_none(id=bd_id)
    if not bd:
        raise HTTPException(status_code=404, detail='BD not found')

    try:
        # 関連するマイリストエントリを削除（全ユーザー）
        await BDLibraryMylist.filter(bd_id=bd_id).delete()

        # 関連する視聴履歴を削除（全ユーザー）
        await BDLibraryHistory.filter(bd_id=bd_id).delete()

        # BDライブラリエントリを削除
        await bd.delete()

        return {'message': 'BD deleted successfully'}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f'Failed to delete BD: {str(e)}')

