<template>
  <div ref="playerContainer" class="watch-player" :class="{
    'watch-player--loading': false,
    'watch-player--virtual-keyboard-display': false,
    'watch-player--video': true,
    'watch-player--pure-black': true,
  }">
    <div class="watch-player__background-wrapper">
      <div class="watch-player__background" :class="{
        'watch-player__background--display': false,
        'watch-player__background--background-hide': true,
      }">
        <img class="watch-player__background-logo" src="/assets/images/logo.svg">
      </div>
    </div>
    <v-progress-circular indeterminate size="60" width="6" class="watch-player__buffering"
      :class="{'watch-player__buffering--display': false}">
    </v-progress-circular>
    <div class="watch-player__dplayer"></div>
    <div class="watch-player__dplayer-setting-cover"
      :class="{'watch-player__dplayer-setting-cover--display': false}"
      @click="handleSettingCoverClick"></div>

    <slot />
  </div>
</template>
<script lang="ts">
import { defineComponent, onMounted, onBeforeUnmount, ref, watch, nextTick, computed } from 'vue';
import usePlayerStore from '@/stores/PlayerStore';

import BDLibraryPlayerController from '@/services/player/BDLibraryPlayerController';
import { IBDLibraryItem } from '@/services/BDLibrary';
import Utils from '@/utils';

