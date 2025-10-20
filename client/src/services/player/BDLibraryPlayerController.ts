import assert from 'assert';

import DPlayer, { DPlayerType } from 'dplayer';
import Hls from 'hls.js';
import mpegts from 'mpegts.js';
import { watch } from 'vue';

import APIClient from '@/services/APIClient';
import CustomBufferController from '@/services/player/CustomBufferController';
import DocumentPiPManager from '@/services/player/managers/DocumentPiPManager';
import KeyboardShortcutManager from '@/services/player/managers/KeyboardShortcutManager';
import LiveDataBroadcastingManager from '@/services/player/managers/LiveDataBroadcastingManager';
import LiveEventManager from '@/services/player/managers/LiveEventManager';
import MediaSessionManager from '@/services/player/managers/MediaSessionManager';
import PlayerManager from '@/services/player/PlayerManager';
import Videos from '@/services/Videos';
import useChannelsStore from '@/stores/ChannelsStore';
import usePlayerStore from '@/stores/PlayerStore';
import useSettingsStore, { LiveStreamingQuality, LIVE_STREAMING_QUALITIES, VideoStreamingQuality, VIDEO_STREAMING_QUALITIES } from '@/stores/SettingsStore';
import { useRecordedVideoHistoryStore } from '@/stores/RecordedVideoHistoryStore';
import { useBDLibraryHistoryStore } from '@/stores/BDLibraryHistoryStore';
import useUserStore from '@/stores/UserStore';
import Utils, { dayjs, PlayerUtils } from '@/utils';


/**
 * 動画プレイヤーである DPlayer に関連するロジックを丸ごとラップするクラスで、再生系ロジックの中核を担う
 * DPlayer の初期化後は DPlayer が発行するイベントなどに合わせ、各イベントハンドラーや PlayerManager を管理する
 *
 * このクラスはコンストラクタで指定されたチャンネル or 録画番組の再生に責任を持つ
 * await destroy() 後に再度 await init() すると、コンストラクタに渡したのと同じチャンネル or 録画番組のプレイヤーを再起動できる
 * 再生対象が他のチャンネル or 録画番組に切り替えられた際は、既存の PlayerController を破棄し、新たに PlayerController を作り直す必要がある
 * 実装上、このクラスのインスタンスは必ずアプリケーション上で1つだけ存在するように実装する必要がある
 */
class BDLibraryPlayerController {

    // ライブ視聴: 低遅延モードオンでの再生バッファ (秒単位)
    // 0.9 秒程度余裕を持たせる
    private static readonly LIVE_PLAYBACK_BUFFER_SECONDS_LOW_LATENCY = 0.9;

    // ライブ視聴: 低遅延モードオフでの再生バッファ (秒単位)
    // 4 秒程度の遅延を許容する
    private static readonly LIVE_PLAYBACK_BUFFER_SECONDS = 4.0;

    // 視聴履歴の最大件数
    private static readonly WATCHED_HISTORY_MAX_COUNT = 50;

    // 何秒視聴したら視聴履歴に追加するかの閾値 (秒)
    private static readonly WATCHED_HISTORY_THRESHOLD_SECONDS = 30;

    // 視聴履歴の更新間隔 (秒)
    private static readonly WATCHED_HISTORY_UPDATE_INTERVAL = 10;

    // DPlayer のインスタンス
    private player: DPlayer | null = null;

    // それぞれの PlayerManager のインスタンスのリスト
    private player_managers: PlayerManager[] = [];

    // 再生モード (Live: ライブ視聴, Video: ビデオ視聴)
    private readonly playback_mode: 'Live' | 'Video';

    // 画質プロファイル (Wi-Fi 回線時 / モバイル回線時)
    // デフォルトは自動判定だが、ユーザーによって手動変更されうる
    private quality_profile_type: 'Wi-Fi' | 'Cellular';

    // ライブ視聴: mpegts.js のバッファ詰まり対策で定期的に強制シークするインターバルをキャンセルする関数
    private live_force_seek_interval_timer_cancel: (() => void) | null = null;

    // ビデオ視聴: ビデオストリームのアクティブ状態を維持するために Keep-Alive API にリクエストを送るインターバルのキャンセルする関数
    private video_keep_alive_interval_timer_cancel: (() => void) | null = null;

    // setupPlayerContainerResizeHandler() で利用する ResizeObserver
    // 保持しておかないと disconnect() で ResizeObserver を止められない
    private player_container_resize_observer: ResizeObserver | null = null;

    // setControlDisplayTimer() で利用するタイマー ID
    // 保持しておかないと clearTimeout() でタイマーを止められない
    private player_control_ui_hide_timer_id: number = 0;

    // 視聴履歴に追加すべきかを判断するためのタイムアウトの ID
    private watched_history_threshold_timer_id: number = 0;

    // Screen Wake Lock API の WakeLockSentinel のインスタンス
    // 確保した起動ロックを解放するために保持しておく必要がある
    // Screen Wake Lock API がサポートされていない場合やリクエストに失敗した場合は null になる
    private screen_wake_lock: WakeLockSentinel | null = null;

    // RomSound の AudioContext と AudioBuffer のリスト
    private readonly romsounds_context: AudioContext = new AudioContext();
    private readonly romsounds_buffers: AudioBuffer[] = [];

    // L字画面のクロップ設定で使うウォッチャーを保持する配列
    private lshaped_screen_crop_watchers: (() => void)[] = [];

    // 破棄中かどうか
    // 破棄中は destroy() が呼ばれても何もしない
    private destroying = false;

    // 破棄済みかどうか
    private destroyed = false;

    // BD専用のm3u8パスと画質情報
    private m3u8Path: string;
    private qualities: any[];
    private defaultQuality: number;
    private bdItem: any;

    /**
     * 動作版と同じ品質置換ロジック
     * /original/ を /{selectedQuality}/ に置換
     */
    private getComputedM3u8Path(selectedQuality?: string): string {
        let url = this.m3u8Path;
        // 画質切替: /original/ の部分を /{selectedQuality}/ に置換
        if (selectedQuality && selectedQuality !== 'original') {
            url = url.replace('/original/', `/${selectedQuality}/`);
        }
        return url;
    }


    /**
     * コンストラクタ
     * 実際の DPlayer の初期化処理は await init() で行われる
     */
    constructor(m3u8Path: string, qualities: any[] = [], defaultQuality: number = 0, bdItem: any = null) {

        // BD専用のプロパティを初期化
        this.m3u8Path = m3u8Path;
        this.qualities = qualities;
        this.defaultQuality = defaultQuality;
        this.bdItem = bdItem;

        // BD視聴用の再生モードをセット
        this.playback_mode = 'Video';

        // デフォルトでは、現在のネットワーク回線が Cellular (モバイル回線) のとき、モバイル回線向けの画質プロファイルを適用する
        // Wi-Fi 回線またはネットワーク回線種別を取得できなかった場合は、Wi-Fi 回線向けの画質プロファイルを適用する
        // この画質プロファイルはユーザーによって手動で変更されうる
        const network_circuit_type = PlayerUtils.getNetworkCircuitType();
        if (network_circuit_type === 'Cellular') {
            this.quality_profile_type = 'Cellular';
        } else {
            this.quality_profile_type = 'Wi-Fi';
        }

        // 01 ~ 14 まですべての RomSound を読み込む
        (async () => {
            for (let index = 1; index <= 14; index++) {
                // ArrayBuffer をデコードして AudioBuffer にし、すぐ呼び出せるように貯めておく
                // ref: https://ics.media/entry/200427/
                const romsound_url = `/assets/romsounds/${index.toString().padStart(2, '0')}.wav`;
                const romsound_response = await APIClient.get<ArrayBuffer>(romsound_url, {
                    baseURL: '',  // BaseURL を明示的にクライアントのルートに設定
                    responseType: 'arraybuffer',
                });
                if (romsound_response.type === 'success') {
                    this.romsounds_buffers.push(await this.romsounds_context.decodeAudioData(romsound_response.data));
                }
            }
        })();
    }


    /**
     * 現在の画質プロファイルタイプに応じた画質プロファイル
     */
    private get quality_profile(): {
        tv_streaming_quality: LiveStreamingQuality;
        tv_data_saver_mode: boolean;
        tv_low_latency_mode: boolean;
        video_streaming_quality: VideoStreamingQuality;
        video_data_saver_mode: boolean;
    } {
        const settings_store = useSettingsStore();
        // モバイル回線向けの画質プロファイルを返す
        if (this.quality_profile_type === 'Cellular') {
            return {
                tv_streaming_quality: settings_store.settings.tv_streaming_quality_cellular,
                tv_data_saver_mode: settings_store.settings.tv_data_saver_mode_cellular,
                tv_low_latency_mode: settings_store.settings.tv_low_latency_mode_cellular,
                video_streaming_quality: settings_store.settings.video_streaming_quality_cellular,
                video_data_saver_mode: settings_store.settings.video_data_saver_mode_cellular,
            };
        // Wi-Fi 回線向けの画質プロファイルを返す
        } else {
            return {
                tv_streaming_quality: settings_store.settings.tv_streaming_quality,
                tv_data_saver_mode: settings_store.settings.tv_data_saver_mode,
                tv_low_latency_mode: settings_store.settings.tv_low_latency_mode,
                video_streaming_quality: settings_store.settings.video_streaming_quality,
                video_data_saver_mode: settings_store.settings.video_data_saver_mode,
            };
        }
    }


    /**
     * ライブ視聴: 許容する HTMLMediaElement の内部再生バッファの秒数
     */
    private get live_playback_buffer_seconds(): number {
        // 低遅延モードであれば低遅延向けの再生バッファを、そうでなければ通常の再生バッファ (秒単位)
        let live_playback_buffer_seconds = this.quality_profile.tv_low_latency_mode ?
            BDLibraryPlayerController.LIVE_PLAYBACK_BUFFER_SECONDS_LOW_LATENCY : BDLibraryPlayerController.LIVE_PLAYBACK_BUFFER_SECONDS;
        // Safari の Media Source Extensions API の実装はどうもバッファの揺らぎが大きい (?) ようなので、バッファ詰まり対策で
        // さらに 0.3 秒程度余裕を持たせる
        if (Utils.isSafari() === true) {
            live_playback_buffer_seconds += 0.3;
        }
        return live_playback_buffer_seconds;
    }


