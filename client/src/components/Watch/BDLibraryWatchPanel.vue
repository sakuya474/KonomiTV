<template>
    <div class="watch-panel"
         @mousemove="playerStore.event_emitter.emit('SetControlDisplayTimer', {event: $event})">
        <div class="watch-panel__header">
            <div v-ripple class="panel-close-button" @click="handleClosePanel">
                <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
                <span class="panel-close-button__text">閉じる</span>
            </div>
            <v-spacer></v-spacer>

        </div>
        <div class="watch-panel__content-container">
            <BDLibraryPanelContent class="watch-panel__content watch-panel__content--active"
                :title="(bdLibraryStore as any).bdItem?.title ?? ''"
                :chapters="groupedChapters"
                @seek="(seconds, message) => seekToChapter(seconds, message)" />
        </div>
        <div class="watch-panel__navigation">
            <div v-ripple class="panel-navigation-button panel-navigation-button--active">
                <Icon class="panel-navigation-button__icon" icon="fa-solid:list" width="33px" />
                <span class="panel-navigation-button__text">チャプター</span>
            </div>
        </div>
    </div>
</template>
<script lang="ts">

import { mapStores } from 'pinia';
import { defineComponent, PropType } from 'vue';

import BDLibraryPanelContent from '@/components/Watch/Panel/BDLibraryPanelContent.vue';
import { useBDLibraryStore } from '@/stores/BDLibraryStore';
import usePlayerStore from '@/stores/PlayerStore';
import Utils from '@/utils';

export default defineComponent({
    name: 'BDLibraryWatch-Panel',
    components: {
        BDLibraryPanelContent,
    },
    props: {
        playback_mode: {
            type: String as PropType<'Live' | 'Video'>,
            required: true,
        },
    },
    data() {
        return {
            // ユーティリティをテンプレートで使えるように
            Utils: Object.freeze(Utils),
        };
    },
    computed: {
        ...mapStores(useBDLibraryStore, usePlayerStore),

        // チャプター情報をグループ化
        groupedChapters(): any[] {
            const store = this.bdLibraryStore as ReturnType<typeof useBDLibraryStore>;
            let chaptersToDisplay: any[] = [];

            // chaptersプロパティからチャプター情報を取得（優先）
            if (store.bdItem?.chapters && Array.isArray(store.bdItem.chapters) && store.bdItem.chapters.length > 0) {
                chaptersToDisplay = store.bdItem.chapters;
            }
            // titlesプロパティからチャプター情報を取得（フォールバック）
            else if (store.bdItem?.titles && Array.isArray(store.bdItem.titles) && store.bdItem.titles.length > 0) {
                const firstTitle = store.bdItem.titles[0];
                if (firstTitle && Array.isArray(firstTitle.chapters)) {
                    chaptersToDisplay = firstTitle.chapters;
                }
            }

            return chaptersToDisplay;
        }
    },

    methods: {
        // パネルを閉じる
        handleClosePanel() {
            this.playerStore.is_panel_display = false;
        },

        // チャプターにシークする
        seekToChapter(seconds: number, customMessage?: string) {
            const bdWatch = this.$parent?.$parent as any;
            if (bdWatch && typeof bdWatch.getBDPlayerController === 'function') {
                const controller = bdWatch.getBDPlayerController();
                if (controller && typeof controller.seek === 'function') {
                    controller.seek(seconds, customMessage);
                }
            }
        }
    }
});

</script>
<style lang="scss" scoped>