export default defineComponent({
    name: 'BDLibraryPlayer',
    props: {
        m3u8Path: {
            type: String,
            required: true,
        },
        isUiVisible: {
            type: Boolean,
            required: true,
        },
        audioTracks: {
            type: Array,
            required: false,
            default: () => [],
        },
        subtitleTracks: {
            type: Array,
            required: false,
            default: () => [],
        },
        qualities: {
            type: Array,
            required: false,
            default: () => [],
        },
        selectedAudio: {
            type: [String, Number],
            required: false,
            default: null,
        },
        selectedSubtitle: {
            type: [String, Number],
            required: false,
            default: null,
        },
        selectedQuality: {
            type: String,
            required: false,
            default: null,
        },
        defaultQuality: {
            type: Number,
            required: false,
            default: 0,
        },
        onAudioChange: {
            type: Function,
            required: false,
        },
        onSubtitleChange: {
            type: Function,
            required: false,
        },
        onQualityChange: {
            type: Function,
            required: false,
        },
        bdItem: {
            type: Object as () => IBDLibraryItem | null,
            required: false,
            default: null,
        },
    },
    emits: ['open-menu', 'ui-interaction'],
    setup(props, { expose }) {
        const playerContainer = ref<HTMLDivElement | null>(null);
        let controller: BDLibraryPlayerController | null = null;
        const playerStore = usePlayerStore();
        const isSubtitleOn = ref(true);

        // m3u8パスを選択内容に応じて生成
        const computedM3u8Path = computed(() => {
            let url = props.m3u8Path;
            // 画質切替: /original/ の部分を /{selectedQuality}/ に置換
            if (props.selectedQuality && props.selectedQuality !== 'original') {
                url = url.replace('/original/', `/${props.selectedQuality}/`);
            }
            // 音声・字幕: ?audio=xx&subtitle=yy をクエリに追加
            const params: string[] = [];
            if (props.selectedAudio) params.push(`audio=${props.selectedAudio}`);
            if (props.selectedSubtitle) params.push(`subtitle=${props.selectedSubtitle}`);
            if (params.length > 0) {
                url += (url.includes('?') ? '&' : '?') + params.join('&');
            }
            return url;
        });

        async function initPlayer() {
            if (playerContainer.value) {
                if (controller) controller.destroy();
                controller = new BDLibraryPlayerController(props.m3u8Path, props.qualities || [], props.defaultQuality || 0, null);
                await controller.init(playerContainer.value, props.audioTracks || [], props.subtitleTracks || []);

                // 録画視聴と同じ『プレーヤー再起動』ボタンを追加
                const rightIcons = playerContainer.value.querySelector('.dplayer-icons.dplayer-icons-right');
                if (rightIcons && !rightIcons.querySelector('.dplayer-player-restart-icon')) {
                    const restartMarkup = `
                        <div class="dplayer-icon dplayer-player-restart-icon" aria-label="プレイヤーを再起動" data-balloon-nofocus="" data-balloon-pos="up">
                            <span class="dplayer-icon-content">
                                <svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24"><path fill="currentColor" d="M12 5V3.21c0-.45-.54-.67-.85-.35l-2.8 2.79c-.2.2-.2.51 0 .71l2.79 2.79c.32.31.86.09.86-.36V7c3.31 0 6 2.69 6 6c0 2.72-1.83 5.02-4.31 5.75c-.42.12-.69.52-.69.95c0 .65.62 1.16 1.25.97A7.991 7.991 0 0 0 20 13c0-4.42-3.58-8-8-8zm-6 8c0-1.34.44-2.58 1.19-3.59c.3-.4.26-.95-.09-1.31c-.42-.42-1.14-.38-1.5.1a7.991 7.991 0 0 0 4.15 12.47c.63.19 1.25-.32 1.25-.97c0-.43-.27-.83-.69-.95C7.83 18.02 6 15.72 6 13z"/></svg>
                            </span>
                        </div>
                    `;
                    // いったん先頭に追加（後で順序を監視して入れ替える）
                    rightIcons.insertAdjacentHTML('afterbegin', restartMarkup);
                    rightIcons.querySelector('.dplayer-player-restart-icon')?.addEventListener('click', async () => {
                        // 現在の画質・再生位置・速度を取得
                        const current_quality = (controller as any)?.player?.qualityIndex ? (controller as any).player.options.video.quality[(controller as any).player.qualityIndex] : null;
                        const current_rate = (controller as any)?.player?.video?.playbackRate ?? null;
                        const current_time = (controller as any)?.player?.video?.currentTime ?? null;
                        // 再初期化
                        await initPlayer();
                        // 画質・速度・時間を可能なら復元
                        setTimeout(() => {
                            try {
                                if ((controller as any)?.player && current_quality) {
                                    const qIndex = (controller as any).player.options.video.quality.findIndex((q: any) => q.name === current_quality.name);
                                    if (qIndex >= 0) (controller as any).player.switchQuality(qIndex);
                                }
                                if ((controller as any)?.player && current_rate) (controller as any).player.speed(current_rate);
                                if (current_time != null) controller?.seek(current_time);
                            } catch {}
                        }, 300);
                    });

                    // 字幕ボタンと再起動ボタンの順序を監視・強制（再起動 -> 字幕）
                    const ensureOrder = () => {
                        const restartEl = rightIcons.querySelector('.dplayer-player-restart-icon') as HTMLElement | null;
                        const subtitleEl = rightIcons.querySelector('.bdlibrary-subtitle-toggle') as HTMLElement | null;
                        if (rightIcons && restartEl && subtitleEl) {
                            // restart を subtitle の直前へ
                            if (subtitleEl.previousElementSibling !== restartEl) {
                                rightIcons.insertBefore(restartEl, subtitleEl);
                            }
                        }
                    };
                    // 初回即時&数秒ポーリング（字幕ボタンが後から追加されるケースに対応）
                    ensureOrder();
                    let tries = 0;
                    const orderInterval = window.setInterval(() => {
                        ensureOrder();
                        if (++tries > 20) window.clearInterval(orderInterval);
                    }, 300);
                    // MutationObserver でも監視（DPlayerの再描画に対応）
                    const mo = new MutationObserver(() => ensureOrder());
                    mo.observe(rightIcons, { childList: true });
                }
            }
        }

        function seek(seconds: number) {
            if (controller) {
                controller.seek(seconds);
            }
        }

        // UI表示/非表示をDPlayerに伝える
        watch(() => props.isUiVisible, (visible) => {
            if (controller) {
                if (visible) {
                    // コントローラー表示/非表示の制御はDPlayerが自動で行う
                    console.log('Controller visibility control is handled automatically by DPlayer');
                }
            }
        }, { immediate: true });

        // 画質・音声・字幕選択が変わったら再初期化
        watch(computedM3u8Path, () => {
            nextTick(async () => {
                await initPlayer();
            });
        });

        expose({ seek });

        onMounted(async () => {
            await initPlayer();
            // パネルからのシーク要求
            playerStore.event_emitter.off('SeekTo');
            playerStore.event_emitter.on('SeekTo', ({ seconds }) => {
                controller?.seek(seconds);
                // コントローラー表示/非表示の制御はDPlayerが自動で行う
            });
        });

        watch(() => props.m3u8Path, (newVal, oldVal) => {
            if (newVal && newVal !== oldVal) {
                nextTick(async () => {
                    await initPlayer();
                });
            }
        });

        onBeforeUnmount(() => {
            if (controller) {
                controller.destroy();
                controller = null;
            }
        });


        // watch-player__dplayer-setting-cover がクリックされたとき、設定パネルを閉じる
        const handleSettingCoverClick = () => {
            const dplayer_mask = document.querySelector<HTMLDivElement>('.dplayer-mask');
            if (dplayer_mask) {
                // dplayer-mask をクリックすることで、player.setting.hide() が内部的に呼び出され、設定パネルが閉じられる
                dplayer_mask.click();
            }
        };

        return {
            playerContainer, isSubtitleOn,
            handleSettingCoverClick, Utils,
        };
    },
});
</script>
<style lang="scss" scoped>
@import '@/styles/mixin.scss';
.watch-player {
  display: flex;
  position: relative;
  width: 100%;
  height: 100%;
  background-size: contain;
  background-position: center;
  &.watch-player--pure-black {
    background-color: #000000;
  }
  @media (min-width: 600.1px) and (max-width: 1280px) and (orientation: portrait) {
    aspect-ratio: 16 / 9;
  }
  @media (max-width: 600px) and (orientation: portrait) {
    aspect-ratio: 16 / 9;
  }

  &.watch-player--video {
    .watch-player__button {
      right: 0px;
      .switch-button {
        border-top-right-radius: 0px;
        border-bottom-right-radius: 0px;
      }
    }
  }
}