    /**
     * DPlayer と PlayerManager を初期化し、再生準備を行う
     */
    public async init(container: HTMLElement, audioTracks: any[] = [], subtitleTracks: any[] = []): Promise<void> {
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();
        const settings_store = useSettingsStore();
        console.log('\u001b[31m[PlayerController] Initializing...');

        // 破棄済みかどうかのフラグを下ろす
        this.destroyed = false;

        // PlayerStore にプレイヤーを初期化したことを通知する
        // 実際にはこの時点ではプレイヤーの初期化は完了していないが、PlayerController.init() を実行したことが通知されることが重要
        // ライブ視聴かつザッピングを経てチャンネルが確定した場合、破棄を遅らせていた以前の PlayerController に紐づく
        // KeyboardShortcutManager がこのタイミングで破棄される
        player_store.is_player_initialized = true;

        // Hls.js を window 直下に入れる
        (window as any).Hls = Hls;

        // BD視聴用: 視聴履歴があればその位置から再生を開始する
        let seek_seconds = 0;

        // BD視聴履歴から再生位置を取得
        const bdLibraryHistoryStore = useBDLibraryHistoryStore();
        const history_item = bdLibraryHistoryStore.history_items.find(
            history => history.bd_id === this.bdItem.id
        );
        if (history_item) {
            seek_seconds = history_item.position;
            console.log(`\u001b[31m[BDLibraryPlayerController] Seeking to ${seek_seconds} seconds. (BD Watched History)`);
        } else {
            console.log(`\u001b[31m[BDLibraryPlayerController] No BD history found, starting from beginning.`);
        }

        // BD視聴ではコメント機能を無効化しているため、コメント関連の初期化は不要

        // BD視聴用: ハイライトマーカーは不要
        const highlights: Array<{text: string, time: number}> = [];

        // .watch-player__dplayer 要素を探す
        const dplayerContainer = container.querySelector('.watch-player__dplayer') as HTMLElement;
        if (!dplayerContainer) {
            throw new Error('BDLibraryPlayerController: .watch-player__dplayer element not found');
        }

        // BD視聴用: 画質設定から適切なデフォルト画質を取得
        let defaultQualityName: string;
        if (this.qualities && this.qualities.length > 0) {
            // 設定から取得したBD画質設定を使用（video_streaming_qualityを流用）
            const settingsQuality = this.quality_profile.video_streaming_quality;
            // 利用可能な画質リストに設定画質が含まれているかチェック
            if (this.qualities.includes(settingsQuality)) {
                defaultQualityName = settingsQuality;
            } else {
                // 設定画質が利用できない場合は最初の画質を使用
                defaultQualityName = this.qualities[0];
                console.warn(`[BDLibraryPlayerController] Configured quality "${settingsQuality}" not available, using "${defaultQualityName}"`);
            }
        } else {
            // 画質リストがない場合は設定画質をそのまま使用（video_streaming_qualityを流用）
            defaultQualityName = this.quality_profile.video_streaming_quality;
        }

        const computedUrl = this.getComputedM3u8Path(defaultQualityName);
        console.log(`[BDLibraryPlayerController] Using quality "${defaultQualityName}"`);
        console.log('[BDLibraryPlayerController] Using computed URL:', computedUrl);

        // DPlayer を初期化
        this.player = new DPlayer({
            // DPlayer を配置する要素
            container: dplayerContainer,
            // テーマカラー
            theme: '#E64F97',
            // 言語 (日本語固定)
            lang: 'ja-jp',
            // ライブモード (BD視聴では無効)
            live: false,
            // ループ再生 (BD視聴では無効)
            loop: false,
            // 自動再生
            autoplay: true,
            // AirPlay 機能 (うまく動かないため無効化)
            airplay: false,
            // ショートカットキー（こちらで制御するため無効化）
            hotkey: false,
            // BD視聴ではスクリーンショット機能を無効化
            screenshot: false,
            // CORS を有効化
            crossOrigin: 'anonymous',
            // 音量の初期値
            volume: 1.0,
            // 再生速度の設定 (x1.1 を追加)
            playbackSpeed: [0.25, 0.5, 0.75, 1, 1.1, 1.25, 1.5, 1.75, 2],
            // シークバー上のハイライトマーカー（BD視聴では不要）
            highlight: highlights,

            // 動画の設定
            video: this.qualities && this.qualities.length > 0
                ? { quality: this.qualities.map((q, i) => ({
                    name: q,
                    url: this.getComputedM3u8Path(q),
                    type: 'hls'
                })), defaultQuality: this.qualities.indexOf(defaultQualityName) !== -1 ? this.qualities.indexOf(defaultQualityName) : 0 }
                : { url: computedUrl, type: 'hls' },

            // 音声トラックの設定 (DPlayerの標準機能では対応していないため、型定義を回避)
            // audio: audioTracks && audioTracks.length > 0 ? audioTracks.map((track, index) => ({
            //     name: track.name || `音声 ${index + 1}`,
            //     url: '', // HLSストリーム内の音声トラックを使用
            //     type: 'hls'
            // })) : [],

            // BD視聴ではコメント機能を完全に無効化
            danmaku: false as any,

            // コメント API バックエンドの設定 (BD視聴では不要)

            // 字幕の設定 (BD視聴では基本設定のみ)
            subtitle: {
                type: 'aribb24',  // aribb24.js を有効化
            } as any,

            // 再生プラグインの設定 (BD視聴用に簡素化)
            pluginOptions: {
                // hls.js
                hls: { ...Hls.DefaultConfig },
                // aribb24.js
                aribb24: {
                    // 文字スーパーレンダラーを有効にする
                    disableSuperimposeRenderer: false,
                    // 描画フォント
                    normalFont: '"Yu Gothic Medium","Yu Gothic","YuGothic", "Rounded M+ 1m for ARIB", sans-serif',
                    // 縁取りする色
                    forceStrokeColor: true,
                    // DRCS 文字を対応する Unicode 文字に置換
                    drcsReplacement: true,
                    // 高解像度の字幕 Canvas を取得できるように
                    enableRawCanvas: true,
                    // 縁取りに strokeText API を利用
                    useStroke: true,
                }
            }
        });

        // デバッグ用にプレイヤーインスタンスも window 直下に入れる
        (window as any).player = this.player;

        // この時点で DPlayer のコンテナ要素に dplayer-mobile クラスが付与されている場合、
        // DPlayer は音量コントロールがないスマホ向けの UI になっている
        // 通常の UI で DPlayer の音量を 1.0 以外に設定した後スマホ向け UI になった場合、DPlayer の音量を変更できず OS の音量を上げるしかなくなる
        // そこで、スマホ向けの UI が表示されている場合のみ常に音量を 1.0 に設定する
        if (this.player.container.classList.contains('dplayer-mobile') === true) {
            // player.volume() を用いることで、単に音量を変更するだけでなく LocalStorage に音量を保存する処理も実行される
            // 第3引数を true に設定すると、通知を表示せずに音量を変更できる
            this.player.volume(1.0, undefined, true);
        }

        // DPlayer 側のコントロール UI 非表示タイマーを無効化（上書き）
        // 無効化しておかないと、PlayerController.setControlDisplayTimer() の処理と競合してしまう
        // 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/v1.30.2/src/ts/controller.ts#L397-L405 にある
        this.player.controller.setAutoHide = (time: number) => {};

        // DPlayer に動画再生系のイベントハンドラーを登録する
        this.setupVideoPlaybackHandler();

        // DPlayer のフルスクリーン関係のメソッドを無理やり上書きし、KonomiTV の UI と統合する
        this.setupFullscreenHandler();

        // DPlayer の設定パネルを無理やり拡張し、KonomiTV 独自の項目を追加する
        this.setupSettingPanelHandler();

        // BD視聴ではコメント機能を完全に無効化しているため、設定項目の削除は不要

        // BD視聴ではL字画面のクロップ機能を無効化

        // KonomiTV 本体の UI を含むプレイヤー全体のコンテナ要素がリサイズされたときのイベントハンドラーを登録する
        this.setupPlayerContainerResizeHandler();

        // プレイヤーのコントロール UI を表示する (初回実行)
        this.setControlDisplayTimer();

        // ビデオ視聴時のみ、指定されている場合は再生速度をレジュームし、指定秒数シークする
        if (this.playback_mode === 'Video') {

            // BD視聴用: 再生速度は1.0で固定

            // 初期化前に算出しておいた秒数分初回シークを実行
            // 録画マージン分シークするケースと、プレイヤー再起動前の再生位置を復元するケースの2通りある
            this.player.seek(seek_seconds);

            // 初回シーク時は確実にエンコーダーの起動が発生するため、ロードに若干時間がかかる
            // このため DPlayer.seek() 内部で実行されているシークバーの更新処理は動作せず、再生が開始されるまで再生済み範囲は反映されない
            // ここで再生済み範囲がシークバー上反映されていないとユーザーの認知的不協和を招くため、手動で再生済み範囲をシーク地点に移動する
            // この時点ではまだ HLS プレイリストのロードが完了していないため、API から取得済みの動画長を用いて割合を計算する
            this.player.bar.set('played', seek_seconds / player_store.recorded_program.recorded_video.duration, 'width');

            // 視聴履歴から再生を再開する場合のみ通知を表示
            // そうでない場合は seek() 実行後に表示される通知を即座に非表示にする
            if (seek_seconds > player_store.recorded_program.recording_start_margin + 2) {
                this.player.notice('前回視聴した続きから再生します');
            } else {
                this.player.hideNotice();
            }
            this.player.play();
            console.log(`\u001b[31m[PlayerController] Seeking to ${seek_seconds} seconds.`);
        }

        // UI コンポーネントからプレイヤーに通知メッセージの送信を要求されたときのイベントハンドラーを登録する
        // このイベントは常にアプリケーション上で1つだけ登録されていなければならない
        player_store.event_emitter.off('SendNotification');  // SendNotification イベントの全てのイベントハンドラーを削除
        player_store.event_emitter.on('SendNotification', (event) => {
            if (this.destroyed === true || this.player === null) return;
            this.player.notice(event.message, event.duration, event.opacity, event.color);
        });

        // プレイヤー初期化後に音声・字幕トラックを設定
        this.player.on('loadedmetadata', () => {
            console.log('\u001b[31m[BDLibraryPlayerController] Video metadata loaded');
            // HTML5 video要素のaudioTracksを設定
            const videoAudioTracks = (this.player!.video as any).audioTracks;
            if (videoAudioTracks && videoAudioTracks.length > 0) {
                console.log(`\u001b[31m[BDLibraryPlayerController] Found ${videoAudioTracks.length} audio tracks in video element`);
                // 最初の音声トラックを有効化
                if (videoAudioTracks.length > 0) {
                    videoAudioTracks[0].enabled = true;
                    console.log(`\u001b[31m[BDLibraryPlayerController] Enabled audio track: ${videoAudioTracks[0].id}`);
                }
            }

            // HTML5 video要素のtextTracksを設定
            const videoTextTracks = this.player!.video.textTracks;
            if (videoTextTracks && videoTextTracks.length > 0) {
                console.log(`\u001b[31m[BDLibraryPlayerController] Found ${videoTextTracks.length} text tracks in video element`);
                // 字幕は初期状態では非表示
                for (let i = 0; i < videoTextTracks.length; i++) {
                    videoTextTracks[i].mode = 'hidden';
                }
            }
        });

        // DPlayerの設定パネルに音声・字幕選択を追加
        setTimeout(() => {
            this.addCustomSettingItems(audioTracks, subtitleTracks);
        }, 1000);

        // 設定パネルの表示を監視して項目を追加
        this.observeSettingPanel(audioTracks, subtitleTracks);

        // PlayerManager からプレイヤーの再起動が必要になったことを通知されたときのイベントハンドラーを登録する
        // このイベントは常にアプリケーション上で1つだけ登録されていなければならない
        // さもなければ使い終わった破棄済みの PlayerController が再起動イベントにより復活し、現在利用中の PlayerController と競合してしまう
        let is_player_restarting = false;  // 現在再起動中かどうか
        player_store.event_emitter.off('PlayerRestartRequired');  // PlayerRestartRequired イベントの全てのイベントハンドラーを削除
        player_store.event_emitter.on('PlayerRestartRequired', async (event) => {

            // すでに破棄済みであれば何もしない
            if (this.destroyed === true || this.player === null) return;
            console.warn('\u001b[31m[PlayerController] PlayerRestartRequired event received. Message: ', event.message);

            // ライブ視聴: iOS 17.0 以下で mpegts.js がサポートされていない場合は再起動できない
            if (this.playback_mode === 'Live' && mpegts.isSupported() !== true) {  // mpegts.js 非対応環境では undefined が返る
                console.warn('\u001b[31m[PlayerController] PlayerRestartRequired event received, but mpegts.js is not supported. Ignored.');
                // iOS 17.0 以下は mpegts.js がサポートされていないため、再生できない
                this.player?.notice('iOS (Safari) 17.0 以下での視聴には対応していません。速やかに iOS を 17.1 以降に更新してください。', -1, undefined, '#FF6F6A');
                return;
            }

            // 既に再起動中であれば何もしない (再起動が重複して行われるのを防ぐ)
            if (is_player_restarting === true) {
                console.warn('\u001b[31m[PlayerController] PlayerRestartRequired event received, but already restarting. Ignored.');
                return;
            }
            is_player_restarting = true;

            // 現在の再生画質・再生速度・再生位置を取得
            // この情報がプレイヤー再起動後にレジュームされる
            const current_quality = this.player?.qualityIndex ? this.player.options.video.quality![this.player.qualityIndex] : null;
            const current_playback_rate = this.player?.video.playbackRate ?? null;
            const current_time = this.player?.video.currentTime ?? null;

            // PlayerController 自身を破棄
            await this.destroy();

            // BD視聴でも再起動時に少し待つ（フリーズ防止）
            await Utils.sleep(0.5);

            // BDLibraryPlayerController 自身を再初期化
            // 再起動完了時点でこの PlayerRestartRequired のイベントハンドラーは再登録されているはず
            // BD視聴では .watch-player コンテナを使用
            const container = document.querySelector('.watch-player') as HTMLElement;
            if (!container) {
                console.error('[BDLibraryPlayerController] Container element not found during restart');
                is_player_restarting = false;
                return;
            }
            try {
                await this.init(container, [], []);
                console.log('[BDLibraryPlayerController] Player restart completed successfully');
            } catch (error) {
                console.error('[BDLibraryPlayerController] Error during player restart:', error);
                is_player_restarting = false;
                return;
            }
            is_player_restarting = false;

            // BD視聴: 再起動前に取得した再生位置にレジューム（スキップ表示なし）
            if (current_time !== null && this.player !== null) {
                // 画質切り替え時はスキップ表示を無効化するため、直接video要素のcurrentTimeを設定
                this.player.video.currentTime = current_time;
                console.log(`[BDLibraryPlayerController] Resumed playback at ${current_time} seconds after restart (skip message disabled)`);
            }

            // BD視聴: 再起動前に取得した再生速度を復元
            if (current_playback_rate !== null && this.player !== null) {
                this.player.video.playbackRate = current_playback_rate;
                console.log(`[BDLibraryPlayerController] Restored playback rate to ${current_playback_rate}x after restart`);
            }

            // BD視聴: 画質プロファイル切り替え後の適切な画質を設定
            if (this.player !== null && this.player.switchQuality) {
                const targetQuality = this.quality_profile.video_streaming_quality;
                const availableQualities = this.player.options.video.quality || [];
                const qualityIndex = availableQualities.findIndex((q: any) => q.name === targetQuality);

                if (qualityIndex !== -1) {
                    this.player.switchQuality(qualityIndex);
                    console.log(`[BDLibraryPlayerController] Switched to quality "${targetQuality}" (index: ${qualityIndex}) after restart`);
                } else {
                    console.warn(`[BDLibraryPlayerController] Target quality "${targetQuality}" not found in available qualities`);
                }
            }

            // プレイヤー側にイベントの発火元から送られたメッセージ (プレイヤーを再起動中である旨) を通知する
            // 再初期化により、作り直した DPlayer が再び this.player にセットされているはず
            // 通知を表示してから PlayerController を破棄すると DPlayer の DOM 要素ごと消えてしまうので、DPlayer を作り直した後に通知を表示する
            assert(this.player !== null);
            if (event.message) {
                // 遅延時間が指定されていれば待つ
                await Utils.sleep(event.message_delay_seconds ?? 0);
                // 明示的にエラーメッセージではないことが指定されていればデフォルトの色で通知を表示する
                // デフォルトではメッセージは赤色で表示される
                const color = event.is_error_message === false ? undefined : '#FF6F6A';
                this.player.notice(event.message, undefined, undefined, color);
            }
        });

        // PlayerController.setControlDisplayTimer() の呼び出しを要求されたときのイベントハンドラーを登録する
        // このイベントは常にアプリケーション上で1つだけ登録されていなければならない
        player_store.event_emitter.off('SetControlDisplayTimer');  // SetControlDisplayTimer イベントの全てのイベントハンドラーを削除
        player_store.event_emitter.on('SetControlDisplayTimer', (event) => {
            this.setControlDisplayTimer(event.event, event.is_player_region_event, event.timeout_seconds);
        });

        // プレイヤー再起動ボタンを DPlayer の UI に追加する (再生が止まった際などに利用する想定)
        // insertAdjacentHTML で .dplayer-icons-right の一番左側に配置する
        this.player.container.querySelector('.dplayer-icons.dplayer-icons-right')!.insertAdjacentHTML('afterbegin', `
            <div class="dplayer-icon dplayer-player-restart-icon" aria-label="プレイヤーを再起動"
                data-balloon-nofocus="" data-balloon-pos="up">
                <span class="dplayer-icon-content">
                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 5V3.21c0-.45-.54-.67-.85-.35l-2.8 2.79c-.2.2-.2.51 0 .71l2.79 2.79c.32.31.86.09.86-.36V7c3.31 0 6 2.69 6 6c0 2.72-1.83 5.02-4.31 5.75c-.42.12-.69.52-.69.95c0 .65.62 1.16 1.25.97A7.991 7.991 0 0 0 20 13c0-4.42-3.58-8-8-8zm-6 8c0-1.34.44-2.58 1.19-3.59c.3-.4.26-.95-.09-1.31c-.42-.42-1.14-.38-1.5.1a7.991 7.991 0 0 0 4.15 12.47c.63.19 1.25-.32 1.25-.97c0-.43-.27-.83-.69-.95C7.83 18.02 6 15.72 6 13z"/></svg>
                </span>
            </div>
        `);
        // PlayerRestartRequired イベントとは異なり、通知メッセージなしで即座に PlayerController を再起動する
        this.player.container.querySelector('.dplayer-player-restart-icon')!.addEventListener('click', async () => {

            // 現在の再生画質・再生速度・再生位置を取得
            // この情報がプレイヤー再起動後にレジュームされる
            const current_quality = this.player?.qualityIndex ? this.player.options.video.quality![this.player.qualityIndex] : null;
            const current_playback_rate = this.player?.video.playbackRate ?? null;
            const current_time = this.player?.video.currentTime ?? null;

            // PlayerController 自身を破棄
            // このイベントは手動で再起動した際に実行されるものなので、再初期化までは待たずに即座に再初期化する
            await this.destroy();

            // PlayerController 自身を再初期化
            await this.init(document.querySelector('.watch-player__dplayer')!, [], []);

            // 通知を表示してから PlayerController を破棄すると DPlayer の DOM 要素ごと消えてしまうので、DPlayer を作り直した後に通知を表示する
            this.player?.notice('プレイヤーを再起動しました。', undefined, undefined, undefined);
        });

        // Screen Wake Lock API を利用して画面の自動スリープを抑制する
        // 待つ必要はないので非同期で実行
        if ('wakeLock' in navigator) {
            navigator.wakeLock.request('screen').then((wake_lock) => {
                this.screen_wake_lock = wake_lock;  // 後で解除するために WakeLockSentinel を保持
                console.log('\u001b[31m[PlayerController] Screen Wake Lock API: Screen Wake Lock acquired.');
            });
        }

        // 各 PlayerManager を初期化・登録
        // BD視聴ではコメント機能、Twitter連携、キャプチャ機能、L字画面クロップ機能を無効化
        // この初期化順序は意図的 (入れ替えても動作するものもあるが、CaptureManager は KeyboardShortcutManager より先に初期化する必要がある)
        if (this.playback_mode === 'Live') {
            // ライブ視聴時に設定する PlayerManager
            this.player_managers = [
                new LiveEventManager(this.player),
                new LiveDataBroadcastingManager(this.player),
                new DocumentPiPManager(this.player, this.playback_mode),
                new KeyboardShortcutManager(this.player, this.playback_mode),
                new MediaSessionManager(this.player, this.playback_mode),
            ];
        } else {
            // ビデオ視聴時に設定する PlayerManager
            this.player_managers = [
                new DocumentPiPManager(this.player, this.playback_mode),
                new KeyboardShortcutManager(this.player, this.playback_mode),
                new MediaSessionManager(this.player, this.playback_mode),
            ];
        }

        // 登録されている PlayerManager をすべて初期化
        // これにより各 PlayerManager での実際の処理が開始される
        // 同期処理すると時間が掛かるので、並行して実行する
        await Promise.all(this.player_managers.map((player_manager) => player_manager.init()));

        // 初期状態でマウスカーソルを表示する
        // プレーヤーUIが表示されている状態から開始するため
        if (this.player !== null) {
            this.player.template.container.style.cursor = '';
        }

        console.log('\u001b[31m[PlayerController] Initialized.');
    }

