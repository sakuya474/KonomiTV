<template>
    <div class="bd-panel">
        <!-- BDタイトル表示 -->
        <div class="bd-panel__title" v-if="title">
            {{ title }}
        </div>

        <div class="bd-panel__chapters">
            <template v-if="Array.isArray(chapters) && chapters.length > 0">
                <!-- 階層構造のチャプターリスト -->
                <div v-for="titleGroup in chapters" :key="titleGroup.Title" class="chapter-title-group">
                    <div class="chapter-title" @click="handleChapterClick(titleGroup)">
                        <span class="chapter-title__text">{{ titleGroup.Title }}</span>
                        <span class="chapter-title__time">{{ formatTime(getTitleGroupTime(titleGroup)) }}</span>
                    </div>
                    <div v-if="Array.isArray(titleGroup.Chapters) && titleGroup.Chapters.length > 0" class="chapter-list">
                        <div v-for="(chapter, index) in titleGroup.Chapters" :key="chapter.ChapterIndex || chapter.Title || index" class="chapter-item" @click="handleChapterClick(chapter, titleGroup, index)">
                            <span class="chapter-item__number">Chapter {{ String(index + 1).padStart(2, '0') }}</span>
                            <span class="chapter-item__title" v-if="chapter.Title && chapter.Title !== `Chapter ${String(index + 1).padStart(2, '0')}`">{{ chapter.Title }}</span>
                            <span class="chapter-item__time" v-if="chapter.StartTime">{{ formatTime(chapter.StartTime) }}</span>
                        </div>
                    </div>
                </div>
            </template>
            <div v-else class="no-chapters">
                チャプター情報がありません
            </div>
        </div>
    </div>
</template>
<script lang="ts">
import { defineComponent, PropType } from 'vue';

export default defineComponent({
    name: 'Panel-BDLibraryPanelContent',
    props: {
        title: { type: String, required: false, default: '' },
        chapters: { type: Array as PropType<any[]>, required: true },
    },
    emits: ['seek'],
    setup(props, { emit }) {
        function handleChapterClick(chapter: any, titleGroup?: any, chapterIndex?: number) {
            // メインタイトルの場合、getTitleGroupTimeを使用して時間を取得
            let startTime = chapter.StartTime || chapter.startTime;
            if (!startTime) {
                startTime = getTitleGroupTime(chapter);
            }

            if (chapter && startTime != null) {
                const seconds = Number(startTime);
                if (!isNaN(seconds)) {
                    // カスタムメッセージを生成
                    let message = '';
                    if (chapter.Title && Array.isArray(chapter.Chapters)) {
                        // メインタイトルの場合
                        message = `${chapter.Title}まで移動しました`;
                    } else if (titleGroup && chapterIndex !== undefined) {
                        // チャプターの場合
                        const titleName = titleGroup.Title || props.title || 'タイトル';
                        const chapterNumber = String(chapterIndex + 1).padStart(2, '0');
                        message = `${titleName}のチャプター${chapterNumber}まで移動しました`;
                    } else {
                        // デフォルトメッセージ
                        message = 'チャプターまで移動しました';
                    }

                    emit('seek', seconds, message);
                }
            }
        }

                function formatTime(seconds: number | string | null | undefined): string {
            if (seconds == null || seconds === '') return '--:--';
            const num = Number(seconds);
            if (isNaN(num)) return '--:--';

            const hours = Math.floor(num / 3600);
            const minutes = Math.floor((num % 3600) / 60);
            const secs = Math.floor(num % 60);

            if (hours > 0) {
                return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
            } else {
                return `${minutes}:${secs.toString().padStart(2, '0')}`;
            }
        }

        function getTitleGroupTime(titleGroup: any): number | string | null | undefined {
            // まず、titleGroup自体のStartTimeを確認
            if (titleGroup.StartTime || titleGroup.startTime) {
                return titleGroup.StartTime || titleGroup.startTime;
            }

            // titleGroupにStartTimeがない場合、最初のチャプターのStartTimeを使用
            if (Array.isArray(titleGroup.Chapters) && titleGroup.Chapters.length > 0) {
                const firstChapter = titleGroup.Chapters[0];
                if (firstChapter && (firstChapter.StartTime || firstChapter.startTime)) {
                    return firstChapter.StartTime || firstChapter.startTime;
                }
            }

            // それでも時間がない場合は、0を返す（開始時間として）
            return 0;
        }



        return { handleChapterClick, formatTime, getTitleGroupTime };
    },
});
</script>
<style lang="scss" scoped>

.bd-panel {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgb(var(--v-theme-background));
    overflow-y: auto;
    overflow-x: hidden;
    -webkit-overflow-scrolling: touch;
}

.bd-panel__title {
    font-size: 16px;
    font-weight: 600;
    color: rgb(var(--v-theme-text));
    padding: 20px 24px 16px 24px;
    border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
    line-height: 1.4;
}

.bd-panel__chapters {
    padding: 16px 0;
}

.chapter-title-group {
    margin-bottom: 16px;
}

.chapter-title {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-weight: bold;
    font-size: 16px;
    margin-bottom: 8px;
    padding: 8px 12px;
    background: rgba(255,255,255,0.05);
    border-radius: 6px;
    cursor: pointer;
    color: rgb(var(--v-theme-text));
    transition: all 0.2s;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    border: 1px solid rgba(255,255,255,0.1);

    &:hover {
        background: rgba(255,255,255,0.1);
        color: rgb(var(--v-theme-primary));
    }

    &:active {
        background: rgba(255,255,255,0.15);
        color: rgb(var(--v-theme-primary));
    }

    .chapter-title__text {
        flex: 1;
    }

    .chapter-title__time {
        font-size: 12px;
        color: rgba(var(--v-theme-text), 0.6);
        font-weight: 500;
        margin-left: auto;
        text-align: right;
        min-width: 60px;
    }
}

.chapter-list {
    margin-left: 8px;
    border-left: 2px solid rgba(255,255,255,0.1);
    padding-left: 12px;
}

.chapter-item {
    display: flex;
    align-items: center;
    gap: 8px;
    cursor: pointer;
    padding: 6px 8px;
    margin-bottom: 2px;
    border-radius: 4px;
    color: rgb(var(--v-theme-text));
    transition: all 0.2s;
    user-select: none;
    -webkit-tap-highlight-color: transparent;
    font-size: 14px;

    &:hover {
        background: rgba(255,255,255,0.05);
        color: rgb(var(--v-theme-primary));
    }

    &:active {
        background: rgba(255,255,255,0.1);
        color: rgb(var(--v-theme-primary));
    }

    .chapter-item__number {
        font-weight: 500;
        color: rgba(var(--v-theme-text), 0.7);
        min-width: 80px;
        font-size: 13px;
    }

    .chapter-item__title {
        flex: 1;
        font-weight: 400;
    }

    .chapter-item__time {
        font-size: 12px;
        color: rgba(var(--v-theme-text), 0.6);
        font-weight: 500;
        margin-left: auto;
        text-align: right;
        min-width: 50px;
    }
}

.no-chapters {
    display: flex;
    align-items: center;
    justify-content: center;
    height: 120px;
    color: rgb(var(--v-theme-text-lighten-2));
    font-size: 14px;
}

</style>
