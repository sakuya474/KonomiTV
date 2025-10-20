<template>
    <router-link v-ripple class="bd-library-item"
        :to="`/bd-library/watch/${item.bd_id.toString()}`">
        <div class="bd-library-item__container">
            <div class="bd-library-item__thumbnail">
                <img class="bd-library-item__thumbnail-image" loading="lazy" decoding="async"
                    :src="`${Utils.api_base_url}/bd-library/${item.bd_id.toString()}/thumbnail`" @error="onThumbnailError">
                <div v-if="item.duration" class="bd-library-item__thumbnail-duration">{{formatDuration(item.duration)}}</div>
                <div v-if="item.position && item.duration" class="bd-library-item__thumbnail-progress">
                    <div class="bd-library-item__thumbnail-progress-bar"
                        :style="`width: ${(item.position / item.duration) * 100}%`">
                    </div>
                </div>
            </div>
            <div class="bd-library-item__content">
                <div class="bd-library-item__content-title">{{ item.title }}</div>
            </div>
            <!-- マイリスト追加ボタン（通常リスト時） -->
            <div v-if="!forMylist && !forWatchedHistory" v-ripple
                class="bd-library-item__mylist"
                :class="{'bd-library-item__mylist--added': isInMylist}"
                v-ftooltip="isInMylist ? 'マイリストから削除する' : 'マイリストに追加する'"
                @click.prevent.stop="onToggleMylist"
                @mousedown.prevent.stop="">
                <svg v-if="isInMylist" width="22px" height="22px" viewBox="0 0 16 16">
                    <path :fill="'#e91e63'" d="M14.046 3.486a.75.75 0 0 1-.032 1.06l-7.93 7.474a.85.85 0 0 1-1.188-.022l-2.68-2.72a.75.75 0 1 1 1.068-1.053l2.234 2.267l7.468-7.038a.75.75 0 0 1 1.06.032" />
                </svg>
                <svg v-else width="22px" height="22px" viewBox="0 0 15.2 15.2">
                    <path :fill="'#fff'" d="M8 2.5a.5.5 0 0 0-1 0V7H2.5a.5.5 0 0 0 0 1H7v4.5a.5.5 0 0 0 1 0V8h4.5a.5.5 0 0 0 0-1H8z" />
                </svg>
            </div>
            <div v-if="forMylist" v-ripple class="bd-library-item__mylist"
                v-ftooltip="'マイリストから削除する'"
                @click.prevent.stop="removeFromMylist"
                @mousedown.prevent.stop="">
                <svg width="22px" height="22px" viewBox="0 0 16 16">
                    <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0M6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0zM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5"></path>
                </svg>
            </div>
            <div v-if="forWatchedHistory" v-ripple class="bd-library-item__mylist"
                v-ftooltip="'視聴履歴から削除する'"
                @click.prevent.stop="removeFromWatchedHistory"
                @mousedown.prevent.stop="">
                <svg width="22px" height="22px" viewBox="0 0 16 16">
                    <path fill="currentColor" d="M7 3h2a1 1 0 0 0-2 0M6 3a2 2 0 1 1 4 0h4a.5.5 0 0 1 0 1h-.564l-1.205 8.838A2.5 2.5 0 0 1 9.754 15H6.246a2.5 2.5 0 0 1-2.477-2.162L2.564 4H2a.5.5 0 0 1 0-1zm1 3.5a.5.5 0 0 0-1 0v5a.5.5 0 0 0 1 0zM9.5 6a.5.5 0 0 0-.5.5v5a.5.5 0 0 0 1 0v-5a.5.5 0 0 0-.5-.5"></path>
                </svg>
            </div>
            <div class="bd-library-item__menu">
                <v-menu location="bottom end" :close-on-content-click="true">
                    <template v-slot:activator="{ props }">
                        <div v-ripple class="bd-library-item__menu-button"
                            v-bind="props"
                            @click.prevent.stop=""
                            @mousedown.prevent.stop="">
                            <svg width="19px" height="19px" viewBox="0 0 16 16">
                                <path fill="currentColor" d="M9.5 13a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0m0-5a1.5 1.5 0 1 1-3 0a1.5 1.5 0 0 1 3 0"/>
                            </svg>
                        </div>
                    </template>
                    <v-list density="compact" bg-color="background-lighten-1" class="bd-library-item__menu-list">
                        <v-list-item @click="playBD">
                            <template v-slot:prepend>
                                <Icon icon="fluent:play-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">BDを再生</v-list-item-title>
                        </v-list-item>
                        <v-list-item @click="showBDInfo">
                            <template v-slot:prepend>
                                <svg width="20px" height="20px" viewBox="0 0 16 16">
                                    <path fill="currentColor" d="M8.499 7.5a.5.5 0 1 0-1 0v3a.5.5 0 0 0 1 0zm.25-2a.749.749 0 1 1-1.499 0a.749.749 0 0 1 1.498 0M8 1a7 7 0 1 0 0 14A7 7 0 0 0 8 1M2 8a6 6 0 1 1 12 0A6 6 0 0 1 2 8"></path>
                                </svg>
                            </template>
                            <v-list-item-title class="ml-3">BD情報を表示</v-list-item-title>
                        </v-list-item>
                        <v-divider></v-divider>
                        <v-list-item @click="showDeleteConfirmation" class="bd-library-item__menu-list-item--danger">
                            <template v-slot:prepend>
                                <Icon icon="fluent:delete-24-regular" width="20px" height="20px" />
                            </template>
                            <v-list-item-title class="ml-3">BDを削除</v-list-item-title>
                        </v-list-item>
                    </v-list>
                </v-menu>
            </div>
        </div>
    </router-link>

    <!-- BD削除確認ダイアログ -->
    <v-dialog max-width="750" v-model="show_delete_confirmation">
        <v-card>
            <v-card-title class="d-flex justify-center pt-6 font-weight-bold">本当にBDを削除しますか？</v-card-title>
            <v-card-text class="pt-2 pb-0">
                <div class="delete-confirmation__file-path mb-4">{{ item.path }}</div>
                <div class="text-error-lighten-1 font-weight-bold">
                    このBDに関連するすべてのデータ (マイリスト / 視聴履歴を含む) が削除されます。<br>
                    元に戻すことはできません。本当にBDを削除しますか？
                </div>
            </v-card-text>
            <v-card-actions class="pt-4 px-6 pb-6">
                <v-spacer></v-spacer>
                <v-btn color="text" variant="text" @click="show_delete_confirmation = false">
                    <Icon icon="fluent:dismiss-20-regular" width="18px" height="18px" />
                    <span class="ml-1">キャンセル</span>
                </v-btn>
                <v-btn class="px-3" color="error" variant="flat" @click="deleteBD">
                    <Icon icon="fluent:delete-20-regular" width="18px" height="18px" />
                    <span class="ml-1">BDを削除</span>
                </v-btn>
            </v-card-actions>
        </v-card>
    </v-dialog>