    /**
     * 字幕トラックの情報を取得する
     */
    public getSubtitleTracks(): any[] {
        if (this.player && this.player.subtitle) {
            return (this.player.subtitle as any).tracks || [];
        }
        return [];
    }

    /**
     * 音声トラックの情報を取得する
     */
    public getAudioTracks(): any[] {
        if (this.player && (this.player as any).audio) {
            return (this.player as any).audio || [];
        }
        return [];
    }

    /**
     * 字幕トラックを切り替える
     */
    public switchSubtitleTrack(trackIndex: number): void {
        if (this.player && this.player.subtitle) {
            const tracks = this.getSubtitleTracks();
            if (tracks[trackIndex]) {
                (this.player.subtitle as any).switch(trackIndex);
            }
        }
    }

    /**
     * 音声トラックを切り替える
     */
    public switchAudioTrack(trackIndex: number): void {
        if (this.player && (this.player as any).audio) {
            const tracks = this.getAudioTracks();
            if (tracks[trackIndex]) {
                (this.player as any).audio.switch(trackIndex);
            }
        }
    }


    /**
     * ライブ視聴: 現在の DPlayer の再生バッファを再生位置とバッファ秒数の差から取得する
     * ビデオ視聴時と、取得に失敗した場合は 0 を返す
     * @returns バッファ秒数
     */
    private getPlaybackBufferSeconds(): number {
        if (this.player === null) return 0;
        if (this.playback_mode === 'Live') {
            try {
                const buffered_range_count = this.player.video.buffered.length;
                const buffer_remain = this.player.video.buffered.end(buffered_range_count - 1) - this.player.video.currentTime;
                return Utils.mathFloor(buffer_remain, 3);
            } catch (error) {
                return 0;
            }
        } else {
            return 0;
        }
    }


