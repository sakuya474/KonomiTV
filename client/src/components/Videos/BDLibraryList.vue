<template>
    <div class="bd-library-list" :class="{'bd-library-list--show-sort': !hideSort}">
        <div class="bd-library-list__header" v-if="!hideHeader">
            <h2 class="bd-library-list__title">
                <div v-if="showBackButton" v-ripple class="bd-library-list__title-back" @click="$router.back()">
                    <Icon icon="fluent:chevron-left-12-filled" width="27px" />
                </div>
                <span class="bd-library-list__title-text">{{title}}</span>
                <div class="bd-library-list__title-count" v-if="!showMoreButton">
                    <template v-if="isSearching">
                        <Icon icon="line-md:loading-twotone-loop" class="mr-1 spin" width="20px" height="20px" />
                        <span>検索中...</span>
                    </template>
                    <template v-else>{{displayTotal}}件</template>
                </div>
            </h2>
            <div class="bd-library-list__actions">
                <v-select v-if="!hideSort"
                    v-model="sort_order"
                    :items="[
                        { title: '新しい順', value: 'added_desc' },
                        { title: '古い順', value: 'added_asc' },
                    ]"
                    item-title="title"
                    item-value="value"
                    class="bd-library-list__sort"
                    color="primary"
                    bg-color="background-lighten-1"
                    variant="solo"
                    density="comfortable"
                    hide-details
                    @update:model-value="$emit('update:sortOrder', $event)">
                </v-select>
                <v-btn v-if="showMoreButton"
                    variant="text"
                    class="bd-library-list__more"
                    @click="$emit('more')">
                    <span class="text-primary">もっと見る</span>
                    <Icon icon="fluent:chevron-right-12-regular" width="18px" class="ml-1 text-text-darken-1" style="margin: 0px -4px;" />
                </v-btn>
            </div>
        </div>
        <div class="bd-library-list__grid"
            :class="{
                'bd-library-list__grid--loading': isLoading || isSearching,
                'bd-library-list__grid--empty': displayTotal === 0 && showEmptyMessage,
                'bd-library-list__grid--searching': isSearching,
            }">
            <div class="bd-library-list__empty"
                :class="{
                    'bd-library-list__empty--show': displayTotal === 0 && showEmptyMessage && !isSearching,
                }">
                <div class="bd-library-list__empty-content">
                    <Icon class="bd-library-list__empty-icon" :icon="emptyIcon" width="54px" height="54px" />
                    <h2 v-html="emptyMessage"></h2>
                    <div class="bd-library-list__empty-submessage"
                        v-if="emptySubMessage" v-html="emptySubMessage"></div>
                </div>
            </div>
            <div class="bd-library-list__grid-content">
                <BDLibraryItem v-for="item in displayItems" :key="item.id" :item="item"
                    :forMylist="forMylist" :forWatchedHistory="forWatchedHistory" @deleted="handleItemDeleted" />
            </div>
        </div>
        <div class="bd-library-list__pagination" v-if="!hidePagination && displayTotal > 0">
            <v-pagination
                v-model="current_page"
                active-color="primary"
                density="comfortable"
                :length="Math.ceil(displayTotal / 31)"
                :total-visible="Utils.isSmartphoneVertical() ? 5 : 7"
                @update:model-value="$emit('update:page', $event)">
            </v-pagination>
        </div>
    </div>
</template>
<script lang="ts" setup>

import { ref, watch } from 'vue';
import { useRouter } from 'vue-router';

import BDLibraryItem from '@/components/Videos/BDLibraryItem.vue';
import Utils from '@/utils';

// BDライブラリアイテムの型定義
export interface IBDLibraryItem {
    id: string;
    bd_id: number;
    title: string;
    path: string;
    watched_at?: string;
    position?: number;
    duration?: number;
    added_at?: string;
}

// ソート順の型定義
export type BDLibrarySortOrder = 'added_desc' | 'added_asc';

const router = useRouter();

// Props
const props = withDefaults(defineProps<{
    title: string;
    items: IBDLibraryItem[];
    total: number;
    page?: number;
    sortOrder?: BDLibrarySortOrder;
    hideHeader?: boolean;
    hideSort?: boolean;
    hidePagination?: boolean;
    showMoreButton?: boolean;
    showBackButton?: boolean;
    showEmptyMessage?: boolean;
    emptyIcon?: string;
    emptyMessage?: string;
    emptySubMessage?: string;
    isLoading?: boolean;
    isSearching?: boolean;
    forMylist?: boolean;
    forWatchedHistory?: boolean;
}>(), {
    page: 1,
    sortOrder: 'added_desc',
    hideHeader: false,
    hideSort: false,
    hidePagination: false,
    showMoreButton: false,
    showBackButton: false,
    showEmptyMessage: true,
    emptyIcon: 'fluent:warning-20-regular',
    emptyMessage: 'BDが見つかりませんでした。',
    emptySubMessage: 'BDライブラリにBDが追加されているか確認してください。',
    isLoading: false,
    isSearching: false,
    forMylist: false,
    forWatchedHistory: false,
});

// Emits
defineEmits<{
    (e: 'update:page', page: number): void;
    (e: 'update:sortOrder', order: BDLibrarySortOrder): void;
    (e: 'more'): void;
}>();

// 現在のページ番号
const current_page = ref(props.page);

// 並び順
const sort_order = ref<BDLibrarySortOrder>(props.sortOrder);

