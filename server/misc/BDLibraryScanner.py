import os
import sys
import asyncio
import yaml
import json

# appモジュールにアクセスするためのパスを追加
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from tortoise import Tortoise
from app.models.BDLibrary import BDLibrary
from app.models.BDLibraryMylist import BDLibraryMylist

def load_bd_folders_from_config():
    # プロジェクトルートのconfig.yamlを参照するため、パスを調整
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    config_path = os.path.join(base_dir, 'config.yaml')
    print(f"設定ファイルパス: {config_path}")
    print(f"設定ファイル存在: {os.path.exists(config_path)}")
    if not os.path.exists(config_path):
        config_path = os.path.join(base_dir, 'config.example.yaml')
        print(f"代替設定ファイルパス: {config_path}")
        print(f"代替設定ファイル存在: {os.path.exists(config_path)}")
    with open(config_path, encoding='utf-8') as f:
        config = yaml.safe_load(f)
    print(f"読み込まれた設定: {config}")
    bd_folders = config.get('video', {}).get('bd_library_folders', [])
    print(f"BDライブラリフォルダ: {bd_folders}")
    return bd_folders

async def init_db():
    """データベースを初期化"""
    await Tortoise.init(
        db_url='sqlite://./data/database.sqlite',
        modules={'models': ['app.models']}
    )
    await Tortoise.generate_schemas()

async def check_duration():
    """BDライブラリのdurationフィールドの値を確認"""
    bds = await BDLibrary.all()
    print(f'Total BDs: {len(bds)}')
    for bd in bds[:5]:
        print(f'BD {bd.id}: {bd.title} - duration: {bd.duration}')

async def scan_async(bd_folders: list[str]):
    # 既存の全作品パスを取得
    existing_paths = set([item.path for item in await BDLibrary.all()])
    found_paths = set()

    print(f"BDライブラリフォルダ: {bd_folders}")

    for parent_folder in bd_folders:
        print(f"処理中のフォルダ: {parent_folder}")
        if not os.path.isdir(parent_folder):
            print(f"フォルダが存在しません: {parent_folder}")
            continue
        parent_dirname = os.path.basename(os.path.normpath(parent_folder))
        # 直下のサブディレクトリ（作品ごと）のみを厳密に対象
        print(f"作品ディレクトリを検索中: {parent_folder}")
        for work_dir in os.listdir(parent_folder):
            work_path = os.path.join(parent_folder, work_dir)
            print(f"  検出された項目: {work_dir}")
            if not os.path.isdir(work_path):
                print(f"    ディレクトリではありません: {work_path}")
                continue
            # 親ディレクトリ自身や隠しディレクトリ、親と同名のサブディレクトリは除外
            if work_dir in ('.', '..') or work_path == parent_folder or work_dir == parent_dirname:
                continue
            titles = []
            # サブディレクトリ探索（従来通り）
            for title_dir in os.listdir(work_path):
                title_path = os.path.join(work_path, title_dir)
                if not os.path.isdir(title_path):
                    continue
                m3u8_path = os.path.join(title_path, 'playlist.m3u8')
                chapters_json_path = os.path.join(title_path, 'chapters.json')
                print(f"    ファイル確認: {m3u8_path} (存在: {os.path.exists(m3u8_path)})")
                print(f"    ファイル確認: {chapters_json_path} (存在: {os.path.exists(chapters_json_path)})")
                if os.path.exists(m3u8_path) and os.path.exists(chapters_json_path):
                    with open(chapters_json_path, encoding='utf-8') as f:
                        chapters = json.load(f)
                    titles.append({
                        'name': title_dir,
                        'hls_dir': title_dir,
                        'm3u8_path': m3u8_path,
                        'chapters': chapters,
                    })
            # 直下にplaylist.m3u8がある場合も追加
            m3u8_path = os.path.join(work_path, 'playlist.m3u8')
            chapters_json_path = os.path.join(work_path, 'chapters.json')
            print(f"  直下ファイル確認: {m3u8_path} (存在: {os.path.exists(m3u8_path)})")
            print(f"  直下ファイル確認: {chapters_json_path} (存在: {os.path.exists(chapters_json_path)})")
            if os.path.exists(m3u8_path) and os.path.exists(chapters_json_path):
                with open(chapters_json_path, encoding='utf-8') as f:
                    chapters = json.load(f)
                titles.append({
                    'name': 'original',
                    'hls_dir': '',
                    'm3u8_path': m3u8_path,
                    'chapters': chapters,
                })
            if titles:
                # chapters.jsonから動画時間を取得
                duration = None
                if os.path.exists(chapters_json_path):
                    with open(chapters_json_path, encoding='utf-8') as f:
                        chapters = json.load(f)
                    print(f"    chapters.json内容: {chapters}")
                    # 最後のチャプターの終了時間を動画時間とする
                    if chapters and len(chapters) > 0:
                        last_chapter = chapters[-1]
                        print(f"    最後のチャプター: {last_chapter}")
                        if 'end_time' in last_chapter:
                            duration = int(last_chapter['end_time'])
                        elif 'endTime' in last_chapter:
                            duration = int(last_chapter['endTime'])
                        elif 'EndTime' in last_chapter:
                            duration = int(last_chapter['EndTime'])
                        elif 'duration' in last_chapter:
                            duration = int(last_chapter['duration'])
                        print(f"    取得したduration: {duration}")

                print(f"  BDライブラリに追加: {work_dir} (パス: {work_path}, duration: {duration})")
                await BDLibrary.update_or_create(
                    defaults={
                        'title': work_dir,
                        'titles': titles,
                        'duration': duration,
                    },
                    path=work_path,
                )
                found_paths.add(work_path)
    # DBにあるが実際には存在しないパスのレコードを削除
    for path in existing_paths - found_paths:
        # 削除されるBDのIDを先に取得
        bds_to_delete = await BDLibrary.filter(path=path).all()
        bd_ids_to_delete = [bd.id for bd in bds_to_delete]

        # BDライブラリから削除
        await BDLibrary.filter(path=path).delete()

        # 削除されたBDに対応するマイリストエントリも削除
        for bd_id in bd_ids_to_delete:
            await BDLibraryMylist.filter(bd_id=bd_id).delete()

    # 存在しないBDのマイリストエントリを一括削除
    # 現在存在するBDのIDリストを取得
    existing_bd_ids = set([bd.id for bd in await BDLibrary.all()])

    # マイリストエントリのうち、存在しないBDのIDに対応するものを削除
    all_mylist_items = await BDLibraryMylist.all()
    for mylist_item in all_mylist_items:
        if mylist_item.bd_id not in existing_bd_ids:
            await BDLibraryMylist.filter(id=mylist_item.id).delete()

if __name__ == '__main__':
    async def main():
        # データベースを初期化
        await init_db()

        # まずdurationフィールドの値を確認
        await check_duration()

        # その後、通常のスキャンを実行
        bd_folders = load_bd_folders_from_config()
        await scan_async(bd_folders)

        # データベース接続を閉じる
        await Tortoise.close_connections()

    asyncio.run(main())
