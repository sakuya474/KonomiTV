import discord
from discord.ext import commands
from discord import app_commands
from discord.ui import View, Button, Select
import datetime
from typing import Dict, List, Tuple, Optional

from app import logging
from app.config import Config, SaveConfig

# Botが実行中かどうかを示すグローバル変数
is_bot_running: bool = False

from fastapi import HTTPException
from app.models.Channel import Channel
from app import schemas
from app.models.Program import Program
from app.routers.VideosRouter import VideosAPI
from app.routers.ReservationsRouter import ReservationsAPI, GetCtrlCmdUtil, AddReservationAPI
from app.routers.ProgramsRouter import ProgramSearchAPI

config = Config()

# 日本のタイムゾーンを定数として定義
JST = datetime.timezone(datetime.timedelta(hours=9))

# ボットの初期化
bot = commands.Bot(
    command_prefix='!',
    intents=discord.Intents.default(),
    activity=discord.Game("/helpでコマンド一覧")
)

@bot.event
async def on_ready():
    """起動時に実行されるイベントハンドラ"""
    global is_bot_running
    is_bot_running = True
    if bot.user:
        logging.info(f'[DiscordBot] ✅ Login successful! (User: {bot.user} (ID: {bot.user.id})')
    else:
        logging.info('[DiscordBot] ✅ Login successful! (User info unavailable)')

    # コマンドツリーを同期
    try:
        await bot.tree.sync()
        logging.info('[DiscordBot] 🔄 Slash commands synchronized.')
    except Exception as e:
        logging.error(f'[DiscordBot] Error synchronizing command tree: {e}')

     # 起動時にログチャンネルにメッセージを送信
    if config.discord.notify_server:
        await send_bot_status_message("startup")

@bot.event
async def on_disconnect():
    """切断時に実行されるイベントハンドラ"""
    global is_bot_running
    is_bot_running = False
    logging.info('[DiscordBot] 🔌 Disconnected from Discord.')

async def setup():
    """"ボットの初期設定を行う"""
    # コグの登録
    await bot.add_cog(UtilityCog(bot))
    await bot.add_cog(SettingCog(bot))
    await bot.add_cog(ViewCog(bot))
    await bot.add_cog(MaintenanceCog(bot))