</template>
<script lang="ts" setup>

import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';

import Message from '@/message';
import BDLibrary from '@/services/BDLibrary';
import { useBDLibraryHistoryStore } from '@/stores/BDLibraryHistoryStore';
import { useBDLibraryMylistStore } from '@/stores/BDLibraryMylistStore';
import useUserStore from '@/stores/UserStore';
import Utils from '@/utils';
import type { IBDLibraryItem } from './BDLibraryList.vue';

// Props
const props = withDefaults(defineProps<{
    item: IBDLibraryItem;
    forMylist?: boolean;
    forWatchedHistory?: boolean;
}>(), {
    forMylist: false,
    forWatchedHistory: false,
});

// Emits
const emit = defineEmits<{
    (e: 'deleted', id: string): void;
}>();

const router = useRouter();
const bdLibraryHistoryStore = useBDLibraryHistoryStore();
const bdLibraryMylistStore = useBDLibraryMylistStore();
const userStore = useUserStore();

// 削除確認ダイアログの表示状態
const show_delete_confirmation = ref(false);

const isInMylist = computed(() => {
    return bdLibraryMylistStore.mylist_items.some(item => item.bd_id === props.item.bd_id || Number(item.id) === props.item.bd_id);
});

// 日付をフォーマット
const formatDate = (date_string: string): string => {
    const date = new Date(date_string);
    return date.toLocaleDateString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
    });
};

// 進捗をフォーマット
const formatProgress = (position: number, duration: number): string => {
    if (duration === 0) return '0%';
    const percentage = Math.round((position / duration) * 100);
    return `${percentage}%`;
};


