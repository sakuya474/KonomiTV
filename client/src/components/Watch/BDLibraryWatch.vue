<template>
    <BDLibraryWatchMain :playback_mode="'Video'" />
</template>
<script lang="ts">
import { defineComponent, onBeforeUnmount } from 'vue';
import { mapStores } from 'pinia';

import BDLibraryWatchMain from '@/components/Watch/BDLibraryWatchMain.vue';
import BDLibrary, { IBDLibraryItem } from '@/services/BDLibrary';
import BDLibraryPlayerController from '@/services/player/BDLibraryPlayerController';
import useSettingsStore from '@/stores/SettingsStore';
import { useBDLibraryStore } from '@/stores/BDLibraryStore';
import { useBDLibraryHistoryStore } from '@/stores/BDLibraryHistoryStore';
import usePlayerStore from '@/stores/PlayerStore';

// BDLibraryPlayerController のインスタンス
// data() 内に記述すると再帰的にリアクティブ化され重くなる上リアクティブにする必要自体がないので、グローバル変数にしている
let bd_player_controller: BDLibraryPlayerController | null = null;

export default defineComponent({
    name: 'BDLibraryWatch',
    components: {
        BDLibraryWatchMain,
    },

    computed: {
        ...mapStores(usePlayerStore, useSettingsStore, useBDLibraryStore, useBDLibraryHistoryStore),
    },
    // 開始時に実行
    created() {

        // 下記以外の視聴画面の開始処理は BDLibraryWatchMain コンポーネントの方で自動的に行われる

        // 再生セッションを初期化
        this.init();
    },
    // BD切り替え時に実行
    // コンポーネント（インスタンス）は再利用される
    // ref: https://v3.router.vuejs.org/ja/guide/advanced/navigation-guards.html#%E3%83%AB%E3%83%BC%E3%83%88%E5%8D%98%E4%BD%8D%E3%82%AB%E3%82%99%E3%83%BC%E3%83%89
    beforeRouteUpdate(to, from, next) {

        // 前の再生セッションを破棄して終了し、完了を待ってから再度初期化する
        const destroy_promise = this.destroy();
        destroy_promise.then(() => this.init());

        // 次のルートに置き換え
        next();
    },
    // 終了前に実行
    beforeUnmount() {

        // destroy() を実行
        // 別のページへ遷移するため、DPlayer のインスタンスを確実に破棄する
        // さもなければ、ブラウザがリロードされるまでバックグラウンドで永遠に再生され続けてしまう
        this.destroy();

        // 上記以外の視聴画面の終了処理は BDLibraryWatchMain コンポーネントの方で自動的に行われる
    },
    methods: {

        // 再生セッションを初期化する
        async init() {

            // URL 上の BD ID が未定義なら実行しない (フェイルセーフ)
            // 基本あり得ないはずだが、念のため
            if (this.$route.params.id === undefined) {
                this.$router.push({path: '/not-found/'});
                return;
            }

            // BD アイテム情報を更新する
            console.log('BD ID:', this.$route.params.id);
            const bd_item = await BDLibrary.fetchBDLibraryItem(parseInt(this.$route.params.id as string));
            console.log('BD Item fetched:', bd_item);
            console.log('BD Item titles:', bd_item?.titles);
            console.log('BD Item chapters:', bd_item?.chapters);
            if (bd_item === null) {
                console.error('BD item not found for ID:', this.$route.params.id);
                this.$router.push({path: '/not-found/'});
                return;
            }
            this.bdLibraryStore.bdItem = bd_item;

            // 音声・字幕トラック情報を明示的に取得
            console.log('Attempting to fetch tracks for BD ID:', bd_item.id);
            try {
                const tracks = await BDLibrary.fetchBDLibraryTracks(bd_item.id);
                console.log('Tracks API response:', tracks);
                if (tracks && tracks.audio && tracks.subtitle) {
                    console.log('Adding tracks to BD item');
                    bd_item.audio = tracks.audio;
                    bd_item.subtitle = tracks.subtitle;
                    this.bdLibraryStore.bdItem = { ...bd_item, audio: tracks.audio, subtitle: tracks.subtitle };
                    console.log('Updated BD item with tracks:', this.bdLibraryStore.bdItem);
                } else {
                    console.log('No tracks data received or invalid format');
                }
            } catch (error) {
                console.error('Failed to fetch tracks:', error);
                console.log('Proceeding without tracks data');
            }

            // BD視聴履歴を事前に取得（続きから再生のため）
            await this.bdLibraryHistoryStore.fetchHistoryList();

            // チャプター情報を明示的に取得
            console.log('Attempting to fetch chapters for BD ID:', bd_item.id);
            try {
                const chapters = await BDLibrary.fetchBDLibraryChapters(bd_item.id);
                console.log('Chapters API response:', chapters);
                if (chapters && Array.isArray(chapters)) {
                    console.log('Adding chapters to BD item');
                    bd_item.chapters = chapters;
                    this.bdLibraryStore.bdItem = { ...bd_item, chapters };
                    console.log('Updated BD item with chapters:', this.bdLibraryStore.bdItem);
                } else {
                    console.log('No chapters data received or invalid format');
                }
            } catch (error) {
                console.error('Failed to fetch chapters:', error);
                console.log('Proceeding without chapters data');
            }

            // PlayerStore の状態を更新
            this.playerStore.is_loading = true;
            this.playerStore.is_background_display = true; // 背景を表示してローディング状態を明確にする
            this.playerStore.is_video_buffering = false;
            // BD視聴では初期状態でパネルを表示
            this.playerStore.is_panel_display = true;

            // フルスクリーン状態を監視（追加の保険）
            const checkFullscreen = () => {
                const isFullscreen = !!document.fullscreenElement;
                if (this.playerStore.is_fullscreen !== isFullscreen) {
                    console.log('[BDLibraryWatch] Updating fullscreen state:', isFullscreen);
                    this.playerStore.is_fullscreen = isFullscreen;
                }
            };

            // フルスクリーン監視を開始
            setInterval(checkFullscreen, 500);

            // 動作版と完全に同じロジック: 初期は /original/ で、後で品質に応じて置換
            const sessionId = crypto.randomUUID().split('-')[0]; // 動作版と同じUUID生成方式
            const m3u8Path = `/api/streams/bd-library/${bd_item.id}/original/playlist.m3u8?session_id=${sessionId}`;

            console.log('[BDLibraryWatch] Generated session_id:', sessionId);
            console.log('[BDLibraryWatch] Final m3u8 path:', m3u8Path);
            console.log('[BDLibraryWatch] Available qualities:', bd_item.available_qualities);
            bd_player_controller = new BDLibraryPlayerController(m3u8Path, bd_item.available_qualities || [], 0, bd_item);

            // プレイヤーコンテナを取得して初期化
            // DOM要素が生成されるまで少し待つ
            await this.$nextTick();
            await new Promise(resolve => setTimeout(resolve, 200)); // 追加の待機時間

            // DOMから直接プレイヤーコンテナを取得
            const container = document.querySelector('.watch-player') as HTMLElement;

            if (container) {
                console.log('Initializing BDLibraryPlayerController with:', {
                    m3u8Path,
                    qualities: bd_item.available_qualities,
                    audio: bd_item.audio,
                    subtitle: bd_item.subtitle
                });
                try {
                    await bd_player_controller.init(container, bd_item.audio || [], bd_item.subtitle || []);
                    console.log('BDLibraryPlayerController initialized successfully');

                    // プレイヤーが実際に動画を読み込めているかチェック
                    const dplayerElement = container.querySelector('.dplayer');
                    console.log('DPlayer element found:', dplayerElement);

                    // DPlayerの実際の状態を監視してローディング状態を解除
                    const checkPlayerReady = () => {
                        const dplayerElement = container.querySelector('.dplayer');
                        const video = dplayerElement?.querySelector('video');

                        console.log('Checking player ready state...');
                        console.log('DPlayer classes:', dplayerElement?.className);
                        console.log('Video element:', video);
                        console.log('Video readyState:', video?.readyState);
                        console.log('Video networkState:', video?.networkState);

                        if (video && video.readyState >= 2) {
                            // 動画が読み込み準備完了
                            console.log('Video is ready, clearing loading state');
                            this.playerStore.is_loading = false;
                            this.playerStore.is_background_display = false;
                        } else if (dplayerElement && !dplayerElement.classList.contains('dplayer-loading')) {
                            // DPlayerのローディングクラスが削除されている
                            console.log('DPlayer loading class removed, clearing loading state');
                            this.playerStore.is_loading = false;
                            this.playerStore.is_background_display = false;
                        } else {
                            // まだ準備できていない場合は500ms後に再チェック
                            setTimeout(checkPlayerReady, 500);
                        }
                    };

                    // 初回チェックを1秒後に開始
                    setTimeout(checkPlayerReady, 1000);

                    // 10秒後に強制的にローディング状態を解除（フェイルセーフ）
                    setTimeout(() => {
                        console.log('[BDLibraryWatch] Force clearing loading state after 10 seconds');
                        this.playerStore.is_loading = false;
                        this.playerStore.is_background_display = false;

                        // DPlayerのローディングクラスも強制除去
                        const dplayerElement = container.querySelector('.dplayer');
                        if (dplayerElement && dplayerElement.classList.contains('dplayer-loading')) {
                            console.log('[BDLibraryWatch] Force removing dplayer-loading class');
                            dplayerElement.classList.remove('dplayer-loading');
                        }
                    }, 10000);
                } catch (error) {
                    console.error('Failed to initialize BDLibraryPlayerController:', error);
                    this.playerStore.is_loading = false;
                }
            } else {
                console.error('Player container not found');
                this.playerStore.is_loading = false;
            }
        },

        // 再生セッションを破棄する
        // 再生する BD を切り替える際にも実行される
        async destroy() {

            // BDLibraryPlayerController を破棄
            if (bd_player_controller !== null) {
                await bd_player_controller.destroy();
                bd_player_controller = null;
            }
        },

        // BDLibraryPlayerController のインスタンスを取得するメソッド
        // 子コンポーネントからアクセスするために使用
        getBDPlayerController() {
            return bd_player_controller;
        },
    }
});
</script>
<style lang="scss">

