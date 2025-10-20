<template>
  <div class="watch-panel">
    <div class="watch-panel__header">
      <div v-ripple class="panel-close-button" @click="handleClosePanel">
        <Icon class="panel-close-button__icon" icon="akar-icons:chevron-right" width="25px" />
        <span class="panel-close-button__text">閉じる</span>
      </div>
      <v-spacer></v-spacer>
    </div>
    <div class="watch-panel__content-container">
      <div class="bd-panel">
        <div class="bd-panel__chapters">
          <div class="bd-panel__title">{{ title }}</div>
          <template v-if="Array.isArray(chapters) && chapters.length > 0">
            <div v-for="titleGroup in chapters" :key="titleGroup.Title" class="chapter-title-group">
              <div class="chapter-title" @click="handleChapterClick(titleGroup)">{{ titleGroup.Title }}</div>
              <div v-if="Array.isArray(titleGroup.Chapters) && titleGroup.Chapters.length > 0" class="chapter-list">
                <div v-for="(chapter, index) in titleGroup.Chapters" :key="chapter.ChapterIndex || chapter.Title || index" class="chapter-item" @click="handleChapterClick(chapter, titleGroup, index)">
                  <span class="chapter-item__number">Chapter {{ String(index + 1).padStart(2, '0') }}</span>
                  <span class="chapter-item__title" v-if="chapter.Title">{{ chapter.Title }}</span>
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
    </div>
  </div>
</template>
<script lang="ts">
import { defineComponent, PropType } from 'vue';
import { mapStores } from 'pinia';

import usePlayerStore from '@/stores/PlayerStore';

export default defineComponent({
  name: 'Panel-BDLibrary',
  props: {
    title: { type: String, required: false, default: '' },
    chapters: { type: Array as PropType<any[]>, required: true },
  },
  emits: ['seek'],
  computed: {
    ...mapStores(usePlayerStore),
  },
  setup(props, { emit }) {
    function handleChapterClick(chapter: any, titleGroup?: any, chapterIndex?: number) {
      if (chapter && chapter.StartTime != null) {
        const seconds = Number(chapter.StartTime);
        if (!isNaN(seconds)) {
          // カスタムメッセージを生成
          let message = '';
          if (chapter.Title && Array.isArray(chapter.Chapters)) {
            // メインタイトルの場合
            message = `「${chapter.Title}」まで移動しました`;
          } else if (titleGroup && chapterIndex !== undefined) {
            // チャプターの場合
            const titleName = titleGroup.Title || props.title || 'タイトル';
            const chapterNumber = String(chapterIndex + 1).padStart(2, '0');
            message = `「${titleName}」のチャプター${chapterNumber}まで移動しました`;
          } else {
            // デフォルトメッセージ
            message = 'チャプターまで移動しました';
          }

          // イベントを発火して親コンポーネントにシーク命令を送信
          emit('seek', seconds, message);
        }
      }
    }

    function formatTime(seconds: number): string {
      const hours = Math.floor(seconds / 3600);
      const minutes = Math.floor((seconds % 3600) / 60);
      const secs = Math.floor(seconds % 60);

      if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      } else {
        return `${minutes}:${secs.toString().padStart(2, '0')}`;
      }
    }

    return { handleChapterClick, formatTime };
  },
  methods: {
    handleClosePanel() {
      this.playerStore.is_panel_display = false;
    },
  },
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
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 8px;
      color: rgb(var(--v-theme-on-surface));
      cursor: pointer;
      transition: background-color 0.2s;

      &:hover {
        background: rgba(var(--v-theme-on-surface), 0.08);
      }

      .panel-close-button__icon {
        color: rgb(var(--v-theme-on-surface));
      }

      .panel-close-button__text {
        font-size: 14px;
        font-weight: 500;
      }
    }

    .panel-bd-info {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      gap: 4px;

      .panel-bd-info__title {
        font-size: 14px;
        font-weight: 600;
        color: rgb(var(--v-theme-on-surface));
        text-align: right;
        max-width: 200px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .panel-bd-info__type {
        font-size: 12px;
        color: rgb(var(--v-theme-primary));
        font-weight: 500;
      }
    }
  }

  .watch-panel__content-container {
    position: relative;
    height: 100%;
  }
}

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

.bd-panel__chapters {
  padding: 16px;
}

.bd-panel__title {
  font-size: 18px;
  font-weight: bold;
  color: rgb(var(--v-theme-on-surface));
  margin-bottom: 16px;
  padding-bottom: 8px;
  border-bottom: 2px solid rgba(255,255,255,0.2);
}

.chapter-title-group {
  margin-bottom: 16px;
}

.chapter-title {
  font-weight: bold;
  font-size: 16px;
  margin-bottom: 8px;
  padding: 8px 12px;
  background: rgba(255,255,255,0.05);
  border-radius: 6px;
  cursor: pointer;
  color: rgb(var(--v-theme-on-surface));
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
  color: rgb(var(--v-theme-on-surface));
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
    color: rgba(var(--v-theme-on-surface), 0.7);
    min-width: 80px;
    font-size: 13px;
  }

  .chapter-item__title {
    flex: 1;
    font-weight: 400;
  }

  .chapter-item__time {
    font-size: 12px;
    color: rgba(var(--v-theme-on-surface), 0.6);
    font-weight: 500;
    min-width: 50px;
    text-align: right;
  }
}

.no-chapters {
  text-align: center;
  color: rgba(var(--v-theme-on-surface), 0.6);
  font-style: italic;
  padding: 20px;
}
</style>