.watch-player__background-wrapper {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;

  .watch-player__background {
    position: relative;
    top: 50%;
    left: 50%;
    max-height: 100%;
    aspect-ratio: 16 / 9;
    transform: translate(-50%, -50%);
    background-blend-mode: overlay;
    background-color: rgba(14, 14, 18, 0.35);
    background-size: cover;
    background-image: none;
    opacity: 0;
    visibility: hidden;
    transition: opacity 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94), visibility 0.4s cubic-bezier(0.4, 0.38, 0.49, 0.94);
    will-change: opacity;

    &--display {
      opacity: 1;
      visibility: visible;
    }
    &--background-hide {
      background-image: none !important;
      background-color: #101010;
    }

    .watch-player__background-logo {
      display: inline-block;
      position: absolute;
      height: 34px;
      right: 56px;
      bottom: 44px;
      filter: drop-shadow(0px 0px 5px rgb(var(--v-theme-black)));

      @media (max-width: 1024px) and (orientation: portrait) {
        height: 30px;
        right: 34px;
        bottom: 30px;
      }
      @media (max-width: 768px) and (orientation: landscape) {
        height: 25px;
        right: 30px;
        bottom: 24px;
      }
      @media (max-width: 768px) and (orientation: portrait) {
        height: 22px;
        right: 30px;
        bottom: 24px;
      }
    }
  }
}

.watch-player__buffering {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 10;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s, visibility 0.3s;

  &--display {
    opacity: 1;
    visibility: visible;
  }
}