// 上書きしたいスタイル

// コントロール表示時
.watch-container.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-controller-mask, .dplayer-controller {
            opacity: 1 !important;
            visibility: visible !important;
            .dplayer-comment-box {
                left: calc(68px + 20px);
                @include tablet-vertical {
                    left: calc(0px + 16px);
                }
                @include smartphone-horizontal {
                    left: calc(0px + 16px);
                }
                @include smartphone-vertical {
                    left: calc(0px + 16px);
                }
            }
        }
        .dplayer-notice {
            left: calc(68px + 30px);
            bottom: 62px;
            @include tablet-vertical {
                left: calc(0px + 16px);
                bottom: 62px !important;
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
                bottom: 62px !important;
            }
        }
        .dplayer-info-panel {
            top: 82px;
            left: calc(68px + 30px);
            @include tablet-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
            }
        }
        .dplayer-comment-setting-box {
            left: calc(68px + 20px);
            @include tablet-vertical {
                left: calc(0px + 16px);
            }
            @include smartphone-horizontal {
                left: calc(0px + 16px);
            }
            @include smartphone-vertical {
                left: calc(0px + 16px);
            }
        }
        .dplayer-mobile .dplayer-mobile-icon-wrap {
            opacity: 0.7 !important;
            visibility: visible !important;
        }
    }
}