    /**
     * まだ再生が開始できていない場合 (HTMLVideoElement.readyState < HAVE_FUTURE_DATA) に再生状態の復旧を試みる
     * 処理の完了を待つ必要はないので、基本 await せず非同期で実行すべき
     * 基本 Safari だとなぜか再生開始がうまく行かないことが多いので（自動再生まわりが影響してる？）、その対策として用意した処理
     */
    private async recoverPlayback(): Promise<void> {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // 1 秒待つ
        await Utils.sleep(1);

        // この時点で映像が停止していて、かつ readyState が HAVE_FUTURE_DATA な場合、復旧を試みる
        // Safari ではタイミングによっては this.player.video が null になる場合があるらしいので ? を付ける
        if (player_store.is_video_buffering === true && this.player?.video?.readyState < 3) {
            console.warn('\u001b[31m[PlayerController] Video still buffering. (HTMLVideoElement.readyState < HAVE_FUTURE_DATA) Trying to recover.');

            // 一旦停止して、0.25 秒間を置く
            this.player.video.pause();
            await Utils.sleep(0.25);

            // 再度再生を試みる
            try {
                await this.player.video.play();
            } catch (error) {
                assert(this.player !== null);
                console.warn('\u001b[31m[PlayerController] HTMLVideoElement.play() rejected. paused.');
                this.player.pause();
                return;  // 再生開始がリジェクトされた場合はここで終了
            }

            // さらに 0.5 秒待った時点で映像が停止している場合、復旧を試みる
            await Utils.sleep(0.5);
            if (player_store.is_video_buffering === true && this.player?.video?.readyState < 3) {
                console.warn('\u001b[31m[PlayerController] Video still buffering. (HTMLVideoElement.readyState < HAVE_FUTURE_DATA) Trying to recover.');

                // 一旦停止して、0.25 秒間を置く
                this.player.video.pause();
                await Utils.sleep(0.25);

                // 再度再生を試みる
                try {
                    await this.player.video.play();
                } catch (error) {
                    assert(this.player !== null);
                    console.warn('\u001b[31m[PlayerController] (retry) HTMLVideoElement.play() rejected. paused.');
                    this.player.pause();
                }
            }
        }
    }