// 動画時間をフォーマット（録画と統一）
const formatDuration = (duration: number): string => {
    const hours = Math.floor(duration / 3600);
    const minutes = Math.floor((duration % 3600) / 60);
    const seconds = Math.floor(duration % 60);

    if (hours > 0) {
        return `${hours}:${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
        return `${minutes}:${seconds.toString().padStart(2, '0')}`;
    }
};

// サムネイルエラー時の処理
const onThumbnailError = (event: Event) => {
    const target = event.target as HTMLImageElement;
    target.src = '/assets/images/icon.svg';
};

// マイリスト追加/削除の切替（ログインチェック込み）
const onToggleMylist = async () => {
    // 最新のログイン状態を反映
    await userStore.fetchUser(true);
    const accessToken = Utils.getAccessToken();
    const isLoggedIn = userStore.is_logged_in && accessToken !== null;
    if (!isLoggedIn) {
        Message.error('マイリストを利用するにはログインが必要です。');
        return;
    }
    if (isInMylist.value) {
        await removeFromMylist();
    } else {
        try {
            await bdLibraryMylistStore.addToMylist({ id: props.item.bd_id, title: props.item.title, path: '' });
            Message.success('マイリストに追加しました。');
        } catch (e) {
            Message.error('マイリストの追加に失敗しました。');
        }
    }
};

// マイリストから削除
const removeFromMylist = async () => {
    // props.item.id は「マイリスト一覧」では mylist_id、通常一覧では bd_id を文字列化したもの
    // ストアから bd_id に紐づく mylist_id を解決してから削除する
    const candidate = bdLibraryMylistStore.mylist_items.find(item =>
        item.id === props.item.id || item.bd_id === props.item.bd_id
    );
    const mylistId = candidate ? candidate.id : props.item.id;
    try {
        await bdLibraryMylistStore.removeFromMylist(mylistId);
        Message.show('マイリストから削除しました。');
    } catch (e) {
        Message.error('マイリストの削除に失敗しました。');
        return;
    }
    // 一覧（forMylist=true）のときだけ、行を消すために親へ通知する
    if (props.forMylist === true) {
        emit('deleted', props.item.id);
    }
};

// 視聴履歴から削除
const removeFromWatchedHistory = async () => {
    await bdLibraryHistoryStore.removeHistory(props.item.id);
    Message.show('視聴履歴から削除しました。');
    if (props.forWatchedHistory === true) {
        emit('deleted', props.item.id);
    }
};

// BDを再生
const playBD = () => {
    router.push(`/bd-library/watch/${props.item.bd_id.toString()}`);
};

// BD情報を表示
const showBDInfo = () => {
    // BD情報表示の実装（必要に応じて）
    Message.info('BD情報表示機能は未実装です。');
};

// BD削除確認ダイアログを表示
const showDeleteConfirmation = () => {
    if (userStore.user === null || userStore.user.is_admin === false) {
        Message.error('BDを削除するには管理者権限が必要です。\n管理者アカウントでログインし直してください。');
        return;
    }
    show_delete_confirmation.value = true;
};

// BD削除
const deleteBD = async () => {
    show_delete_confirmation.value = false;

    const result = await BDLibrary.deleteBD(props.item.bd_id);
    if (result === true) {
        Message.success('BDを削除しました。');
        // 親コンポーネントに削除イベントを発行
        emit('deleted', props.item.id);
    }
};



</script>
<style lang="scss" scoped>

.bd-library-item {
    display: flex;
    position: relative;
    width: 100%;
    height: 125px;
    padding: 0px 16px;
    color: rgb(var(--v-theme-text));
    background: rgb(var(--v-theme-background-lighten-1));
    transition: background-color 0.15s;
    text-decoration: none;
    user-select: none;
    box-sizing: border-box;
    cursor: pointer;
    content-visibility: auto;
    contain-intrinsic-height: auto 125px;
    @include smartphone-vertical {
        height: auto;
        padding: 0px 9px;
        contain-intrinsic-height: auto 115px;
    }

    &:hover {
        background: rgb(var(--v-theme-background-lighten-2));
    }
    // タッチデバイスで hover を無効にする
    @media (hover: none) {
        &:hover {
            background: rgb(var(--v-theme-background-lighten-1));
        }
    }

    &__container {
        display: flex;
        align-items: center;
        width: 100%;
        height: 100%;
        padding: 12px 0px;
        @include smartphone-vertical {
            padding: 8px 0px;
        }
    }

    &__thumbnail {
        display: flex;
        align-items: center;
        flex-shrink: 0;
        aspect-ratio: 16 / 9;
        height: 100%;
        border-radius: 4px;
        overflow: hidden;
        position: relative;
        @include smartphone-vertical {
            width: 120px;
            height: auto;
            aspect-ratio: 3 / 2;
        }

        &-image {
            width: 100%;
            border-radius: 4px;
            aspect-ratio: 16 / 9;
            object-fit: cover;
            @include smartphone-vertical {
                aspect-ratio: 3 / 2;
            }
        }

        &-duration {
            position: absolute;
            right: 4px;
            bottom: 4px;
            padding: 3px 4px;
            border-radius: 2px;
            background: rgba(0, 0, 0, 0.7);
            color: #fff;
            font-size: 11px;
            line-height: 1;
            @include smartphone-vertical {
                font-size: 10.5px;
            }
        }

        &-progress {
            position: absolute;
            left: 0;
            right: 0;
            bottom: 0;
            height: 3px;
            background: rgba(0, 0, 0, 0.6);

            &-bar {
                height: 100%;
                background: rgb(var(--v-theme-secondary-lighten-1));
                transition: width 0.2s ease;
            }
        }
    }

    &__content {
        display: flex;
        align-items: center;
        flex-grow: 1;
        min-width: 0;  // magic!
        margin-left: 16px;
        margin-right: 40px;
        @include tablet-vertical {
            margin-right: 16px;
        }
        @include smartphone-horizontal {
            margin-right: 20px;
        }
        @include smartphone-vertical {
            margin-left: 12px;
            margin-right: 0px;
        }

        &-title {
            display: -webkit-box;
            font-size: 17px;
            font-weight: 600;
            font-feature-settings: "palt" 1;  // 文字詰め
            letter-spacing: 0.07em;  // 字間を少し空ける
            overflow: hidden;
            -webkit-line-clamp: 2;  // 2行までに制限
            -webkit-box-orient: vertical;
            @include tablet-vertical {
                font-size: 15px;
                line-height: 1.4;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
            @include smartphone-horizontal {
                font-size: 14px;
            }
            @include smartphone-vertical {
                margin-right: 12px;
                font-size: 13px;
                line-height: 1.4;
                -webkit-line-clamp: 2;  // 2行までに制限
            }
        }


    }

    &__mylist {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 38%;
        right: 12px;
        transform: translateY(-50%);
        width: 32px;
        height: 32px;
        color: #fff !important; // デフォルトは白
        border-radius: 50%;
        transition: color 0.15s ease, background-color 0.15s ease;
        user-select: none;
        cursor: pointer;
        @include tablet-vertical {
            right: 6px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
        }
        @include smartphone-horizontal {
            right: 6px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
        }
        @include smartphone-vertical {
            right: 4px;
            width: 28px;
            height: 28px;
            svg {
                width: 18px;
                height: 18px;
            }
        }

        &:before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            border-radius: inherit;
            background-color: currentColor;
            color: inherit;
            opacity: 0;
            transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
            pointer-events: none;
        }
        &:hover {
            color: rgb(var(--v-theme-text));
            &:before {
                opacity: 0.15;
            }
        }
        // タッチデバイスで hover を無効にする
        @media (hover: none) {
            &:hover {
                &:before {
                    opacity: 0;
                }
            }
        }
        &--added {
            color: #e91e63 !important; // 追加済みはピンク
        }
    }

    &__menu {
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        position: absolute;
        top: 65%;
        right: 12px;
        transform: translateY(-50%);
        cursor: pointer;
        @include tablet-vertical {
            right: 6px;
        }
        @include smartphone-horizontal {
            right: 6px;
        }
        @include smartphone-vertical {
            right: 4px;
        }

        &-button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 32px;
            height: 32px;
            color: rgb(var(--v-theme-text-darken-1));
            border-radius: 50%;
            transition: color 0.15s ease, background-color 0.15s ease;
            user-select: none;
            @include tablet-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-horizontal {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }
            @include smartphone-vertical {
                width: 28px;
                height: 28px;
                svg {
                    width: 18px;
                    height: 18px;
                }
            }

            &:before {
                content: "";
                position: absolute;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                border-radius: inherit;
                background-color: currentColor;
                color: inherit;
                opacity: 0;
                transition: opacity 0.2s cubic-bezier(0.4, 0, 0.6, 1);
                pointer-events: none;
            }
            &:hover {
                color: rgb(var(--v-theme-text));
                &:before {
                    opacity: 0.15;
                }
            }
            // タッチデバイスで hover を無効にする
            @media (hover: none) {
                &:hover {
                    &:before {
                        opacity: 0;
                    }
                }
            }
        }

        &-list {
            :deep(.v-list-item-title) {
                font-size: 14px !important;
            }

            :deep(.v-list-item) {
                min-height: 36px !important;
            }

            &-item--danger {
                color: rgb(var(--v-theme-error));
                &:hover {
                    background-color: rgb(var(--v-theme-error-container));
                }
            }
        }
    }
}

.delete-confirmation__file-path {
    font-family: monospace;
    font-size: 14px;
    color: rgb(var(--v-theme-text-darken-1));
    background-color: rgb(var(--v-theme-background-lighten-1));
    padding: 8px 12px;
    border-radius: 4px;
    word-break: break-all;
}

</style>