// コントロール非表示時
.watch-container:not(.watch-container--control-display) {
    .watch-player__dplayer {
        .dplayer-danmaku {
            max-height: 100% !important;
            aspect-ratio: 16 / 9 !important;
        }
        .dplayer-notice {
            bottom: 20px !important;
        }
    }
}

// 非フルスクリーン時
.watch-container:not(.watch-container--fullscreen) {
    .watch-player__dplayer.dplayer-mobile {
        .dplayer-setting-box {
            @include smartphone-vertical {
                // スマホ縦画面かつ非フルスクリーン時のみ、設定パネルを画面下部にオーバーレイ配置
                position: fixed;
                left: 0px !important;
                right: 0px !important;
                bottom: env(safe-area-inset-bottom) !important;  // iPhone X 以降の Home Indicator の高さ分
                width: 100% !important;
                height: 100% !important;
                background: rgb(var(--v-theme-background));
                transform: translateY(40%) !important;
                z-index: 100 !important;
            }
            &.dplayer-setting-box-open {
                transform: translateY(0%) !important;
            }
        }
    }
}
// フルスクリーン時
.watch-container.watch-container--fullscreen {
    .watch-player__dplayer {
        .dplayer-controller {
            padding-left: 20px !important;
        }
        &.dplayer-mobile .dplayer-controller {
            padding-left: 30px !important;
            @include tablet-vertical {
                padding-left: 16px !important;
            }
            @include smartphone-horizontal {
                padding-left: 16px !important;
            }
            @include smartphone-vertical {
                padding-left: 16px !important;
            }
        }
        .dplayer-comment-box, .dplayer-comment-setting-box {
            left: 20px !important;
            @include tablet-vertical {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-vertical {
                left: 16px !important;
            }
        }
    }
    .watch-header__back-icon {
        display: none !important;
    }
}

// フルスクリーン時 + コントロール表示時
.watch-container.watch-container--fullscreen.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-notice, .dplayer-info-panel {
            left: 30px !important;
            @include tablet-vertical {
                left: 16px !important;
            }
            @include smartphone-horizontal {
                left: 16px !important;
            }
            @include smartphone-vertical {
                left: 16px !important;
            }
        }
    }
}

// Document Picture-in-Picture 時
.watch-container.watch-container--document-pip {
    // ナビゲーションを強制表示
    .watch-navigation {
        opacity: 1 !important;
        visibility: visible !important;
    }
}