class UtilityCog(commands.Cog):
    """🔧 ユーティリティコマンド集"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="コマンド一覧を表示")
    async def help(self, interaction: discord.Interaction):
        """ヘルプメッセージを表示"""
        try:
            embed = discord.Embed(
                title="📺 KonomiTV Discord Bot コマンド一覧",
                description="利用可能なスラッシュコマンド",
                color=0x00ff00
            )

            # 各コグからコマンド情報を取得
            for cog_name, cog in self.bot.cogs.items():
                cog_commands = []
                # Cog直下のコマンド
                for command in cog.get_app_commands():
                    if isinstance(command, app_commands.Command):
                        cog_commands.append(f"🔹 `/{command.name}` - {command.description}")
                    # グループコマンド
                    elif isinstance(command, app_commands.Group):
                        # サブコマンドのみを追加（グループ自体の説明は除外）
                        for subcommand in command.commands:
                            cog_commands.append(f"🔸 `/{command.name} {subcommand.name}` - {subcommand.description}")

                if cog_commands:
                    # Cogのdocstringを取得（なければCogの名前を使用）
                    cog_description = cog.__doc__ or cog_name
                    embed.add_field(
                        name=f"**{cog_description}**",
                        value="\n".join(cog_commands),
                        inline=False
                    )

            embed.timestamp = datetime.datetime.now(datetime.timezone.utc)

            await interaction.response.send_message(embed=embed)
        except Exception as e:
            logging.error(f'[DiscordBot] Error generating help message: {e}')
            await interaction.response.send_message("❌ ヘルプメッセージの生成中にエラーが発生しました。", ephemeral=True)

    @app_commands.command(name="version", description="バージョン情報")
    async def version(self, interaction: discord.Interaction):
        """KonomiTV のバージョン情報を表示"""
        try:
            # Version API から情報を取得
            from app.routers.VersionRouter import VersionInformationAPI
            version_info = await VersionInformationAPI()

            # バージョン比較
            is_latest = version_info["version"] == version_info["latest_version"]
            version_status = "最新バージョンです。" if is_latest else "⚠️ 更新があります"

        except Exception as e:
            logging.error(f'[DiscordBot] Error getting version info: {e}')
            await interaction.response.send_message("❌ バージョン情報の取得中にエラーが発生しました。", ephemeral=True)
            return

        embed = discord.Embed(
            title="📺 KonomiTV バージョン情報",
            description=f"**{version_status}**",
            color=0x0091ff
        )
        embed.set_image(url="https://user-images.githubusercontent.com/39271166/134050201-8110f076-a939-4b62-8c86-7beaa3d4728c.png")
        embed.add_field(
            name="🔢 現在のバージョン",
            value=f"```{version_info['version']}```",
            inline=True
        )
        if version_info["latest_version"]:
            embed.add_field(
                name="🌐 最新バージョン",
                value=f"```{version_info['latest_version']}```",
                inline=True
            )
        embed.add_field(
            name="💻 環境",
            value=f"```{version_info['environment']}```",
            inline=False
        )
        embed.add_field(
            name="📡 バックエンド",
            value=f"```{version_info['backend']}```",
            inline=True
        )
        embed.add_field(
            name="🎥 エンコーダー",
            value=f"```{version_info['encoder']}```",
            inline=True
        )
        embed.set_footer(text=f"情報取得日時: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
        await interaction.response.send_message(embed=embed)

class ViewCog(commands.Cog):
    """📺 ビューコマンド集"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    view = app_commands.Group(
        name="view",
        description="チャンネル情報などを確認する"
    )

    #チャンネル一覧を表示するサブコマンド
    @view.command(name="channel_list", description="指定タイプのチャンネル一覧を表示 (地デジ(GR), BS, CS)")
    @app_commands.describe(channel_type="表示したいチャンネルタイプ (地デジ(GR), BS, CS)")
    async def channel_list(self, interaction: discord.Interaction,channel_type: str):
        """チャンネル一覧を表示"""
        await interaction.response.defer(ephemeral=True)
        try:
            #チャンネルタイプが正しいかをフィルタ
            if channel_type in ['GR', 'BS', 'CS', 'all']:
                if channel_type == 'all':
                    channel_types_to_fetch = ['GR', 'BS', 'CS']
                else:
                    channel_types_to_fetch = [channel_type]
                channels_data = await get_specific_channels(channel_types_to_fetch)
            else:
                await interaction.followup.send("チャンネルタイプが正しくありません。GR、BS、CS、またはallを指定してください。", ephemeral=True)
                return

            embed = discord.Embed(
                title="チャンネル一覧 (GR, BS, CS)",
                color=0x0091ff
            )

            for ch_type in channel_types_to_fetch:
                channel_list = channels_data.get(ch_type, [])
                if channel_list:
                    # チャンネルリストを整形 (ID: 名前)
                    value_str = "\n".join([f"`{ch_id}`: {ch_name}" for ch_id, ch_name in channel_list[:25]])
                    embed.add_field(name=f"📺 {ch_type}", value=value_str, inline=False)
                else:
                    # チャンネルが見つからない場合
                    embed.add_field(name=f"📺 {ch_type}", value="チャンネルが見つかりません。", inline=False)
            # タイムスタンプを追加
            embed.set_footer(text=datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logging.error(f'[DiscordBot] Error getting channel list: {e}')
            await interaction.followup.send(f"❌ チャンネル一覧の取得中にエラーが発生しました。\nエラー詳細: {e}", ephemeral=True)

    @view.command(name="channel_now", description="指定されたチャンネルの現在と次の番組情報を表示")
    @app_commands.describe(channel_id="表示したいチャンネルのID (例: gr011)")
    async def channel_now(self, interaction: discord.Interaction, channel_id: str):
        """指定されたチャンネルの現在の番組情報を表示"""
        try:
            channel_instance = await Channel.get_or_none(display_channel_id=channel_id)

            # channelIDが得られなかった場合
            if not channel_instance:
                await interaction.response.send_message(f"❌ チャンネルID '{channel_id}' が見つかりません。", ephemeral=True)
                return

            # Channel インスタンスから現在の番組と次の番組を取得
            program_present, program_following = await channel_instance.getCurrentAndNextProgram()

            embed = discord.Embed(
                title=f"{channel_instance.name} ({channel_instance.display_channel_id}) の現在の番組情報",
                color=0x0091ff
            )

             # 共通関数を使用して番組情報をフォーマット
            embed.add_field(
                name="📺 現在の番組",
                value=format_program_info(program_present),
                inline=False
            )

            embed.add_field(
                name="▶️ 次の番組",
                value=format_program_info(program_following),
                inline=False
            )
            embed.set_footer(text=datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
            await interaction.response.send_message(embed=embed)

        except Exception as e:
            logging.error(f'[DiscordBot] Error getting channel info for {channel_id}: {e}')
            await interaction.response.send_message(f"❌ チャンネル情報の取得中にエラーが発生しました。\n{e}", ephemeral=True)

    @view.command(name="recorded_info", description="録画済み番組一覧を表示")
    @app_commands.describe(page="表示したいページ番号 (デフォルト: 1)")
    async def recorded_info(self, interaction: discord.Interaction, page: int = 1):
        """録画済み番組一覧を表示"""
        await interaction.response.defer()
        try:
            # 不正なページ番号をチェック
            if page < 1:
                await interaction.followup.send("❌ ページ番号は1以上を指定してください。", ephemeral=True)
                return

            # VideosAPI を呼び出して録画番組リストを取得
            # VideosAPI は schemas.RecordedPrograms を返す
            recorded_programs_data: schemas.RecordedPrograms = await VideosAPI(order='desc', page=page)

            if not recorded_programs_data.recorded_programs:
                await interaction.followup.send(f"❌ 録画番組が見つかりません。(ページ: {page})", ephemeral=True)
                return

            # 1ページあたりの録画番組数
            items_per_page = 10
            total_items = recorded_programs_data.total
            total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1

            # 現在のページが総ページ数を超えている場合
            if page > total_pages and total_items > 0:
                await interaction.followup.send(f"❌ 指定されたページ番号（{page}）は総ページ数（{total_pages}）を超えています。", ephemeral=True)
                return

             # Embed を作成
            embed = discord.Embed(
                title=f"録画済み番組一覧 (ページ {page})",
                color=0x0091ff
            )
            # 現在のページに表示する番組を取得
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_page_programs = recorded_programs_data.recorded_programs[start_index:end_index]

            for i, recorded in enumerate(current_page_programs, start_index + 1):
                start_time_jst = recorded.start_time.astimezone(JST)
                end_time_jst = recorded.end_time.astimezone(JST)

                embed.add_field(
                    name=f"🔵録画 {i}: {recorded.title}",
                    value=(
                        f"チャンネル: {recorded.channel.name if recorded.channel else 'なし'}\n"
                        f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                    ),
                    inline=False
                )

            # ページ情報とタイムスタンプ
            embed.set_footer(text=f"ページ {page} / {total_pages}・全 {total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

            # View (ボタン) を作成
            view = RecordedProgramsView(recorded_programs_data, page, total_pages, total_items, items_per_page)

            # メッセージを送信
            await interaction.followup.send(embed=embed, view=view)

        except HTTPException as e:
            # FastAPI の HTTPException
            error_detail = getattr(e, 'detail', str(e))
            logging.error(f'[DiscordBot] Error getting recorded list (page {page}): {error_detail}')
            await interaction.followup.send(f"❌ 録画番組一覧の取得中にHTTPエラーが発生しました。\n詳細: {error_detail}", ephemeral=True)
        except Exception as e:
            # その他の予期せぬエラー
            logging.error(f'[DiscordBot] Error getting recorded list (page {page}): {e}')
            await interaction.followup.send(f"❌ 録画番組一覧の取得中に予期せぬエラーが発生しました。\nエラー詳細: {e}", ephemeral=True)

    @view.command(name="search_programs", description="番組検索を実行")
    @app_commands.describe(keyword="検索キーワード (番組名の一部を入力)")
    async def search_programs(self, interaction: discord.Interaction, keyword: str):
        """番組検索を実行"""
        await interaction.response.defer()
        try:
            # キーワードが空の場合はエラー
            if not keyword.strip():
                await interaction.followup.send("❌ 検索キーワードを入力してください。", ephemeral=True)
                return

            # 番組検索条件を構築
            search_condition = schemas.ProgramSearchCondition(
                keyword=keyword.strip(),
                is_title_only=True,  # 番組名のみ検索
                is_fuzzy_search_enabled=True,  # あいまい検索を有効
            )

            # EDCB バックエンドが有効かどうかを確認
            edcb = GetCtrlCmdUtil()

            # 番組検索を実行
            search_results: schemas.Programs = await ProgramSearchAPI(search_condition, edcb)

            if not search_results.programs:
                await interaction.followup.send(f"❌ 「{keyword}」に一致する番組が見つかりませんでした。", ephemeral=True)
                return

            # 現時刻を取得（JST）
            current_time = datetime.datetime.now(JST)

            # 過去の番組（終了時刻が現時刻より前）を除外
            future_programs = []
            for program in search_results.programs:
                program_end_time = program.end_time.astimezone(JST)
                if program_end_time > current_time:
                    future_programs.append(program)

            # フィルタリング後に番組がない場合
            if not future_programs:
                await interaction.followup.send(f"❌ 「{keyword}」に一致する放送予定の番組が見つかりませんでした。", ephemeral=True)
                return

            # フィルタリング後の番組リストに更新
            search_results.programs = future_programs
            search_results.total = len(future_programs)

            # 1ページあたりの番組数
            items_per_page = 10
            total_items = search_results.total
            total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1

            # 現在のページ（1ページ目）に表示する番組を取得
            page = 1
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_page_programs = search_results.programs[start_index:end_index]

            embed = discord.Embed(
                title=f"📺 番組検索結果: 「{keyword}」",
                description=f"検索結果: {len(current_page_programs)} / {search_results.total} 件",
                color=0x0091ff
            )

            # 各番組を個別のフィールドとして追加
            for i, program in enumerate(current_page_programs, start_index + 1):
                start_time_jst = program.start_time.astimezone(JST)
                end_time_jst = program.end_time.astimezone(JST)

                # チャンネル情報を取得
                channel = await Channel.get_or_none(id=program.channel_id)
                channel_name = channel.name if channel else '不明'

                # 番組情報をフィールドとして追加
                embed.add_field(
                    name=f"🎬 {i}: {program.title}",
                    value=(
                        f"チャンネル: {channel_name}\n"
                        f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                        f"概要: {program.description[:100]}{'...' if len(program.description) > 100 else ''}"
                    ),
                    inline=False
                )

            # ページ情報とタイムスタンプを追加
            embed.set_footer(text=f"ページ {page} / {total_pages}・全 {total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

            # View (ページネーションボタン) を作成
            view = ProgramSearchResultView(search_results.programs, keyword, page, total_pages, total_items, items_per_page)

            # メッセージを送信
            await interaction.followup.send(embed=embed, view=view)

        except HTTPException as e:
            error_detail = getattr(e, 'detail', str(e))
            logging.error(f'[DiscordBot] Error searching programs with keyword "{keyword}": {error_detail}')
            await interaction.followup.send(f"❌ 番組検索中にHTTPエラーが発生しました。\n詳細: {error_detail}", ephemeral=True)
        except Exception as e:
            logging.error(f'[DiscordBot] Error searching programs with keyword "{keyword}": {e}')
            await interaction.followup.send(f"❌ 番組検索中に予期せぬエラーが発生しました。\nエラー詳細: {e}", ephemeral=True)

    @view.command(name="reservation_list", description="録画予約一覧を表示")
    @app_commands.describe(page="表示したいページ番号 (デフォルト: 1)")
    async def reservation_list(self, interaction: discord.Interaction, page: int = 1):
        """録画予約一覧を表示"""
        await interaction.response.defer()
        try:
            # 不正なページ番号をチェック
            if page < 1:
                await interaction.followup.send("❌ ページ番号は1以上を指定してください。", ephemeral=True)
                return

            # EDCB バックエンドが有効かどうかを確認
            edcb = GetCtrlCmdUtil()

            # ReservationsAPI を呼び出して予約情報を取得
            reservations_data: schemas.Reservations = await ReservationsAPI(edcb)

            if not reservations_data.reservations:
                await interaction.followup.send("❌ 録画予約が見つかりません。", ephemeral=True)
                return

            # 1ページあたりの予約件数
            items_per_page = 10
            total_items = len(reservations_data.reservations)
            total_pages = (total_items + items_per_page - 1) // items_per_page if items_per_page > 0 else 1

            # 現在のページが総ページ数を超えている場合
            if page > total_pages and total_items > 0:
                await interaction.followup.send(f"❌ 指定されたページ番号（{page}）は総ページ数（{total_pages}）を超えています。", ephemeral=True)
                return

            # 現在のページに表示する予約を取得
            start_index = (page - 1) * items_per_page
            end_index = start_index + items_per_page
            current_page_reservations = reservations_data.reservations[start_index:end_index]

            # Embed を作成
            embed = discord.Embed(
                title=f"録画予約一覧 (ページ {page})",
                color=0x0091ff
            )

            # 各予約を個別のフィールドとして追加
            for i, reservation in enumerate(current_page_reservations, start_index + 1):
                start_time_jst = reservation.program.start_time.astimezone(JST)
                end_time_jst = reservation.program.end_time.astimezone(JST)

                # 予約状況を表す絵文字とテキスト
                if not reservation.record_settings.is_enabled:
                    status_emoji = "⚪"  # 予約無効
                    status_text = "予約無効"
                elif reservation.recording_availability == "Unavailable":
                    status_emoji = "🔴"  # 録画不可
                    status_text = "録画不可"
                elif reservation.recording_availability == "Partial":
                    status_emoji = "🟠"  # 一部録画不可
                    status_text = "一部録画不可"
                elif reservation.is_recording_in_progress:
                    status_emoji = "🔵"  # 録画中
                    status_text = "録画中"
                else:
                    status_emoji = "🟡"  # 録画予定
                    status_text = "録画予定"

                # チャンネル情報と番組情報をフィールドとして追加
                embed.add_field(
                    name=f"{status_emoji} 予約 {i}: {reservation.program.title}",
                    value=(
                        f"チャンネル: {reservation.channel.name}\n"
                        f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                        f"録画状況: {status_text}"
                    ),
                    inline=False
                )

            # ページ情報とタイムスタンプ
            embed.set_footer(text=f"ページ {page} / {total_pages}・全 {total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

            # Viewを作成
            view = ReservationListView(reservations_data, page, total_pages, total_items, items_per_page)

            await interaction.followup.send(embed=embed, view=view)

        except HTTPException as e:
            # FastAPI の HTTPException
            error_detail = getattr(e, 'detail', str(e))
            logging.error(f'[DiscordBot] Error getting reservation list: {error_detail}')
            await interaction.followup.send(f"❌ 録画予約一覧の取得中にHTTPエラーが発生しました。\n詳細: {error_detail}", ephemeral=True)
        except Exception as e:
            # その他の予期せぬエラー
            logging.error(f'[DiscordBot] Error getting reservation list: {e}')
            await interaction.followup.send(f"❌ 録画予約一覧の取得中に予期せぬエラーが発生しました。\nエラー詳細: {e}", ephemeral=True)

class MaintenanceCog(commands.Cog):
    """🛠️ メンテナンスコマンド集"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot
    maintenance = app_commands.Group(
        name="maintenance",
        description="メンテナンス関連のコマンド"
    )

    @maintenance.command(name="restart", description="サーバーを再起動する")
    async def restart(self, interaction: discord.Interaction):
        """サーバーを再起動する"""
        try:
            # 許可されているか確認
            if not await self.is_allowed(interaction.user):
                await interaction.response.send_message("❌ 許可されていないユーザーです。", ephemeral=True)
                return

            # 再起動処理
            await interaction.response.send_message("🔄 サーバーを再起動しています...1分ほどお待ち下さい。", ephemeral=True)
            from app.routers.MaintenanceRouter import ServerRestartAPI
            ServerRestartAPI(None)  # current_user は None でOK (ローカルアクセス)
        except Exception as e:
            logging.error(f'[DiscordBot] Error processing restart command: {e}')
            # エラーメッセージを送信 (すでにresponseが使われている場合はfollowup)
            try:
                await interaction.response.send_message("❌ コマンドの実行中にエラーが発生しました。", ephemeral=True)
            except:
                await interaction.followup.send("❌ コマンドの実行中にエラーが発生しました。", ephemeral=True)

    @maintenance.command(name="shutdown", description="サーバーを終了する")
    async def shutdown(self, interaction: discord.Interaction):
        """サーバーを終了する"""
        try:
            # 許可されているか確認
            if not await self.is_allowed(interaction.user):
                await interaction.response.send_message("❌ 許可されていないユーザーです。", ephemeral=True)
                return

            # 終了処理
            await interaction.response.send_message("🛑 サーバーを終了しています...", ephemeral=True)
            from app.routers.MaintenanceRouter import ServerShutdownAPI
            ServerShutdownAPI(None)  # current_user は None でOK (ローカルアクセス)
        except Exception as e:
            logging.error(f'[DiscordBot] Error processing shutdown command: {e}')
            # エラーメッセージを送信 (すでにresponseが使われている場合はfollowup)
            try:
                await interaction.response.send_message("❌ コマンドの実行中にエラーが発生しました。", ephemeral=True)
            except:
                await interaction.followup.send("❌ コマンドの実行中にエラーが発生しました。", ephemeral=True)

    @maintenance.command(name="epg_acquire", description="EPG 獲得を開始する")
    async def epg_acquire(self, interaction: discord.Interaction):
        """EPG 獲得を開始する"""
        try:
            # 許可されているか確認
            if not await self.is_allowed(interaction.user):
                await interaction.response.send_message("❌ 許可されていないユーザーです。", ephemeral=True)
                return

            # バックエンドが EDCB かチェック
            if config.general.backend != 'EDCB':
                await interaction.response.send_message("❌ このコマンドは EDCB バックエンドでのみ利用可能です。", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)

            # EDCB の CtrlCmdUtil を取得
            from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
            edcb = CtrlCmdUtil()

            # EPG 獲得を開始
            result = await edcb.sendEpgCapNow()

            if result:
                # 成功時のメッセージ
                embed = discord.Embed(
                    title="✅ EPG 獲得開始",
                    description="EDCB での EPG 獲得処理を開始しました。",
                    color=0x00ff00
                )
                embed.set_footer(text=f"実行時間: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logging.info('[DiscordBot] EPG acquisition started successfully')
            else:
                embed = discord.Embed(
                    title="❌ EPG 獲得開始失敗",
                    description="EDCB での EPG 獲得処理の開始に失敗しました。",
                    color=0xff0000
                )
                embed.set_footer(text=f"実行時間: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logging.error('[DiscordBot] Failed to start EPG acquisition')

        except Exception as e:
            logging.error(f'[DiscordBot] Error processing epg_acquire command: {e}')
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ EPG 獲得コマンドの実行中にエラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ EPG 獲得コマンドの実行中にエラーが発生しました。", ephemeral=True)
            except:
                logging.error('[DiscordBot] Failed to send error message to Discord')

    async def is_allowed(self, user: discord.User) -> bool:
        """ユーザーが許可されているかを確認する"""
        try:
            # config.discord.maintenance_user_ids にユーザーIDが含まれているか確認
            if hasattr(user, 'id') and str(user.id) in config.discord.maintenance_user_ids:
                logging.debug(f'[DiscordBot] User {user.id} is allowed to use maintenance commands.')
                return True
            else:
                logging.debug(f'[DiscordBot] User {user.id} is not allowed to use maintenance commands.')
                return False
        except Exception as e:
            logging.error(f'[DiscordBot] Error checking user permissions: {e}')
            return False

    @maintenance.command(name="epg_reload", description="EPG を再読み込みする")
    async def epg_reload(self, interaction: discord.Interaction):
        """EPG を再読み込みする"""
        try:
            # 許可されているか確認
            if not await self.is_allowed(interaction.user):
                await interaction.response.send_message("❌ 許可されていないユーザーです。", ephemeral=True)
                return

            # バックエンドが EDCB かチェック
            if config.general.backend != 'EDCB':
                await interaction.response.send_message("❌ このコマンドは EDCB バックエンドでのみ利用可能です。", ephemeral=True)
                return
            await interaction.response.defer(ephemeral=True)

            # EDCB の CtrlCmdUtil を取得
            from app.utils.edcb.CtrlCmdUtil import CtrlCmdUtil
            edcb = CtrlCmdUtil()

            # EPG 再読み込みを開始する
            result = await edcb.sendReloadEpg()

            if result:
                # 成功時のメッセージ
                embed = discord.Embed(
                    title="✅ EPG 再読み込み開始",
                    description="EDCB での EPG 再読み込みを開始しました。",
                    color=0x00ff00
                )
                embed.set_footer(text=f"実行時間: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logging.info('[DiscordBot] EPG reload started successfully')
            else:
                embed = discord.Embed(
                    title="❌ EPG 再読み込み開始失敗",
                    description="EDCB での EPG 再読み込み処理の開始に失敗しました。",
                    color=0xff0000
                )
                embed.set_footer(text=f"実行時間: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")
                await interaction.followup.send(embed=embed, ephemeral=True)
                logging.error('[DiscordBot] Failed to start EPG reload')

        except Exception as e:
            logging.error(f'[DiscordBot] Error processing epg_reload command: {e}')
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("❌ EPG 再読み込みコマンドの実行中にエラーが発生しました。", ephemeral=True)
                else:
                    await interaction.followup.send("❌ EPG 再読み込みコマンドの実行中にエラーが発生しました。", ephemeral=True)
            except:
                logging.error('[DiscordBot] Failed to send error message to Discord')

    async def is_allowed(self, user: discord.User) -> bool:
        """ユーザーが許可されているかを確認する"""
        try:
            # config.discord.maintenance_user_ids にユーザーIDが含まれているか確認
            if hasattr(user, 'id') and str(user.id) in config.discord.maintenance_user_ids:
                logging.debug(f'[DiscordBot] User {user.id} is allowed to use maintenance commands.')
                return True
            else:
                logging.debug(f'[DiscordBot] User {user.id} is not allowed to use maintenance commands.')
                return False
        except Exception as e:
            logging.error(f'[DiscordBot] Error checking user permissions: {e}')
            return False

class SettingCog(commands.Cog):
    """⚙️ 設定コマンド集"""
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    #settingコマンドグループを定義
    setting = app_commands.Group(
        name="setting",
        description="各種設定を行う"
    )

    #通知チャンネルの設定をするサブコマンド
    @setting.command(name="channel", description="通知チャンネルを設定")
    async def channel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """通知チャンネルを設定"""
        try:
            #引数からチャンネルIDを変更
            config.discord.channel_id = channel.id

            # 設定ファイルを保存
            SaveConfig(config)

            await interaction.response.send_message(
                f"✅通知チャンネルを{channel.mention}に設定しました。",
                ephemeral=True
            )
            logging.info(f'[DiscordBot] Notification channel set to {channel.name} (ID: {channel.id})')

        #エラー時の処理
        except Exception as e:
            logging.error(f'[DiscordBot] Error setting notification channel: {e}')
            await interaction.response.send_message(
                f'❌通知チャンネルの設定に失敗しました。',
                  ephemeral=True
            )

    #予約通知の有効/無効を切り替えるサブコマンド
    @setting.command(name="notify", description="予約通知の有効/無効を切り替え")
    async def notify(self, interaction: discord.Interaction, enabled: bool):
        """予約通知の有効/無効を切り替え"""
        try:
            #設定を変更
            config.discord.notify_recording = enabled

            # 設定ファイルを保存
            SaveConfig(config)

            # メッセージを送信
            status_text = "有効" if enabled else "無効"
            await interaction.response.send_message(
                f"✅予約通知を{status_text}にしました。",
                ephemeral=True
            )
            logging.info(f'[DiscordBot] Reservation notifications set to {status_text}')

        #エラー時の処理
        except Exception as e:
            logging.error(f'[DiscordBot] Error setting reservation notifications: {e}')
            await interaction.response.send_message(
                f'❌予約通知の設定に失敗しました。',
                  ephemeral=True
            )

async def start_discord_bot():
    """Discord ボットを起動する"""

    # Discord トークンが設定されているか確認
    if not config.discord.enabled or not config.discord.token:
        logging.info("[Discord Bot] Discord Bot is disabled or token is not configured. Aborting startup.")
        return # トークンがなければ起動しない

    try:
        # コグの登録など、ボット起動前の非同期セットアップ
        await setup()
        # ボットを非同期で起動
        logging.info("Discord Bot starting...")
        await bot.start(config.discord.token)

    #ログインに失敗した際の処理
    except discord.LoginFailure:
        logging.error("[Discord Bot] Discord Bot login failed, please check the token setting in Config.yaml.")
    #内部エラーが発生した際の処理
    except Exception as e:
        logging.error(f"[Discord Bot] An internal error occurred. Error details: {e}")

async def stop_discord_bot():
    """Discord ボットを停止する"""
    global is_bot_running
    try:
        # 停止メッセージを送信
        if config.discord.notify_server:
            await send_bot_status_message("shutdown")
        # ボットを停止
        await bot.close()
        is_bot_running = False
        logging.info("[DiscordBot] Discord Bot stopped successfully.")
    except Exception as e:
        logging.error(f"[Discord Bot] An internal error occurred while stopping the bot. Error details: {e}")


# 通知済みの予約IDを保持するセット（開始時刻、終了時刻）
notified_reservations_start = set()
notified_reservations_end = set()

async def send_bot_status_message(status:str):
    """ボットの状態を通知チャンネルに送信する共通関数"""
    try:
        channel_id = config.discord.channel_id

        if not channel_id:
            return

        channel = await bot.fetch_channel(int(channel_id))
        # チャンネルが存在しているかを確認
        if channel and isinstance(channel, discord.TextChannel):
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            embed = discord.Embed(colour=0x0091ff)

            if status == "startup":
                embed.set_author(name="🟢KonomiTVが起動しました")
            elif status == "shutdown":
                embed.set_author(name="🛑KonomiTVが終了しました")

            embed.set_footer(text=time)
            await channel.send(embed=embed)
            logging.info(f'[DiscordBot] Sent {status} message to #{channel.name} (ID: {channel.id})')
        elif channel:
            # テキストチャンネル以外が見つかった場合
            logging.warning(f'[DiscordBot] Configured notification channel (ID: {channel_id}) is not a TextChannel.')
        else:
            # チャンネルが見つからなかった場合
            logging.warning(f'[DiscordBot] Notification channel (ID: {channel_id}) not found.')
    except Exception as e:
        logging.error(f'[DiscordBot] Error sending {status} message: {e}')

async def send_reservation_notification(reservation: schemas.Reservation, notification_type: str):
    """予約開始時または終了時の通知を送信する関数"""
    try:
        channel_id = config.discord.channel_id

        if not channel_id:
            return

        channel = await bot.fetch_channel(int(channel_id))
        # チャンネルが存在しているかを確認
        if channel and isinstance(channel, discord.TextChannel):
            time = datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S")
            embed = discord.Embed(colour=0x0091ff)

            start_time_jst = reservation.program.start_time.astimezone(JST)
            end_time_jst = reservation.program.end_time.astimezone(JST)

            if notification_type == "start":
                embed.set_author(name=f"📺 録画予約開始: {reservation.program.title}")
                embed.description = f"チャンネル: {reservation.channel.name}\n" \
                                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}"
                embed.set_footer(text=f"予約ID: {reservation.id} | {time}")
            elif notification_type == "end":
                embed.set_author(name=f"✅ 録画予約終了: {reservation.program.title}")
                embed.description = f"チャンネル: {reservation.channel.name}\n" \
                                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}"
                embed.set_footer(text=f"予約ID: {reservation.id} | {time}")

            await channel.send(embed=embed)
            logging.info(f'[ReservationNotification] Sent {notification_type} notification for reservation ID {reservation.id} to #{channel.name} (ID: {channel.id})')
        elif channel:
            # テキストチャンネル以外が見つかった場合
            logging.warning(f'[DiscordBot] Configured notification channel (ID: {channel_id}) is not a TextChannel.')
        else:
            # チャンネルが見つからなかった場合
            logging.warning(f'[DiscordBot] Notification channel (ID: {channel_id}) not found.')
    except Exception as e:
        logging.error(f'[DiscordBot] Error sending {notification_type} notification for reservation ID {reservation.id}: {e}')

def format_program_info(program: Optional[Program]):
    """番組情報をフォーマットする"""
    if not program:
        return "情報なし"
    try:
        start_time_jst = program.start_time.astimezone(JST)
        end_time_jst = program.end_time.astimezone(JST)

        return (f"**{program.title}**\n" \
                f"{start_time_jst.strftime('%H:%M')} - {end_time_jst.strftime('%H:%M')}\n" \
                f"{program.description or '詳細情報なし'}")
    except Exception as e:
        logging.error(f'[DiscordBot] Error formatting program info: {e}')
        return "番組情報のフォーマット中にエラーが発生しました"

# チャンネル情報取得
async def get_specific_channels(channel_types: List[str] = ['GR', 'BS', 'CS']) -> Dict[str, List[Tuple[str, str]]]:
    """
    指定されたチャンネルタイプのチャンネルID(display_channel_id)と名前のリストを取得する。
    """
    channels_data: Dict[str, List[Tuple[str, str]]] = {ch_type: [] for ch_type in channel_types}
    try:
        # 視聴可能なチャンネルをデータベースから取得 (タイプ、チャンネル番号、リモコンID順)
        all_channels = await Channel.filter(is_watchable=True).order_by('type', 'channel_number', 'remocon_id')
        # 指定されたチャンネルタイプでフィルタリングし、IDと名前を抽出
        for channel in all_channels:
            if channel.type in channel_types:
                # display_channel_id と name をタプルで追加
                channels_data[channel.type].append((channel.display_channel_id, channel.name))
    except Exception as e:
        logging.error(f"[DiscordBot] Error fetching channel data: {e}")
        # エラー発生時は空の辞書を返す
        return {ch_type: [] for ch_type in channel_types}
    return channels_data

class RecordedProgramsView(View):
    """録画番組一覧表示用のViewクラス"""
    def __init__(self, recorded_programs_data: schemas.RecordedPrograms, page: int, total_pages: int, total_items: int, items_per_page: int):
        super().__init__(timeout=60)  # 60秒でタイムアウト
        self.recorded_programs_data = recorded_programs_data
        self.page = page
        self.total_pages = total_pages
        self.total_items = total_items
        self.items_per_page = items_per_page

        # 前のページボタンを追加（1ページ目でない場合）
        if page > 1:
            previous_button = Button(label="前のページ", style=discord.ButtonStyle.secondary, custom_id="previous_page")
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # 次のページボタンを追加（最後のページでない場合）
        if page < total_pages:
            next_button = Button(label="次のページ", style=discord.ButtonStyle.primary, custom_id="next_page")
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        """前のページを表示する"""
        # 前のページ番号を計算
        previous_page = self.page - 1

        # ページ番号が1未満にならないようにする
        if previous_page < 1:
            await interaction.response.send_message("❌ ページ番号が不正です。", ephemeral=True)
            return

        # 現在のページに表示する予約を取得
        start_index = (previous_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_recorded = self.recorded_programs_data.recorded_programs[start_index:end_index]

        embed = discord.Embed(
            title=f"録画済み番組一覧 (ページ {previous_page})",
            color=0x0091ff
        )

        for i, recorded in enumerate(current_page_recorded, start_index + 1):
            start_time_jst = recorded.start_time.astimezone(JST)
            end_time_jst = recorded.end_time.astimezone(JST)

            # チャンネル情報と番組情報をフィールドとして追加
            embed.add_field(
                name=f"🔵録画 {i}: {recorded.title}",
                value=(
                    f"チャンネル: {recorded.channel.name if recorded.channel else 'なし'}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプ
        embed.set_footer(text=f"ページ {previous_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいView（ボタン）を作成
        view = RecordedProgramsView(self.recorded_programs_data, previous_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(self, interaction: discord.Interaction):
        """次のページを表示する"""
        # 次のページ番号を計算
        next_page = self.page + 1

        # 現在のページが総ページ数を超えている場合
        if next_page > self.total_pages and self.total_items > 0:
            await interaction.response.send_message("❌ 指定されたページ番号は総ページ数を超えています。", ephemeral=True)
            return

        # 現在のページに表示する予約を取得
        start_index = (next_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_recorded = self.recorded_programs_data.recorded_programs[start_index:end_index]

        embed = discord.Embed(
            title=f"録画済み番組一覧 (ページ {next_page})",
            color=0x0091ff
        )

        for i, recorded in enumerate(current_page_recorded, start_index + 1):
            start_time_jst = recorded.start_time.astimezone(JST)
            end_time_jst = recorded.end_time.astimezone(JST)

            # チャンネル情報と番組情報をフィールドとして追加
            embed.add_field(
                name=f"🔵録画 {i}: {recorded.title}",
                value=(
                    f"チャンネル: {recorded.channel.name if recorded.channel else 'なし'}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプ
        embed.set_footer(text=f"ページ {next_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいView（ボタン）を作成
        view = RecordedProgramsView(self.recorded_programs_data, next_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)

class ProgramSelectMenu(Select):
    """番組選択用のSelectMenuクラス"""
    def __init__(self, programs: List[schemas.Program], start_index: int):
        # 番組をオプションとして追加（最大25件まで）
        options = []
        for i, program in enumerate(programs[:25], start_index + 1):
            # チャンネル情報を取得
            start_time_jst = program.start_time.astimezone(JST)

            # オプションを作成
            option_label = f"{i}: {program.title}"
            if len(option_label) > 100:  # Discord の制限
                option_label = f"{i}: {program.title[:95]}..."

            option_description = f"{start_time_jst.strftime('%m/%d %H:%M')}"
            if len(option_description) > 100:  # Discord の制限
                option_description = option_description[:97] + "..."

            options.append(discord.SelectOption(
                label=option_label,
                value=str(i - start_index - 1),  # インデックス（0ベース）
                description=option_description
            ))

        super().__init__(
            placeholder="📹 録画したい番組を選択してください",
            options=options,
            custom_id="program_select"
        )
        self.programs = programs
        self.start_index = start_index

    async def callback(self, interaction: discord.Interaction):
        """選択された番組を録画予約に追加"""
        await interaction.response.defer(ephemeral=True)
        try:
            # 選択された番組のインデックスを取得
            selected_index = int(self.values[0])
            selected_program = self.programs[selected_index]

            # EDCB バックエンドが有効かどうかを確認
            edcb = GetCtrlCmdUtil()

            # デフォルトの録画設定を作成
            record_settings = schemas.RecordSettings(
                is_enabled=True,
                priority=3,
                recording_folders=[],  # デフォルトフォルダを使用
                recording_start_margin=None,  # デフォルト設定に従う
                recording_end_margin=None,  # デフォルト設定に従う
                recording_mode='SpecifiedService',
                caption_recording_mode='Default',
                data_broadcasting_recording_mode='Default',
                post_recording_mode='Default',
                post_recording_bat_file_path=None,
                is_event_relay_follow_enabled=True,
                is_exact_recording_enabled=False,
                is_oneseg_separate_output_enabled=False,
                is_sequential_recording_in_single_file_enabled=False,
                forced_tuner_id=None,
            )

            # 録画予約リクエストを作成
            reservation_request = schemas.ReservationAddRequest(
                program_id=selected_program.id,
                record_settings=record_settings,
            )

            # 録画予約を追加
            await AddReservationAPI(reservation_request, edcb)

            # 成功メッセージを送信
            start_time_jst = selected_program.start_time.astimezone(JST)
            end_time_jst = selected_program.end_time.astimezone(JST)

            # チャンネル情報を取得
            channel = await Channel.get_or_none(id=selected_program.channel_id)
            channel_name = channel.name if channel else '不明'

            success_embed = discord.Embed(
                title="✅ 録画予約が追加されました",
                color=0x00ff00
            )
            success_embed.add_field(
                name="番組名",
                value=selected_program.title,
                inline=False
            )
            success_embed.add_field(
                name="チャンネル",
                value=channel_name,
                inline=True
            )
            success_embed.add_field(
                name="放送時間",
                value=f"{start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}",
                inline=True
            )
            success_embed.set_footer(text=f"予約追加時間: {datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

            await interaction.followup.send(embed=success_embed, ephemeral=True)
            logging.info(f'[DiscordBot] Successfully added recording reservation for program: {selected_program.title} (ID: {selected_program.id})')

        except HTTPException as e:
            error_detail = getattr(e, 'detail', str(e))
            logging.error(f'[DiscordBot] Error adding recording reservation for program {selected_program.id}: {error_detail}')

            # エラーの種類によってメッセージを変更
            if 'already reserved' in error_detail:
                await interaction.followup.send("❌ この番組は既に録画予約済みです。", ephemeral=True)
            elif 'not found' in error_detail:
                await interaction.followup.send("❌ 指定された番組またはチャンネルが見つかりません。", ephemeral=True)
            else:
                await interaction.followup.send(f"❌ 録画予約の追加中にエラーが発生しました。\n詳細: {error_detail}", ephemeral=True)
        except Exception as e:
            logging.error(f'[DiscordBot] Error adding recording reservation for program {selected_program.id}: {e}')
            await interaction.followup.send(f"❌ 録画予約の追加中に予期せぬエラーが発生しました。\nエラー詳細: {e}", ephemeral=True)

class ProgramSearchResultView(View):
    """番組検索結果表示用のViewクラス"""
    def __init__(self, programs: List[schemas.Program], search_keyword: str, page: int, total_pages: int, total_items: int, items_per_page: int):
        super().__init__(timeout=60)  # 60秒でタイムアウト
        self.programs = programs
        self.search_keyword = search_keyword
        self.page = page
        self.total_pages = total_pages
        self.total_items = total_items
        self.items_per_page = items_per_page

        # 現在のページに表示する番組を取得
        start_index = (page - 1) * items_per_page
        end_index = start_index + items_per_page
        current_page_programs = programs[start_index:end_index]

        # 番組選択用のSelectMenuを追加（番組がある場合のみ）
        if current_page_programs:
            select_menu = ProgramSelectMenu(current_page_programs, start_index)
            self.add_item(select_menu)

        # 前のページボタンを追加（1ページ目でない場合）
        if page > 1:
            previous_button = Button(label="前のページ", style=discord.ButtonStyle.secondary, custom_id="previous_page")
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # 次のページボタンを追加（最後のページでない場合）
        if page < total_pages:
            next_button = Button(label="次のページ", style=discord.ButtonStyle.primary, custom_id="next_page")
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        """前のページを表示する"""
        # 前のページ番号を計算
        previous_page = self.page - 1

        # ページ番号が1未満にならないようにする
        if previous_page < 1:
            await interaction.response.send_message("❌ ページ番号が不正です。", ephemeral=True)
            return

        # 現在のページに表示する番組を取得
        start_index = (previous_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_programs = self.programs[start_index:end_index]

        embed = discord.Embed(
            title=f"📺 番組検索結果: 「{self.search_keyword}」",
            description=f"検索結果: {len(current_page_programs)} / {self.total_items} 件",
            color=0x0091ff
        )

        # 各番組を個別のフィールドとして追加
        for i, program in enumerate(current_page_programs, start_index + 1):
            start_time_jst = program.start_time.astimezone(JST)
            end_time_jst = program.end_time.astimezone(JST)

            # チャンネル情報を取得
            channel = await Channel.get_or_none(id=program.channel_id)
            channel_name = channel.name if channel else '不明'

            # 番組情報をフィールドとして追加
            embed.add_field(
                name=f"🎬 {i}: {program.title}",
                value=(
                    f"チャンネル: {channel_name}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                    f"概要: {program.description[:100]}{'...' if len(program.description) > 100 else ''}"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプを追加
        embed.set_footer(text=f"ページ {previous_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいView（ボタン）を作成
        view = ProgramSearchResultView(self.programs, self.search_keyword, previous_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(self, interaction: discord.Interaction):
        """次のページを表示する"""
        # 次のページ番号を計算
        next_page = self.page + 1

        # 現在のページが総ページ数を超えている場合
        if next_page > self.total_pages and self.total_items > 0:
            await interaction.response.send_message("❌ 指定されたページ番号は総ページ数を超えています。", ephemeral=True)
            return

        # 現在のページに表示する番組を取得
        start_index = (next_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_programs = self.programs[start_index:end_index]

        embed = discord.Embed(
            title=f"📺 番組検索結果: 「{self.search_keyword}」",
            description=f"検索結果: {len(current_page_programs)} / {self.total_items} 件",
            color=0x0091ff
        )

        # 各番組を個別のフィールドとして追加
        for i, program in enumerate(current_page_programs, start_index + 1):
            start_time_jst = program.start_time.astimezone(JST)
            end_time_jst = program.end_time.astimezone(JST)

            # チャンネル情報を取得
            channel = await Channel.get_or_none(id=program.channel_id)
            channel_name = channel.name if channel else '不明'

            # 番組情報をフィールドとして追加
            embed.add_field(
                name=f"🎬 {i}: {program.title}",
                value=(
                    f"チャンネル: {channel_name}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                    f"概要: {program.description[:100]}{'...' if len(program.description) > 100 else ''}"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプを追加
        embed.set_footer(text=f"ページ {next_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいView（ボタン）を作成
        view = ProgramSearchResultView(self.programs, self.search_keyword, next_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)

class ReservationListView(View):
    """録画予約一覧表示用のViewクラス"""
    def __init__(self, reservations_data: schemas.Reservations, page: int, total_pages: int, total_items: int, items_per_page: int):
        super().__init__(timeout=60)  # 60秒でタイムアウト
        self.reservations_data = reservations_data
        self.page = page
        self.total_pages = total_pages
        self.total_items = total_items
        self.items_per_page = items_per_page

        # 前のページボタンを追加（1ページ目でない場合）
        if page > 1:
            previous_button = Button(label="前のページ", style=discord.ButtonStyle.secondary, custom_id="previous_page")
            previous_button.callback = self.previous_page
            self.add_item(previous_button)

        # 次のページボタンを追加（最後のページでない場合）
        if page < total_pages:
            next_button = Button(label="次のページ", style=discord.ButtonStyle.primary, custom_id="next_page")
            next_button.callback = self.next_page
            self.add_item(next_button)

    async def previous_page(self, interaction: discord.Interaction):
        """前のページを表示する"""
        # 前のページ番号を計算
        previous_page = self.page - 1

        # ページ番号が1未満にならないようにする
        if previous_page < 1:
            await interaction.response.send_message("❌ ページ番号が不正です。", ephemeral=True)
            return

        # 現在のページに表示する予約を取得
        start_index = (previous_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_reservations = self.reservations_data.reservations[start_index:end_index]

        # Embed を作成
        embed = discord.Embed(
            title=f"録画予約一覧 (ページ {previous_page})",
            color=0x0091ff
        )

        # 各予約を個別のフィールドとして追加
        for i, reservation in enumerate(current_page_reservations, start_index + 1):
            start_time_jst = reservation.program.start_time.astimezone(JST)
            end_time_jst = reservation.program.end_time.astimezone(JST)

            # 予約状況を表す絵文字とテキスト
            if not reservation.record_settings.is_enabled:
                status_emoji = "⚪"  # 予約無効
                status_text = "予約無効"
            elif reservation.recording_availability == "Unavailable":
                status_emoji = "🔴"  # 録画不可
                status_text = "録画不可"
            elif reservation.recording_availability == "Partial":
                status_emoji = "🟠"  # 一部録画不可
                status_text = "一部録画不可"
            elif reservation.is_recording_in_progress:
                status_emoji = "🔵"  # 録画中
                status_text = "録画中"
            else:
                status_emoji = "🟡"  # 録画予定
                status_text = "録画予定"

            # チャンネル情報と番組情報をフィールドとして追加
            embed.add_field(
                name=f"{status_emoji} 予約 {i}: {reservation.program.title}",
                value=(
                    f"チャンネル: {reservation.channel.name}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                    f"録画状況: {status_text}"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプ
        embed.set_footer(text=f"ページ {previous_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいViewを作成
        view = ReservationListView(self.reservations_data, previous_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)

    async def next_page(self, interaction: discord.Interaction):
        """次のページを表示する"""
        # 次のページ番号を計算
        next_page = self.page + 1

        # 現在のページが総ページ数を超えている場合
        if next_page > self.total_pages and self.total_items > 0:
            await interaction.response.send_message("❌ 指定されたページ番号は総ページ数を超えています。", ephemeral=True)
            return

        # 現在のページに表示する予約を取得
        start_index = (next_page - 1) * self.items_per_page
        end_index = start_index + self.items_per_page
        current_page_reservations = self.reservations_data.reservations[start_index:end_index]

        # Embed を作成
        embed = discord.Embed(
            title=f"録画予約一覧 (ページ {next_page})",
            color=0x0091ff
        )

        # 各予約を個別のフィールドとして追加
        for i, reservation in enumerate(current_page_reservations, start_index + 1):
            start_time_jst = reservation.program.start_time.astimezone(JST)
            end_time_jst = reservation.program.end_time.astimezone(JST)

            # 予約状況を表す絵文字とテキスト
            if not reservation.record_settings.is_enabled:
                status_emoji = "⚪"  # 予約無効
                status_text = "予約無効"
            elif reservation.recording_availability == "Unavailable":
                status_emoji = "🔴"  # 録画不可
                status_text = "録画不可"
            elif reservation.recording_availability == "Partial":
                status_emoji = "🟠"  # 一部録画不可
                status_text = "一部録画不可"
            elif reservation.is_recording_in_progress:
                status_emoji = "🔵"  # 録画中
                status_text = "録画中"
            else:
                status_emoji = "🟡"  # 録画予定
                status_text = "録画予定"

            # チャンネル情報と番組情報をフィールドとして追加
            embed.add_field(
                name=f"{status_emoji} 予約 {i}: {reservation.program.title}",
                value=(
                    f"チャンネル: {reservation.channel.name}\n"
                    f"放送時間: {start_time_jst.strftime('%m/%d %H:%M')} - {end_time_jst.strftime('%H:%M')}\n"
                    f"録画状況: {status_text}"
                ),
                inline=False
            )

        # ページ情報とタイムスタンプ
        embed.set_footer(text=f"ページ {next_page} / {self.total_pages}・全 {self.total_items} 件・{datetime.datetime.now().strftime('%Y/%m/%d %H:%M:%S')}")

        # 新しいViewを作成
        view = ReservationListView(self.reservations_data, next_page, self.total_pages, self.total_items, self.items_per_page)

        # メッセージを更新
        await interaction.response.edit_message(embed=embed, view=view)