    /**
     * DPlayer に動画再生系のイベントハンドラーを登録する
     * 特にライブ視聴ではここで適切に再生状態の管理 (再生可能かどうか、エラーが発生していないかなど) を行う必要がある
     */
    private setupVideoPlaybackHandler(): void {
        assert(this.player !== null);
        const channels_store = useChannelsStore();
        const player_store = usePlayerStore();
        const settings_store = useSettingsStore();

        // ライブ視聴: 再生停止状態かつ現在の再生位置からバッファが 30 秒以上離れていないかを 60 秒おきに監視し、そうなっていたら強制的にシークする
        // mpegts.js の仕様上、MSE 側に未再生のバッファが貯まり過ぎると新規に SourceBuffer が追加できなくなるため、強制的に接続が切断されてしまう
        // 再生停止状態でも定期的にシークすることで、バッファが貯まりすぎないように調節する
        if (this.playback_mode === 'Live') {
            this.live_force_seek_interval_timer_cancel = Utils.setIntervalInWorker(() => {
                if (this.player === null) return;
                if ((this.player.video.paused && this.player.video.buffered.length >= 1) &&
                    (this.player.video.buffered.end(0) - this.player.video.currentTime > 30)) {
                    this.player.sync();
                }
            }, 60 * 1000);
        }

        // ビデオ視聴: ビデオストリームのアクティブ状態を維持するために 5 秒おきに Keep-Alive API にリクエストを送る
        // HLS プレイリストやセグメントのリクエストが行われたタイミングでも Keep-Alive が行われるが、
        // それだけではタイミング次第では十分ではないため、定期的に Keep-Alive を行う
        // Keep-Alive が行われなくなったタイミングで、サーバー側で自動的にビデオストリームの終了処理 (エンコードタスクの停止) が行われる
        if (this.playback_mode === 'Video') {
            this.video_keep_alive_interval_timer_cancel = Utils.setIntervalInWorker(async () => {
                // 画質切り替えでベース URL が変わることも想定し、あえて毎回 API URL を取得している
                if (this.player === null) return;
                const api_quality = PlayerUtils.extractVideoAPIQualityFromDPlayer(this.player);
                const session_id = PlayerUtils.extractSessionIdFromDPlayer(this.player);
                await APIClient.put(`${Utils.api_base_url}/streams/video/${player_store.recorded_program.id}/${api_quality}/keep-alive?session_id=${session_id}`);
            }, 5 * 1000);
        }

        // 再生/停止されたときのイベント
        // デバイスの通知バーからの制御など、ブラウザの画面以外から動画の再生/停止が行われる事もあるため必要
        const on_play_or_pause = () => {
            if (this.player === null) return;
            player_store.is_video_paused = this.player.video.paused;
            // 停止された場合、ロード中でなければ Progress Circular を非表示にする
            if (this.player.video.paused === true && player_store.is_loading === false) {
                player_store.is_video_buffering = false;
            }
            // まだ設定パネルが表示されていたら非表示にする
            this.player.setting.hide();
            // プレイヤーのコントロール UI を表示する
            this.setControlDisplayTimer();
        };
        this.player.on('play', on_play_or_pause);
        this.player.on('pause', on_play_or_pause);

        // 再生が一時的に止まってバッファリングしているとき/再び再生されはじめたときのイベント
        // バッファリングの Progress Circular の表示を制御する
        this.player.on('waiting', () => {
            // Progress Circular を表示する
            player_store.is_video_buffering = true;
        });
        this.player.on('playing', () => {
            // ロード中 (映像が表示されていない) でなければ Progress Circular を非表示にする
            if (player_store.is_loading === false) {
                player_store.is_video_buffering = false;
            }
            // ライブ視聴: 再生が開始できていない場合に再生状態の復旧を試みる
            if (this.playback_mode === 'Live') {
                this.recoverPlayback();
            }
        });

        // 今回 (DPlayer 初期化直後) と画質切り替え開始時の両方のタイミングで実行する必要がある処理
        // mpegts.js などの DPlayer のプラグインは画質切り替え時に一旦破棄されるため、再度イベントハンドラーを登録する必要がある
        const on_init_or_quality_change = async () => {
            assert(this.player !== null);

            // ローディング中の背景写真をランダムに変更
            player_store.background_url = PlayerUtils.generatePlayerBackgroundURL();

            // 実装上画質切り替え後にそのまま対応できない PlayerManager (LiveDataBroadcastingManager など) をここで再起動する
            // 初回実行時はそもそもまだ PlayerManager が一つも初期化されていないので、何も起こらない
            for (const player_manager of this.player_managers) {
                if (player_manager.restart_required_when_quality_switched === true) {
                    player_manager.destroy().then(() => player_manager.init());  // 非同期で実行
                }
            }

            // ライブ視聴時のみ
            if (this.playback_mode === 'Live') {

                // mpegts.js のエラーログハンドラーを登録
                // 再生中に mpegts.js 内部でエラーが発生した際 (例: デバイスの通信が一時的に切断され、API からのストリーミングが途切れた際) に呼び出される
                // このエラーハンドラーでエラーをキャッチして、PlayerController の再起動を要求する
                // PlayerController 内部なので直接再起動してもいいのだが、PlayerController を再起動させる処理は共通化しておきたい
                this.player.plugins.mpegts?.on(mpegts.Events.ERROR, async (error_type: string, detail: string) => {

                    // DPlayer がすでに破棄されている場合は何もしない
                    if (this.player === null) {
                        return;
                    }

                    // すぐ再起動すると問題があるケースがあるので、少し待機する
                    await Utils.sleep(1);

                    // もしこの時点でオフラインの場合、ネットワーク接続の変更による接続切断の可能性が高いので、オンラインになるまで待機する
                    if (navigator.onLine === false) {
                        this.player.notice('現在ネットワーク接続がありません。オンラインになるまで待機しています…', undefined, undefined, '#FF6F6A');
                        console.warn('\u001b[31m[PlayerController] mpegts.js error event: Network error. Waiting for online...');
                        await Utils.waitUntilOnline();
                    }

                    // PlayerController の再起動を要求する
                    console.error('\u001b[31m[PlayerController] mpegts.js error event:', error_type, detail);
                    player_store.event_emitter.emit('PlayerRestartRequired', {
                        message: `再生中にエラーが発生しました。(${error_type}: ${detail}) プレイヤーを再起動しています…`,
                    });
                });

                // HTMLVideoElement ネイティブの再生時エラーのイベントハンドラーを登録
                // mpegts.js が予期せずクラッシュした場合など、意図せず発生してしまうことがある
                // Offline 以外であれば PlayerController の再起動を要求する
                this.player.on('error', async (event: MediaError) => {

                    // DPlayer がすでに破棄されているか、現在ライブストリームが Offline であれば何もしない
                    if (this.player === null || player_store.live_stream_status === 'Offline') {
                        return;
                    }

                    // すぐ再起動すると問題があるケースがあるので、少し待機する
                    await Utils.sleep(1);

                    if (this.player.video.error) {
                        console.error('\u001b[31m[PlayerController] HTMLVideoElement error event:', this.player.video.error);
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: `再生中にエラーが発生しました。(Native: ${this.player.video.error.code}: ${this.player.video.error.message}) プレイヤーを再起動しています…`,
                        });
                    } else {
                        // MediaError オブジェクトは場合によっては存在しないことがあるらしい…
                        // 存在しない場合は unknown error として扱う
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: '再生中にエラーが発生しました。(Native: unknown error) プレイヤーを再起動しています…',
                        });
                    }
                });

                // 必ず最初はローディング状態とする
                player_store.is_loading = true;

                // 一旦音量をミュートする
                this.player.video.muted = true;

                // この時点で HTMLVideoElement.paused が true のとき、再生できるようになるまで 0.05 秒間を開けて 5 回試す
                if (this.player.video.paused === true) {
                    let attempts = 0;
                    const maxAttempts = 5;  // 試行回数
                    const attemptInterval = 0.05;  // 試行間隔 (秒)
                    const attemptPlay = async (): Promise<void> => {
                        if (attempts >= maxAttempts) {
                            console.warn(`\u001b[31m[PlayerController] Failed to start playback after ${maxAttempts} attempts.`);
                            return;
                        }
                        try {
                            await this.player?.video.play();
                            console.log('\u001b[31m[PlayerController] Playback started successfully.');
                        } catch (error) {
                            console.warn(`\u001b[31m[PlayerController] Attempt ${attempts + 1} to start playback failed:`, error);
                            attempts++;
                            await Utils.sleep(attemptInterval);
                            await attemptPlay();
                        }
                    };
                    await attemptPlay();
                }

                // 再生準備ができた段階で再生バッファを調整し、再生準備ができた段階でローディング中の背景写真を非表示にするイベントハンドラーを登録
                let on_canplay_called = false;
                const on_canplay = async () => {

                    // 重複実行を回避する
                    if (this.player === null) return;
                    if (on_canplay_called === true) return;
                    this.player.video.oncanplay = null;
                    this.player.video.oncanplaythrough = null;
                    on_canplay_called = true;

                    // 再生バッファ調整のため、一旦停止させる
                    // this.player.video.pause() を使うとプレイヤーの UI アイコンが停止してしまうので、代わりに playbackRate を使う
                    console.log('\u001b[31m[PlayerController] Buffering...');
                    this.player.video.playbackRate = 0;

                    // 再生バッファが live_playback_buffer_seconds を超えるまで 0.1 秒おきに再生バッファをチェックする
                    // 再生バッファが live_playback_buffer_seconds を切ると再生が途切れやすくなるので (特に動きの激しい映像)、
                    // 再生開始までの時間を若干犠牲にして、再生バッファの調整と同期に時間を割く
                    // live_playback_buffer_seconds の値は mpegts.js の liveSyncTargetLatency 設定に渡す値と共通
                    const live_playback_buffer_seconds = this.live_playback_buffer_seconds;  // 毎回取得すると負荷が掛かるのでキャッシュする
                    let current_playback_buffer_sec = this.getPlaybackBufferSeconds();
                    while (current_playback_buffer_sec < live_playback_buffer_seconds) {
                        await Utils.sleep(0.1);
                        current_playback_buffer_sec = this.getPlaybackBufferSeconds();
                    }

                    // 再生バッファ調整のため一旦停止していた再生を再び開始
                    this.player.video.playbackRate = 1;
                    console.log('\u001b[31m[PlayerController] Buffering completed.');

                    // ローディング状態を解除し、映像を表示する
                    player_store.is_loading = false;

                    // バッファリング中の Progress Circular を非表示にする
                    player_store.is_video_buffering = false;

                    // この時点で再生が開始できていない場合、再生状態の復旧を試みる
                    this.recoverPlayback();

                    if (channels_store.channel.current.is_radiochannel === true) {
                        // ラジオチャンネルでは引き続き映像の代わりとしてローディング中の背景写真を表示し続ける
                        player_store.is_background_display = true;
                    } else {
                        // ローディング中の背景写真をフェードアウト
                        player_store.is_background_display = false;
                    }

                    // 再生開始時に音量を徐々に上げる (いきなり再生されるよりも体験が良い)
                    // ミュートを解除した上で即座に音量を 0 に設定し、そこから徐々に上げていく
                    this.player.video.muted = false;
                    this.player.video.volume = 0;
                    // 0.5 秒間かけて 0 から current_volume まで音量を上げる
                    const current_volume = this.player.user.get('volume');  // 0.0 ~ 1.0 の範囲
                    const volume_step = current_volume / 10;
                    for (let i = 0; i < 10; i++) {  // 10 回に分けて音量を上げる
                        await Utils.sleep(0.5 / 10);
                        // 音量が current_volume を超えないようにする
                        // 浮動小数点絡みの問題 (丸め誤差) が出るため小数第3位で切り捨てる
                        this.player.video.volume = Math.min(Utils.mathFloor(this.player.video.volume + volume_step, 3), current_volume);
                    }
                    // 最後に current_volume に設定し直す
                    // 上記ロジックでは丸め誤差の関係で完全に current_volume とは一致しないことがあるため
                    this.player.video.volume = current_volume;
                };
                this.player.video.oncanplay = on_canplay;
                this.player.video.oncanplaythrough = on_canplay;

                // 万が一 canplay(through) が発火しなかった場合のために (ほぼ Safari 向け) 、
                // mpegts.js 側でメディア情報が取得できたタイミングでも再生開始を試みる
                // 特に Safari 18 以降では MSE の canplay(through) が場合によっては発火しなかったり、発火が異常に遅かったりする…
                // Safari 18 以降、MSE において canplay(through) の発火タイミングと readyState の値は信頼できない
                this.player.plugins.mpegts?.on(mpegts.Events.MEDIA_INFO, async (info: {[key: string]: any}) => {
                    console.log('\u001b[31m[PlayerController] mpegts.js media info:', info);
                    // 一応ブラウザネイティブの canplay(through) を優先したいので、0.25 秒待ってから再生開始を試みる
                    // 既に再生開始処理を実行済みの場合は実行しない
                    await Utils.sleep(0.25);
                    if (on_canplay_called === false) {
                        console.warn('\u001b[31m[PlayerController] mpegts.js media info fired, but canplay(through) event not fired. Trying to manually start playback.');
                        on_canplay();
                    }
                });

                // 万が一 canplay(through) が発火しなかった場合のために (ほぼ Safari 向け) 、
                // 非同期で 0.05 秒おきに直接 readyState === HAVE_ENOUGH_DATA かどうかを確認する
                // ほとんどのケースでは 先に上記 mpegts.js の MEDIA_INFO イベントが発火するため、この処理は実行されない
                (async () => {
                    let have_future_data_count = 0;
                    while (this.player !== null && this.player.video.readyState < 4) {
                        // プレイヤーが充分と判断する基準はまちまちでブラウザによっては HAVE_FUTURE_DATA のままタイムアウトするので
                        // HAVE_FUTURE_DATA がおおむね 5 秒つづけば HAVE_ENOUGH_DATA 扱いする
                        if (this.player.video.readyState < 3) {
                            have_future_data_count = 0;
                        } else if (++have_future_data_count > 100) {
                            break;
                        }
                        await Utils.sleep(0.05);
                    }
                    // ループを終えた時点で readyState === HAVE_ENOUGH_DATA になっているので、再生開始を試みる
                    // 既に再生開始処理を実行済みの場合は実行しない
                    await Utils.sleep(0.1);
                    if (on_canplay_called === false) {
                        console.warn('\u001b[31m[PlayerController] canplay(through) event not fired. Trying to manually start playback.');
                        on_canplay();
                    }
                })();

                // もしライブストリームのステータスが ONAir にも関わらず 15 秒以上バッファリング中で canplaythrough が発火しない場合、
                // ロードに失敗したとみなし PlayerController の再起動を要求する
                await Utils.sleep(15);
                if (this.destroyed === true || this.player === null) return;
                if (player_store.live_stream_status === 'ONAir' && player_store.is_video_buffering === true && on_canplay_called === false) {
                    player_store.event_emitter.emit('PlayerRestartRequired', {
                        message: '再生開始までに時間が掛かっています。プレイヤーを再起動しています…',
                    });
                }

            // ビデオ視聴のみ
            } else {

                // 必ず最初はローディング状態で、背景写真を表示する
                player_store.is_loading = true;
                player_store.is_background_display = true;

                // 再生準備ができた段階でローディング中の背景写真を非表示にするイベントハンドラーを登録
                let on_canplay_called = false;
                const on_canplay = async () => {

                    // 重複実行を回避する
                    if (this.player === null) return;
                    if (on_canplay_called === true) return;
                    this.player.video.oncanplaythrough = null;
                    on_canplay_called = true;

                    // ローディング状態を解除し、映像を表示する
                    player_store.is_loading = false;

                    // バッファリング中の Progress Circular を非表示にする
                    player_store.is_video_buffering = false;

                    // ローディング中の背景写真をフェードアウト
                    player_store.is_background_display = false;
                };
                this.player.video.oncanplaythrough = on_canplay;

                // HTMLVideoElement ネイティブの再生時エラーのイベントハンドラーを登録
                // HLS 再生時にブラウザが呼び出す HW デコーダーがクラッシュした場合など、意図せず発生してしまうことがある
                // プレイヤー自体の破棄・再生成以外では基本復旧できないので、PlayerController の再起動を要求する
                this.player.on('error', async (event: MediaError) => {

                    // DPlayer がすでに破棄されていれば何もしない
                    if (this.player === null) {
                        return;
                    }

                    // ライブ視聴時とは異なり、録画なので待たなくても再起動できる
                    if (this.player.video.error) {
                        console.error('\u001b[31m[PlayerController] HTMLVideoElement error event:', this.player.video.error);
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: `再生中にエラーが発生しました。(Native: ${this.player.video.error.code}: ${this.player.video.error.message}) プレイヤーを再起動しています…`,
                        });
                    } else {
                        // MediaError オブジェクトは場合によっては存在しないことがあるらしい…
                        // 存在しない場合は unknown error として扱う
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: '再生中にエラーが発生しました。(Native: unknown error) プレイヤーを再起動しています…',
                        });
                    }
                });

            }
        };

        // 初回実行
        on_init_or_quality_change();

        // 画質切り替え開始時のイベント
        this.player.on('quality_start', on_init_or_quality_change);

        // 動画の統計情報の表示/非表示を切り替える隠しコマンドのイベントハンドラーを登録
        // iOS / iPadOS Safari では DPlayer 側の contextmenu が長押ししても発火しないため、代替の表示手段として用意
        // 番組情報タブ内の NEXT >> を 500ms 以内に3回連続でタップすると統計情報の表示/非表示が切り替わる
        // イベントを重複定義しないように、あえて ontouchstart を使う
        let tap_count = 0;
        let last_tap = 0;
        const element = document.querySelector<HTMLDivElement>('.program-info__next');
        if (element !== null) {
            element.ontouchstart = () => {
                if (this.player === null) return;
                const current_time = new Date().getTime();
                const time_difference = current_time - last_tap;
                if (time_difference < 500 && time_difference > 0) {
                    tap_count++;
                    if (tap_count === 3) {
                        this.player.infoPanel.toggle();
                        tap_count = 0;
                    }
                }
                last_tap = current_time;
            };
        }

        // ビデオ視聴時のみ実行する処理
        if (this.playback_mode === 'Video') {

            // 再生位置の変更（再生の進行状況）を Comment.vue にイベントとして通知する
            this.player.on('timeupdate', () => {
                if (!this.player || !this.player.video) {
                    return;
                }
                player_store.event_emitter.emit('PlaybackPositionChanged', {
                    playback_position: this.player.video.currentTime,
                });
            });

            // 視聴履歴の更新処理
            // timeupdate イベントを間引いて処理
            // ここで登録したイベントは、destroy() を実行した際にプレイヤーごと破棄される
            let last_timeupdate_fired_at = 0;
            this.player.on('timeupdate', () => {
                if (!this.player || !this.player.video) {
                    return;
                }
                // 前回 timeupdate イベントが発火した時刻から WATCHED_HISTORY_UPDATE_INTERVAL 秒間は処理を実行しない（間引く）
                const now = new Date().getTime();
                if (now - last_timeupdate_fired_at < BDLibraryPlayerController.WATCHED_HISTORY_UPDATE_INTERVAL * 1000) {
                    return;
                }
                last_timeupdate_fired_at = now;
                const current_time = this.player.video.currentTime;
                const bd_id = this.bdItem.id;

                // ログイン状態をチェック（視聴履歴機能はログイン時のみ動作）
                const userStore = useUserStore();
                if (!userStore.is_logged_in) {
                    return;
                }

                // BD視聴履歴APIを使用
                const bdLibraryHistoryStore = useBDLibraryHistoryStore();
                const history_item = bdLibraryHistoryStore.history_items.find(
                    history => history.bd_id === bd_id
                );

                // 視聴履歴が既に登録されている場合のみ、現在の再生位置を更新
                if (history_item) {
                    bdLibraryHistoryStore.addHistory(this.bdItem, Math.floor(current_time), Math.floor(this.player.video.duration));
                }
            });

            // 視聴開始から WATCHED_HISTORY_THRESHOLD_SECONDS 秒間このページが開かれ続けていたら、視聴履歴に追加する
            this.watched_history_threshold_timer_id = window.setTimeout(() => {
                if (!this.player || !this.player.video) {
                    return;
                }
                const bd_id = this.bdItem.id;

                // ログイン状態をチェック（視聴履歴機能はログイン時のみ動作）
                const userStore = useUserStore();
                if (!userStore.is_logged_in) {
                    return;
                }

                // BD視聴履歴APIを使用
                const bdLibraryHistoryStore = useBDLibraryHistoryStore();
                const history_item = bdLibraryHistoryStore.history_items.find(
                    history => history.bd_id === bd_id
                );

                // まだ視聴履歴に存在しない場合のみ追加
                if (!history_item) {
                    bdLibraryHistoryStore.addHistory(this.bdItem, Math.floor(this.player.video.currentTime), Math.floor(this.player.video.duration));
                }
            }, BDLibraryPlayerController.WATCHED_HISTORY_THRESHOLD_SECONDS * 1000);
        }
    }


    /**
     * DPlayer のフルスクリーン関係のメソッドを無理やり上書きし、KonomiTV の UI と統合する
     * 上書き元のコードは https://github.com/tsukumijima/DPlayer/blob/master/src/ts/fullscreen.ts にある
     */
    private setupFullscreenHandler(): void {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // フルスクリーンにするコンテナ要素 (ページ全体)
        const fullscreen_container = document.body;

        // フルスクリーンかどうか
        this.player.fullScreen.isFullScreen = (type?: DPlayerType.FullscreenType) => {
            return !!(document.fullscreenElement || document.webkitFullscreenElement);
        };

        // フルスクリーンをリクエスト
        this.player.fullScreen.request = (type?: DPlayerType.FullscreenType) => {
            assert(this.player !== null);
            // すでにフルスクリーンだったらキャンセルする
            if (this.player.fullScreen.isFullScreen()) {
                this.player.fullScreen.cancel();
                return;
            }
            // フルスクリーンをリクエスト
            // Safari は webkit のベンダープレフィックスが必要
            fullscreen_container.requestFullscreen = fullscreen_container.requestFullscreen || fullscreen_container.webkitRequestFullscreen;
            if (fullscreen_container.requestFullscreen) {
                fullscreen_container.requestFullscreen();
            } else {
                // フルスクリーンがサポートされていない場合はエラーを表示
                this.player.notice('iPhone Safari は動画のフルスクリーン表示に対応していません。', undefined, undefined, '#FF6F6A');
                return;
            }
            // 画面の向きを横に固定 (Screen Orientation API がサポートされている場合)
            if (screen.orientation) {
                screen.orientation.lock('landscape').catch(() => {});
            }
        };

        // フルスクリーンをキャンセル
        this.player.fullScreen.cancel = (type?: DPlayerType.FullscreenType) => {
            // フルスクリーンを終了
            // Safari は webkit のベンダープレフィックスが必要
            document.exitFullscreen = document.exitFullscreen || document.webkitExitFullscreen;
            if (document.exitFullscreen) {
                document.exitFullscreen();
            }
            // 画面の向きの固定を解除
            if (screen.orientation) {
                screen.orientation.unlock();
            }
        };

        // フルスクリーン状態が変化した時のイベントハンドラーを登録
        // 複数のイベントを重複登録しないよう、あえて onfullscreenchange を使う
        const fullscreen_handler = () => {
            assert(this.player !== null);
            player_store.is_fullscreen = this.player.fullScreen.isFullScreen() === true;
        };
        if (fullscreen_container.onfullscreenchange !== undefined) {
            fullscreen_container.onfullscreenchange = fullscreen_handler;
        } else if (fullscreen_container.onwebkitfullscreenchange !== undefined) {
            fullscreen_container.onwebkitfullscreenchange = fullscreen_handler;
        }
    }


    /**
     * DPlayer の設定パネルを無理やり拡張し、KonomiTV 独自の項目を追加する
     */
    private setupSettingPanelHandler(): void {
        assert(this.player !== null);
        const player_store = usePlayerStore();

        // 設定パネルの開閉を把握するためモンキーパッチを追加し、PlayerStore に通知する
        const original_hide = this.player.setting.hide;
        const original_show = this.player.setting.show;
        this.player.setting.hide = () => {
            if (this.player === null) return;
            original_hide.call(this.player.setting);
            player_store.is_player_setting_panel_open = false;
        };
        this.player.setting.show = () => {
            if (this.player === null) return;
            original_show.call(this.player.setting);
            player_store.is_player_setting_panel_open = true;
        };

        // モバイル回線プロファイルに切り替えるボタンを動的に追加する
        this.player.template.audio.insertAdjacentHTML('afterend', `
            <div class="dplayer-setting-item dplayer-setting-mobile-profile">
                <span class="dplayer-label">モバイル回線向け画質</span>
                <div class="dplayer-toggle">
                    <input class="dplayer-mobile-profile-setting-input" type="checkbox" name="dplayer-toggle-mobile-profile">
                    <label for="dplayer-toggle-mobile-profile" style="--theme-color:#E64F97"></label>
                </div>
            </div>
        `);

        // デフォルトのチェック状態を画質プロファイルタイプに合わせる
        const toggle_mobile_profile_input = this.player.container.querySelector<HTMLInputElement>('.dplayer-mobile-profile-setting-input')!;
        toggle_mobile_profile_input.checked = this.quality_profile_type === 'Cellular';

        // モバイル回線プロファイルに切り替えるボタンがクリックされた時のイベントハンドラーを登録
        const toggle_mobile_profile_button = this.player.container.querySelector('.dplayer-setting-mobile-profile')!;
        toggle_mobile_profile_button.addEventListener('click', async () => {
            try {
                // チェックボックスの状態を切り替える
                toggle_mobile_profile_input.checked = !toggle_mobile_profile_input.checked;

                // 画質プロファイルをモバイル回線向けに切り替えてから、プレイヤーを再起動
                if (toggle_mobile_profile_input.checked) {
                    this.quality_profile_type = 'Cellular';
                    console.log('[BDLibraryPlayerController] Switching to Cellular quality profile');
                    // 非同期でイベントを発行（フリーズ防止）
                    setTimeout(() => {
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: 'モバイル回線向けの画質プロファイルに切り替えました。',
                            // 他の通知と被らないように、メッセージを遅らせて表示する
                            message_delay_seconds: this.quality_profile.tv_low_latency_mode || this.playback_mode === 'Video' ? 2 : 4.5,
                            is_error_message: false,
                        });
                    }, 100);
                // 画質プロファイルを Wi-Fi 回線向けに切り替えてから、プレイヤーを再起動
                } else {
                    this.quality_profile_type = 'Wi-Fi';
                    console.log('[BDLibraryPlayerController] Switching to Wi-Fi quality profile');
                    // 非同期でイベントを発行（フリーズ防止）
                    setTimeout(() => {
                        player_store.event_emitter.emit('PlayerRestartRequired', {
                            message: 'Wi-Fi 回線向けの画質プロファイルに切り替えました。',
                            // 他の通知と被らないように、メッセージを遅らせて表示する
                            message_delay_seconds: this.quality_profile.tv_low_latency_mode || this.playback_mode === 'Video' ? 2 : 4.5,
                            is_error_message: false,
                        });
                    }, 100);
                }
            } catch (error) {
                console.error('[BDLibraryPlayerController] Error during quality profile switch:', error);
                // エラーが発生した場合はチェックボックスの状態を元に戻す
                toggle_mobile_profile_input.checked = !toggle_mobile_profile_input.checked;
                if (this.player) {
                    this.player.notice('画質プロファイルの切り替えに失敗しました。', 3, undefined, '#FF6F6A');
                }
            }
        });

        // BD視聴ではL字画面のクロップ設定ボタンを無効化

        // 設定パネルにショートカット一覧を表示するボタンを動的に追加する
        // スマホなどのタッチデバイスでは基本キーボードが使えないため、タッチデバイスの場合はボタンを表示しない
        if (Utils.isTouchDevice() === false) {
            this.player.template.settingOriginPanel.insertAdjacentHTML('beforeend', `
                <div class="dplayer-setting-item dplayer-setting-keyboard-shortcut">
                    <span class="dplayer-label">キーボードショートカット</span>
                    <div class="dplayer-toggle">
                        <svg xmlns="http://www.w3.org/2000/svg" version="1.1" viewBox="0 0 32 32">
                            <path d="M22 16l-10.105-10.6-1.895 1.987 8.211 8.613-8.211 8.612 1.895 1.988 8.211-8.613z"></path>
                        </svg>
                    </div>
                </div>
            `);

            // ショートカット一覧モーダルを表示するボタンがクリックされたときのイベントハンドラーを登録
            this.player.template.settingOriginPanel.querySelector('.dplayer-setting-keyboard-shortcut')!.addEventListener('click', () => {
                assert(this.player !== null);
                // 設定パネルを閉じる
                this.player.setting.hide();
                // ショートカットキー一覧モーダルを表示する
                player_store.shortcut_key_modal = true;
            });
        }
    }


    // BD視聴ではL字画面のクロップ機能を無効化


    // BD視聴ではコメント機能を完全に無効化しているため、設定項目の削除メソッドは不要


    /**
     * KonomiTV 本体の UI を含むプレイヤー全体のコンテナ要素がリサイズされたときのイベントハンドラーを登録する
     */
    private setupPlayerContainerResizeHandler(): void {

        // 監視対象のプレイヤー全体のコンテナ要素
        const player_container_element = document.querySelector('.watch-player')!;

        // BD視聴ではコメント機能を無効化しているため、コメント関連のリサイズ処理は不要
        const resize_handler = () => {
            // BD視聴ではコメント機能を無効化しているため、何もしない
        };

        // 初回実行
        resize_handler();

        // 要素の監視を開始
        this.player_container_resize_observer = new ResizeObserver(resize_handler);
        this.player_container_resize_observer.observe(player_container_element);
    }


    /**
     * 一定の条件に基づいてプレイヤーのコントロール UI の表示状態を切り替える
     * マウスが動いたりタップされた時に実行するタイマー関数で、3秒間何も操作がなければプレイヤーのコントロール UI を非表示にする
     * 本来は View 側に実装すべきだが、プレイヤー側のロジックとも密接に関連しているため PlayerController に実装した
     * @param event マウスやタッチイベント (手動実行する際は省略する)
     * @param is_player_region_event プレイヤー画面の中で発火したイベントなら true に設定する
     * @param timeout_seconds 何も操作がない場合にコントロール UI を非表示にするまでの秒数
     */
    private setControlDisplayTimer(
        event: Event | null = null,
        is_player_region_event: boolean = false,
        timeout_seconds: number = 3,
    ): void {
        const player_store = usePlayerStore();

        // タッチデバイスで mousemove 、あるいはタッチデバイス以外で touchmove か click が発火した時は実行じない
        if (Utils.isTouchDevice() === true  && event !== null && (event.type === 'mousemove')) return;
        if (Utils.isTouchDevice() === false && event !== null && (event.type === 'touchmove' || event.type === 'click')) return;

        // 以前セットされたタイマーを止める
        window.clearTimeout(this.player_control_ui_hide_timer_id);

        // 実行された際にプレイヤーのコントロール UI を非表示にするタイマー関数 (setTimeout に渡すコールバック関数)
        const player_control_ui_hide_timer = () => {

            // 万が一実行されたタイミングですでに DPlayer が破棄されていたら何もしない
            if (this.player === null) return;

            // BD視聴ではコメント機能を無効化しているため、コメント入力フォームのチェックは不要

            // コントロールを非表示にする
            player_store.is_control_display = false;

            // プレイヤーのコントロールと設定パネルを非表示にする
            this.player.controller.hide();
            this.player.setting.hide();

            // マウスカーソルを非表示にする
            this.player.template.container.style.cursor = 'none';
        };

        // 万が一実行されたタイミングですでに DPlayer が破棄されていたら何もしない
        if (this.player === null) return;

        // タッチデバイスかつプレイヤー画面の中がタップされたとき
        if (Utils.isTouchDevice() === true && is_player_region_event === true) {

            // DPlayer 側のコントロール UI の表示状態に合わせる
            if (this.player.controller.isShow()) {

                // コントロールを表示する
                player_store.is_control_display = true;

                // プレイヤーのコントロールを表示する
                this.player.controller.show();

                // マウスカーソルを表示する
                this.player.template.container.style.cursor = '';

                // 3秒間何も操作がなければコントロールを非表示にする
                // 3秒間の間一度でもタッチされればタイマーが解除されてやり直しになる
                this.player_control_ui_hide_timer_id =
                    window.setTimeout(player_control_ui_hide_timer, timeout_seconds * 1000);

            } else {

                // コントロール UI を非表示にする
                player_store.is_control_display = false;

                // DPlayer 側のコントロール UI と設定パネルを非表示にする
                this.player.controller.hide();
                this.player.setting.hide();

                // マウスカーソルを非表示にする
                this.player.template.container.style.cursor = 'none';
            }

        // それ以外の画面がクリックされたとき
        } else {

            // コントロール UI を表示する
            player_store.is_control_display = true;

            // DPlayer 側のコントロール UI を表示する
            this.player.controller.show();

            // マウスカーソルを表示する
            this.player.template.container.style.cursor = '';

            // 3秒間何も操作がなければコントロールを非表示にする
            // 3秒間の間一度でもマウスが動けばタイマーが解除されてやり直しになる
            this.player_control_ui_hide_timer_id =
                window.setTimeout(player_control_ui_hide_timer, timeout_seconds * 1000);
        }
    }


    /**
     * BD視聴用のメソッド
     */
    public seek(seconds: number, customMessage?: string): void {
        if (!this.player) return;
        this.player.seek(seconds);

        // カスタムメッセージが指定されている場合は表示
        if (customMessage) {
            this.player.notice(customMessage);
        }
    }

    public showController(): void {
        if (!this.player) return;
        this.player.controller.show();
    }

    public hideController(): void {
        if (!this.player) return;
        this.player.controller.hide();
    }

    public setAudioTrack(trackId: number): void {
        if (!this.player) return;
        console.log(`[BDLibraryPlayerController] Setting audio track to: ${trackId}`);

        // HTML5 video要素のaudioTracksを使用
        const audioTracks = (this.player.video as any).audioTracks;
        if (audioTracks && audioTracks.length > 0) {
            console.log(`[BDLibraryPlayerController] Found ${audioTracks.length} audio tracks`);
            for (let i = 0; i < audioTracks.length; i++) {
                const track = audioTracks[i];
                const shouldEnable = (track.id === trackId);
                track.enabled = shouldEnable;
                console.log(`[BDLibraryPlayerController] Audio track ${track.id}: ${shouldEnable ? 'enabled' : 'disabled'}`);
            }
        } else {
            console.warn('[BDLibraryPlayerController] No audio tracks found in video element');
        }
    }

    public setSubtitleTrack(trackId: number | null): void {
        if (!this.player) return;
        console.log(`[BDLibraryPlayerController] Setting subtitle track to: ${trackId}`);

        const textTracks = this.player.video.textTracks;
        if (textTracks && textTracks.length > 0) {
            console.log(`[BDLibraryPlayerController] Found ${textTracks.length} text tracks`);
            for (let i = 0; i < textTracks.length; i++) {
                const track = textTracks[i];
                const shouldShow = (trackId !== null && track.id == trackId.toString());
                track.mode = shouldShow ? 'showing' : 'hidden';
                console.log(`[BDLibraryPlayerController] Text track ${track.id}: ${shouldShow ? 'showing' : 'hidden'}`);
            }
        } else {
            console.warn('[BDLibraryPlayerController] No text tracks found in video element');
        }
    }

    private observeSettingPanel(audioTracks: any[], subtitleTracks: any[]): void {
        // MutationObserverを使用して設定パネルの表示を監視
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.type === 'childList') {
                    const settingBox = document.querySelector('.dplayer-setting-box') as HTMLElement;
                    if (settingBox && settingBox.style.display !== 'none') {
                        // 設定パネルが表示されたら項目を追加
                        setTimeout(() => {
                            this.addCustomSettingItems(audioTracks, subtitleTracks);
                        }, 100);
                    }
                }
            });
        });

        // プレイヤーコンテナを監視対象に設定
        const playerContainer = document.querySelector('.dplayer');
        if (playerContainer) {
            observer.observe(playerContainer, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['style']
            });
        }
    }

    private addCustomSettingItems(audioTracks: any[], subtitleTracks: any[]): void {
        if (!this.player) return;

        console.log('[BDLibraryPlayerController] Adding custom setting items');
        console.log('Audio tracks:', audioTracks);
        console.log('Subtitle tracks:', subtitleTracks);

        // DPlayerの設定パネルを取得
        const settingBox = document.querySelector('.dplayer-setting-box');
        if (!settingBox) {
            console.warn('[BDLibraryPlayerController] Setting box not found');
            return;
        }

        // 既存のカスタム項目を削除
        const existingAudioSelect = settingBox.querySelector('.bdlibrary-audio-select');
        const existingSubtitleSelect = settingBox.querySelector('.bdlibrary-subtitle-select');
        if (existingAudioSelect) {
            existingAudioSelect.parentElement?.remove();
        }
        if (existingSubtitleSelect) {
            existingSubtitleSelect.parentElement?.remove();
        }

        // 音声選択項目を追加（複数音声がある場合のみ）
        if (audioTracks && audioTracks.length > 1) {
            const audioItem = document.createElement('div');
            audioItem.className = 'dplayer-setting-item';
            audioItem.innerHTML = `
                <span>音声</span>
                <select class="bdlibrary-audio-select">
                    ${audioTracks.map(track =>
                        `<option value="${track.id}">${track.name || `Audio ${track.id}`} (${track.language || 'und'}${track.channels ? ', ' + track.channels + 'ch' : ''})</option>`
                    ).join('')}
                </select>
            `;
            settingBox.appendChild(audioItem);

            // 音声選択イベント
            const audioSelect = audioItem.querySelector('.bdlibrary-audio-select') as HTMLSelectElement;
            audioSelect.addEventListener('change', (e) => {
                const target = e.target as HTMLSelectElement;
                const trackId = Number(target.value);
                console.log('[BDLibraryPlayerController] Audio track selected:', trackId);
                this.setAudioTrack(trackId);
            });

            console.log('[BDLibraryPlayerController] Added audio selection item');
        }

        // 字幕選択項目を追加（字幕がある場合のみ）
        if (subtitleTracks && subtitleTracks.length > 0) {
            const subtitleItem = document.createElement('div');
            subtitleItem.className = 'dplayer-setting-item';
            subtitleItem.innerHTML = `
                <span>字幕</span>
                <select class="bdlibrary-subtitle-select">
                    <option value="">オフ</option>
                    ${subtitleTracks.map(track =>
                        `<option value="${track.id}">${track.name || `Subtitle ${track.id}`} (${track.language || 'und'})</option>`
                    ).join('')}
                </select>
            `;
            settingBox.appendChild(subtitleItem);

            // 字幕選択イベント
            const subtitleSelect = subtitleItem.querySelector('.bdlibrary-subtitle-select') as HTMLSelectElement;
            subtitleSelect.addEventListener('change', (e) => {
                const target = e.target as HTMLSelectElement;
                const trackId = target.value ? Number(target.value) : null;
                console.log('[BDLibraryPlayerController] Subtitle track selected:', trackId);
                this.setSubtitleTrack(trackId);
            });

            console.log('[BDLibraryPlayerController] Added subtitle selection item');
        }
    }

    /**
     * DPlayer と PlayerManager を破棄し、再生を終了する
     * 常に init() で作成したものが destroy() ですべてクリーンアップされるように実装すべき
     * PlayerController の再起動を行う場合、基本外部から直接 await destroy() と await init() は呼び出さず、代わりに
     * player_store.event_emitter.emit('PlayerRestartRequired', 'プレイヤーを再起動しています…') のようにイベントを発火させるべき
     */
    public async destroy(): Promise<void> {
        const settings_store = useSettingsStore();
        const player_store = usePlayerStore();

        // すでに破棄されているのに再度実行してはならない
        if (this.destroyed === true) {
            return;
        }
        // すでに破棄中なら何もしない
        if (this.destroying === true) {
            return;
        }
        this.destroying = true;

        // 視聴履歴の最終位置を更新
        // 現在の再生位置を取得するため、プレイヤーの破棄前に実行する必要がある
        if (this.playback_mode === 'Video' && this.player && this.player.video) {
            const history_index = settings_store.settings.watched_history.findIndex(
                history => history.video_id === player_store.recorded_program.id
            );
            if (history_index !== -1) {
                // 次再生するときにスムーズに再開できるよう、現在の再生位置の10秒前の位置を記録する
                const current_time = this.player.video.currentTime - 10;
                settings_store.settings.watched_history[history_index].last_playback_position = current_time;
                settings_store.settings.watched_history[history_index].updated_at = Utils.time();
                console.log(`\u001b[31m[PlayerController] Last playback position updated. (Video ID: ${player_store.recorded_program.id}, last_playback_position: ${current_time})`);
            }
        }

        console.log('\u001b[31m[PlayerController] Destroying...');

        // 登録されている PlayerManager をすべて破棄
        // CSS アニメーションの関係上、ローディング状態にする前に破棄する必要がある (特に LiveDataBroadcastingManager)
        // 同期処理すると時間が掛かるので、並行して実行する
        await Promise.all(this.player_managers.map(async (player_manager) => player_manager.destroy()));
        this.player_managers = [];

        // Screen Wake Lock API で確保した起動ロックを解放
        // 起動ロックが確保できていない場合は何もしない
        if (this.screen_wake_lock !== null) {
            this.screen_wake_lock.release();
            this.screen_wake_lock = null;
            console.log('\u001b[31m[PlayerController] Screen Wake Lock API: Screen Wake Lock released.');
        }

        // ローディング中の背景写真を隠す
        player_store.is_background_display = false;

        // 再びローディング状態にする
        player_store.is_loading = true;

        // コメントの取得に失敗した際のエラーメッセージを削除
        player_store.live_comment_init_failed_message = null;
        player_store.video_comment_init_failed_message = null;

        // 映像がフェードアウトするアニメーション (0.2秒) 分待ってから実行
        // この 0.2 秒の間に音量をフェードアウトさせる
        if (this.player !== null) {
            // 0.2 秒間かけて current_volume から 0 まで音量を下げる
            const current_volume = this.player.user.get('volume');  // 0.0 ~ 1.0 の範囲
            const volume_step = current_volume / 10;
            for (let i = 0; i < 10; i++) {  // 10 回に分けて音量を下げる
                await Utils.sleep(0.2 / 10);
                // ごく稀に映像が既に破棄されている or まだ再生開始されていない場合がある (?) ので、その場合は実行しない
                if (this.player && this.player.video) {
                    // 音量が 0 より小さくならないようにする
                    // 浮動小数点絡みの問題 (丸め誤差) が出るため小数第3位で切り捨てる
                    this.player.video.volume = Math.max(Utils.mathFloor(this.player.video.volume - volume_step, 3), 0);
                }
            }
            // 最後に音量を 0 に設定
            // 上記ロジックでは丸め誤差の関係で完全に 0 とは一致しないことがあるため
            this.player.video.volume = 0;
        }

        // タイマーを破棄
        if (this.live_force_seek_interval_timer_cancel !== null) {
            this.live_force_seek_interval_timer_cancel();
            this.live_force_seek_interval_timer_cancel = null;
        }
        if (this.video_keep_alive_interval_timer_cancel !== null) {
            this.video_keep_alive_interval_timer_cancel();
            this.video_keep_alive_interval_timer_cancel = null;
        }
        window.clearTimeout(this.watched_history_threshold_timer_id);
        window.clearTimeout(this.player_control_ui_hide_timer_id);

        // プレイヤー全体のコンテナ要素の監視を停止
        if (this.player_container_resize_observer !== null) {
            this.player_container_resize_observer.disconnect();
            this.player_container_resize_observer = null;
        }

        // BD視聴ではL字画面のクロップ設定のウォッチャーは使用しない

        // DPlayer 本体を破棄
        // なぜか例外が出ることがあるので try-catch で囲む
        if (this.player !== null) {
            // プレイヤーの破棄を実行する前に、DPlayer 側に登録された HTMLVideoElement の error イベントハンドラーを全て削除
            // Safari のみ、削除しておかないと「動画の読み込みに失敗しました」というエラーが発生する
            if (this.player.events.events['error']) {
                this.player.events.events['error'] = [];
            }
            // 通常 this.player.destroy() が実行された後 mpegts.js も自動的に破棄されるのだが、Safari のみ
            // なぜか video.src = '' を実行した後に mpegts.js を破棄するとエラーというか挙動不審になるので、
            // あえて mpegts.js を明示的に先に破棄しておいて Safari の地雷を回避する
            if (this.player.plugins.mpegts) {
                try {
                    this.player.plugins.mpegts.unload();
                    this.player.plugins.mpegts.detachMediaElement();
                    this.player.plugins.mpegts.destroy();
                } catch (e) {
                    // 何もしない
                }
            }
            // 引数に true を指定して、破棄後も DPlayer 側の HTML 要素を保持する
            // これにより、チャンネルを切り替えるなどして再度初期化されるまでの僅かな間もプレイヤーのコントロール UI が表示される (動作はしない)
            // ここで HTML 要素を削除してしまうと、プレイヤーのコントロール UI が一瞬削除されることでちらつきが発生して見栄えが悪い
            // BD視聴ではコメント機能を無効化しているため、コメントのクリアは不要

            // マウスカーソルの状態をリセットする
            this.player.template.container.style.cursor = '';

            try {
                this.player.destroy(true);
            } catch (e) {
                // 何もしない
            }
            this.player = null;
        }

        // 破棄済みかどうかのフラグを立てる
        this.destroying = false;
        this.destroyed = true;

        // PlayerStore にプレイヤーを破棄したことを通知
        player_store.is_player_initialized = false;

        console.log('\u001b[31m[PlayerController] Destroyed.');
    }
}

export default BDLibraryPlayerController;