.watch-player__dplayer {
  width: 100%;
  height: 100%;
  @media (max-width: 768px) and (orientation: portrait) {
    overflow: visible !important;
  }
  svg circle, svg path {
    fill: rgb(var(--v-theme-text)) !important;
  }
  .dplayer-video-wrap {
    background: transparent !important;
    .dplayer-video-wrap-aspect {
      transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
      opacity: 1;
    }
    .dplayer-danmaku {
      max-width: 100%;
      max-height: calc(100% - var(--comment-area-vertical-margin, 0px));
      aspect-ratio: var(--comment-area-aspect-ratio, 16 / 9);
      transition: max-height 0.5s cubic-bezier(0.42, 0.19, 0.53, 0.87), aspect-ratio 0.5s cubic-bezier(0.42, 0.19, 0.53, 0.87);
      will-change: aspect-ratio;
      overflow: hidden;
    }
    .dplayer-bml-browser {
      display: block;
      position: absolute;
      width: var(--bml-browser-width, 960px);
      height: var(--bml-browser-height, 540px);
      color: rgb(0, 0, 0);
      overflow: hidden;
      transform-origin: center;
      transform: scale(var(--bml-browser-scale-factor-width, 1), var(--bml-browser-scale-factor-height, 1));
      transition: opacity 0.2s cubic-bezier(0.4, 0.38, 0.49, 0.94);
      opacity: 1;
      aspect-ratio: 16 / 9;
    }
    .dplayer-danloading {
      display: none !important;
    }
    .dplayer-loading-icon {
      display: none !important;
    }
  }
  .dplayer-controller-mask {
    height: 82px !important;
  }
  .dplayer-controller {
    background: linear-gradient(transparent, rgba(0, 0, 0, 0.7)) !important;
    .dplayer-icons {
      .dplayer-icon {
        width: 32px !important;
        height: 32px !important;
        .dplayer-icon-content {
          width: 24px !important;
          height: 24px !important;
        }
      }
    }
  }

  // モバイルのみ適用されるスタイル（録画視聴プレーヤーと同じ）
  &.dplayer-mobile {
    .dplayer-controller {
      padding-left: calc(68px + 30px) !important;
      padding-right: calc(0px + 30px) !important;
      .dplayer-bar-wrap {
        bottom: 51px !important;
        width: calc(100% - 68px - (30px * 2)) !important;
        @include tablet-vertical {
          width: calc(100% - (18px * 2)) !important;
        }
        @include smartphone-horizontal {
          width: calc(100% - (18px * 2)) !important;
        }
        @include smartphone-vertical {
          // スマホ縦画面のみ、シークバーをプレイヤーの下辺に配置
          width: 100% !important;
          left: 0px !important;
          bottom: -6px !important;
          z-index: 100 !important;
        }
        .dplayer-thumb {
          // タッチデバイスのみ、コントロール表示時は常にシークバーのつまみを表示する
          @media (hover: none) {
            transform: scale(1) !important;
          }
        }
      }
      @include tablet-vertical {
        padding-left: calc(0px + 18px) !important;
        padding-right: calc(0px + 18px) !important;
      }
      @include smartphone-horizontal {
        padding-left: calc(0px + 18px) !important;
        padding-right: calc(0px + 18px) !important;
      }
      @include smartphone-vertical {
        padding-left: calc(0px + 18px) !important;
        padding-right: calc(0px + 18px) !important;
      }
    }
    &.dplayer-hide-controller .dplayer-controller {
      transform: none !important;
    }
  }

  // スマートフォン用のシークバースタイルを強制適用
  &.dplayer-mobile .dplayer-controller .dplayer-bar-wrap {
    @media (max-width: 600px) and (orientation: portrait) {
      width: 100% !important;
      left: 0px !important;
      bottom: -6px !important;
      z-index: 100 !important;
    }
  }

  // 狭小幅デバイスのみ適用されるスタイル
  &.dplayer-narrow {
    .dplayer-icons.dplayer-icons-right {
      right: 14px !important;
    }
  }
}

.watch-player__dplayer-setting-cover {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-color: rgba(0, 0, 0, 0.5);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s, visibility 0.3s;
  z-index: 50;

  &--display {
    @media (hover: none) {
      @media (max-width: 768px) and (orientation: portrait) {
        opacity: 1;
        visibility: visible;
      }
    }
  }
}

/* 非フルスクリーン時のDPlayer設定パネル（録画視聴UIと同じ） */
.watch-player__dplayer.dplayer-mobile {
  .dplayer-setting-box {
    @media (max-width: 768px) and (orientation: portrait) {
      /* スマホ縦画面かつ非フルスクリーン時のみ、設定パネルを画面下部にオーバーレイ配置 */
      position: fixed;
      left: 0px !important;
      right: 0px !important;
      bottom: env(safe-area-inset-bottom) !important;  /* iPhone X 以降の Home Indicator の高さ分 */
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


/* DPlayerの設定パネル内のカスタム項目のスタイル */
.dplayer-setting-box {
  .dplayer-setting-item {
    .bdlibrary-audio-select,
    .bdlibrary-subtitle-select {
      width: 100%;
      padding: 4px 8px;
      background: #1F1210C0;
      color: rgb(var(--v-theme-text));
      border: 1px solid #4F423FC0;
      border-radius: 4px;
      font-size: 0.9em;
      margin-top: 4px;

      &:disabled {
        color: #aaa;
        background: #222;
      }
    }
  }
}
</style>

<style>
/* BD視聴プレーヤー用のグローバルスタイル */
.watch-player__dplayer.dplayer-mobile .dplayer-controller .dplayer-bar-wrap {
  @media (max-width: 600px) and (orientation: portrait) {
    width: 100% !important;
    left: 0px !important;
    bottom: -6px !important;
    z-index: 100 !important;
  }
}
</style>