// ビデオ視聴時 + コントロール表示時のみ適用されるスタイル
.watch-container.watch-container--video.watch-container--control-display {
    .watch-player__dplayer {
        .dplayer-notice {
            bottom: 74px !important;
        }
        &.dplayer-mobile .dplayer-notice {
            bottom: 71px !important;
            @include smartphone-vertical {
                bottom: 50px !important;
            }
        }
    }
}

// ビデオ視聴時 + フルスクリーン時のみ適用されるスタイル
.watch-container.watch-container--video.watch-container--fullscreen {
    .watch-player__dplayer {
        .dplayer-bar-wrap {
            width: calc(100% - (18px * 2)) !important;
        }
        &.dplayer-mobile .dplayer-bar-wrap {
            width: calc(100% - (30px * 2));
            @include tablet-horizontal {
                width: calc(100% - (30px * 2)) !important;
            }
            @include tablet-vertical {
                width: calc(100% - (18px * 2)) !important;
            }
            @include smartphone-horizontal {
                width: calc(100% - (18px * 2)) !important;
            }
            @include smartphone-vertical {
                width: calc(100% - (18px * 2)) !important;
            }
        }
    }
}

// Document Picture-in-Picture 時の「ピクチャー イン ピクチャーを再生しています」のテキスト
.watch-container {
    .playing-in-pip {
        display: flex;
        flex-direction: column;
        gap: 20px;
        align-items: center;
        justify-content: center;
        width: 100%;
        color: rgb(var(--v-theme-text-darken-1));
        font-size: 24px;
        padding: 20px;
        @include smartphone-vertical {
            aspect-ratio: 16 / 9;
        }

        &__close-button {
            padding: 12px 16px;
            border-radius: 8px;
            font-size: 15px;
            background: rgb(var(--v-theme-background-lighten-1));
            transition: background-color 0.15s;
            cursor: pointer;

            &:hover {
                background: rgb(var(--v-theme-background-lighten-2));
            }
        }
    }
}

</style>
<style lang="scss" scoped>

.route-container {
    height: 100vh !important;
    height: 100dvh !important;
    border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-background));  // Home Indicator 分浮かせる余白の背景色
    background: rgb(var(--v-theme-black)) !important;
    overflow: hidden;
    // タブレット横画面・スマホ横画面のみ Home Indicator 分浮かせる余白の背景色を rgb(var(--v-theme-black)) にする
    // 映像の左右の黒い余白と背景色を合わせる
    @include tablet-horizontal {
        border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-black));
    }
    @include smartphone-horizontal {
        border-bottom: env(safe-area-inset-bottom) solid rgb(var(--v-theme-black));
    }
}

.watch-container {
    display: flex;
    width: calc(100% + 352px);  // パネルの幅分はみ出す
    height: 100%;
    transition: width 0.4s cubic-bezier(0.26, 0.68, 0.55, 0.99);
    @include tablet-vertical {
        flex-direction: column;
        width: 100%;
    }
    @include smartphone-horizontal {
        width: calc(100% + 310px); // パネルの幅分はみ出す
    }
    @include smartphone-vertical {
        flex-direction: column;
        width: 100%;
    }

    // コントロール表示時
    &.watch-container--control-display {
        .watch-content {
            cursor: auto !important;
        }
        .watch-navigation, .watch-header {
            opacity: 1 !important;
            visibility: visible !important;
        }
        // :deep() で子コンポーネントにも CSS が効くようにする
        // ref: https://qiita.com/buntafujikawa/items/b1703a2a4344fd326fe0
        .watch-player :deep() {
            .watch-player__button {
                opacity: 1 !important;
                visibility: visible !important;
            }
        }
    }

    // パネル表示時
    &.watch-container--panel-display {
        width: 100%;  // 画面幅に収めるように

        // パネルアイコンをハイライト
        .switch-button-panel .switch-button-icon {
            color: rgb(var(--v-theme-primary));
        }

        // タッチデバイスのみ、content-visibility: visible で明示的にパネルを描画する
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }
    @include tablet-vertical {
        width: 100%;
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }
    @include smartphone-vertical {
        width: 100%;
        .watch-panel {
            @media (hover: none) {
                content-visibility: auto;
            }
        }
    }

    // フルスクリーン時
    &.watch-container--fullscreen {

        // ナビゲーションを非表示
        .watch-navigation {
            display: none;
        }
        // ナビゲーションの分の余白を削除
        .watch-content {
            .watch-header {
                padding-left: 30px;
                @include tablet-vertical {
                    padding-left: 16px;
                }
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
                @include smartphone-horizontal {
                    padding-left: 16px;
                }
            }
        }
    }

    .watch-content {
        display: flex;
        position: relative;
        width: 100%;
        cursor: none;
        @include smartphone-vertical {
            z-index: 5;  // スマホ縦画面のみ、シークバーのつまみを少しはみ出るように配置する
        }
    }
}

</style>