// 内部で管理するアイテムリスト
const displayItems = ref<IBDLibraryItem[]>([...props.items]);
// 内部で管理する合計数
const displayTotal = ref<number>(props.total);

// props の page が変更されたら current_page を更新
watch(() => props.page, (newPage) => {
    current_page.value = newPage;
});

// props の sortOrder が変更されたら sort_order を更新
watch(() => props.sortOrder, (newOrder) => {
    sort_order.value = newOrder;
});

// props の items が変更されたら displayItems を更新
watch(() => props.items, (newItems) => {
    displayItems.value = [...newItems];
});

// props の total が変更されたら displayTotal を更新
watch(() => props.total, (newTotal) => {
    displayTotal.value = newTotal;
});

// BDアイテムが削除された時の処理
const handleItemDeleted = (id: string) => {
    // 内部のアイテムリストから削除されたアイテムを除外
    displayItems.value = displayItems.value.filter(item => item.id !== id);
    // 合計数を1減らす
    displayTotal.value--;
};

</script>
<style lang="scss" scoped>

.bd-library-list {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;

    &--show-sort {
        .bd-library-list__grid {
            @include smartphone-vertical {
                margin-top: 3px;
            }
        }
    }

    &__header {
        display: flex;
        align-items: center;
        @include smartphone-vertical {
            padding: 0px 8px;
        }
    }

    &__title {
        display: flex;
        align-items: center;
        position: relative;
        font-size: 24px;
        font-weight: 700;
        padding-top: 8px;
        padding-bottom: 20px;
        @include smartphone-vertical {
            font-size: 22px;
            padding-bottom: 16px;
        }

        &-back {
            display: none;
            position: absolute;
            left: -8px;
            padding: 6px;
            border-radius: 50%;
            color: rgb(var(--v-theme-text));
            cursor: pointer;
            @include smartphone-vertical {
                display: flex;
            }

            & + .bd-library-list__title-text {
                @include smartphone-vertical {
                    margin-left: 32px;
                }
            }
        }

        &-count {
            display: flex;
            align-items: center;
            flex-shrink: 0;
            padding-top: 8px;
            margin-left: 12px;
            font-size: 14px;
            font-weight: 400;
            color: rgb(var(--v-theme-text-darken-1));

            .spin {
                animation: spin 1.15s linear infinite;
            }

            @keyframes spin {
                from {
                    transform: rotate(0deg);
                }
                to {
                    transform: rotate(360deg);
                }
            }
        }
    }

    &__actions {
        display: flex;
        align-items: center;
        margin-left: auto;
        :deep(.v-field) {
            padding-right: 4px !important;
        }
        :deep(.v-field__input) {
            padding-left: 12px !important;
            padding-right: 0px !important;
        }

        .v-select {
            width: 143px;
        }
    }

    &__sort {
        :deep(.v-field__input) {
            font-size: 14px !important;
            padding-top: 6px !important;
            padding-bottom: 6px !important;
            min-height: unset !important;
        }
    }

    &__more {
        margin-bottom: 12px;
        padding: 0px 10px;
        font-size: 15px;
        letter-spacing: 0.05em;
        @include smartphone-vertical {
            margin-bottom: 6px;
        }
    }

    &__grid {
        display: flex;
        flex-direction: column;
        position: relative;
        width: 100%;
        background: rgb(var(--v-theme-background-lighten-1));
        border-radius: 8px;
        overflow: hidden;

        &--loading {
            .bd-library-list__grid-content {
                visibility: hidden;
                opacity: 0;
            }
        }
        &--empty {
            height: 100%;
            min-height: 200px;
        }
        &--searching {
            height: 100%;
        }

        .bd-library-list__grid-content {
            height: 100%;
            transition: visibility 0.2s ease, opacity 0.2s ease;
        }

        :deep(.bd-library-item) {
            // 最後の項目以外の下にボーダーを追加
            &:not(:last-child) > .bd-library-item__container {
                border-bottom: 1px solid rgb(var(--v-theme-background-lighten-2));
            }
        }
    }

    &__pagination {
        display: flex;
        justify-content: center;
        margin-top: 24px;
        @include smartphone-vertical {
            margin-top: 20px;
        }
    }

    &__empty {
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        display: flex;
        justify-content: center;
        align-items: center;
        flex-grow: 1;
        visibility: hidden;
        opacity: 0;
        transition: visibility 0.2s ease, opacity 0.2s ease;

        &--show {
            visibility: visible;
            opacity: 1;
        }

        &-content {
            text-align: center;

            .bd-library-list__empty-icon {
                color: rgb(var(--v-theme-text-darken-1));
            }

            h2 {
                font-size: 21px;
                text-align: center;
                @include tablet-vertical {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal {
                    font-size: 19px !important;
                }
                @include smartphone-horizontal-short {
                    font-size: 19px !important;
                }
                @include smartphone-vertical {
                    font-size: 19px !important;
                }
            }

            .bd-library-list__empty-submessage {
                margin-top: 8px;
                color: rgb(var(--v-theme-text-darken-1));
                font-size: 15px;
                text-align: center;
                @include tablet-vertical {
                    font-size: 13px !important;
                }
                @include smartphone-horizontal {
                    font-size: 13px !important;
                }
                @include smartphone-vertical {
                    font-size: 13px !important;
                    margin-top: 7px !important;
                    line-height: 1.65;
                }
            }
        }
    }
}

</style>