.watch-panel {
    display: flex;
    flex-direction: column;
    flex-shrink: 0;
    width: 352px;
    height: 100%;
    background: rgb(var(--v-theme-background));
    @include tablet-vertical {
        width: 100%;
        height: auto;
        flex-grow: 1;
    }
    @include smartphone-horizontal {
        width: 310px;
    }
    @include smartphone-vertical {
        width: 100%;
        height: auto;
        flex-grow: 1;
    }

    // タッチデバイスのみ、content-visibility: hidden でパネルを折り畳んでいるときの描画パフォーマンスを上げる
    @media (hover: none) {
        content-visibility: hidden;
    }

    .watch-panel__header {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        width: 100%;
        height: 70px;
        padding-left: 16px;
        padding-right: 16px;
        @include tablet-vertical {
            display: none;
        }
        @include smartphone-horizontal {
            display: none;
        }
        @include smartphone-vertical {
            display: none;
        }

        .panel-close-button {
            display: flex;
            position: relative;
            align-items: center;
            flex-shrink: 0;
            left: -4px;
            height: 35px;
            padding: 0 4px;
            border-radius: 5px;
            font-size: 16px;
            user-select: none;
            cursor: pointer;

            &__icon {
                position: relative;
                left: -4px;
            }
            &__text {
                font-weight: bold;
            }
        }

        .panel-broadcaster {
            display: flex;
            align-items: center;
            min-width: 0;
            margin-left: 16px;

            &__icon {
                display: inline-block;
                flex-shrink: 0;
                width: 43px;
                height: 24px;
                border-radius: 3px;
                background: linear-gradient(150deg, rgb(var(--v-theme-gray)), rgb(var(--v-theme-background-lighten-2)));
                object-fit: cover;
                user-select: none;
            }

            &__number {
                flex-shrink: 0;
                margin-left: 8px;
                font-size: 16px;
            }

            &__name {
                margin-left: 5px;
                font-size: 16px;
                overflow: hidden;
                white-space: nowrap;
                text-overflow: ellipsis;
                @include smartphone-horizontal {
                    font-size: 14px;
                }
            }
        }
    }

    .watch-panel__content-container {
        position: relative;
        height: 100%;

        .watch-panel__content {
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgb(var(--v-theme-background));
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;

            // スマホ・タブレット (タッチデバイス) ではアニメーションが重めなので、アニメーションを無効化
            // アクティブなタブ以外は明示的に描画しない
            @media (hover: none) {
                transition: none;
                content-visibility: hidden;
            }
            &--active {
                opacity: 1;
                z-index: 15;
                visibility: visible;
                content-visibility: auto;
            }
        }

        .watch-panel__content-remocon-button {
            display: flex;
            align-items: center;
            justify-content: center;
            position: absolute;
            right: 16px;
            bottom: 16px;
            width: 48px;
            height: 48px;
            border-radius: 50%;
            background: rgb(var(--v-theme-background-lighten-1));
            outline: none;
            transition: opacity 0.2s, visibility 0.2s;
            opacity: 0;
            visibility: hidden;
            z-index: 20;

            @media (hover: none) {
                transition: none;
            }
            &--active {
                opacity: 1;
                visibility: visible;
            }
        }
    }

    .watch-panel__navigation {
        display: flex;
        align-items: center;
        justify-content: space-evenly;
        flex-shrink: 0;
        height: 77px;
        background: rgb(var(--v-theme-background-lighten-1));
        @include tablet-vertical {
            height: 66px;
            background: rgb(var(--v-theme-background));
        }
        @include smartphone-horizontal {
            height: 34px;
        }
        @include smartphone-vertical {
            height: 50px;
            background: rgb(var(--v-theme-background));
        }

        .panel-navigation-button {
            display: flex;
            justify-content: center;
            align-items: center;
            flex-direction: column;
            width: 77px;
            height: 56px;
            padding: 6px 0px;
            border-radius: 5px;
            color: rgb(var(--v-theme-text));
            box-sizing: content-box;
            transition: color 0.3s;
            user-select: none;
            cursor: pointer;
            @include tablet-vertical {
                width: 100px;
                height: 56px;
                padding: 4px 0px;
                box-sizing: border-box;
            }
            @include smartphone-horizontal {
                height: 34px;
                padding: 5px 0px;
                box-sizing: border-box;
            }
            @include smartphone-vertical {
                height: 38px;
                padding: 6px 0px;
                box-sizing: border-box;
            }

            &--active {
                color: rgb(var(--v-theme-primary));
                .panel-navigation-button__icon {
                    color: rgb(var(--v-theme-primary));
                }
                @include tablet-vertical {
                    background: #5b2d3c;
                }
                @include smartphone-vertical {
                    background: #5b2d3c;
                }
            }

            &__icon {
                height: 34px;
                @include tablet-vertical {
                    color: rgb(var(--v-theme-text));
                }
                @include smartphone-vertical {
                    color: rgb(var(--v-theme-text));
                }
            }
            &__text {
                margin-top: 5px;
                font-size: 13px;
                @include tablet-vertical {
                    margin-top: 3px;
                    font-size: 12px;
                }
                @include smartphone-horizontal {
                    display: none;
                }
                @include smartphone-vertical {
                    display: none;
                }
            }
        }
    }
}

</style>