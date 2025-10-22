<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="videos-home-container-wrapper">
                <SPHeaderBar />
                <div class="videos-home-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '録画を見る', path: '/videos/', disabled: true },
                    ]" />
                    <RecordedProgramList
                        class="videos-home-container__programs"
                        :class="{'videos-home-container__programs--loading': programs.length === 0 && is_loading}"
                        title="録画番組一覧"
                        :programs="programs"
                        :total="total_programs"
                        :page="current_page"
                        :sortOrder="sort_order"
                        :hidePagination="false"
                        :hideSort="false"
                        :showMoreButton="false"
                        :showSearch="false"
                        :isLoading="is_loading"
                        :showEmptyMessage="!is_loading"
                        @update:page="updatePage"
                        @update:sortOrder="updateSortOrder" />
                </div>
            </div>
        </main>
         <!-- エンコード進捗表示 -->
         <TSReplaceEncodingProgress
            ref="encodingProgress"
            @completed="handleEncodingCompleted"
            @failed="handleEncodingFailed"
            @cancelled="handleEncodingCancelled" />
    </div>
</template>
<script lang="ts" setup>

import { onMounted, ref, onUnmounted } from 'vue';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import TSReplaceEncodingProgress from '@/components/Videos/TSReplaceEncodingProgress.vue';
import Message from '@/message';
import { IRecordedProgram, SortOrder, MylistSortOrder } from '@/services/Videos';
import Videos from '@/services/Videos';
import useUserStore from '@/stores/UserStore';

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 並び順
const sort_order = ref<SortOrder>('desc');

// エンコード進捗表示の参照
const encodingProgress = ref<InstanceType<typeof TSReplaceEncodingProgress>>();

// 録画番組を取得
const fetchPrograms = async () => {
    const result = await Videos.fetchVideos(sort_order.value, current_page.value);
    if (result) {
        programs.value = result.recorded_programs;
        total_programs.value = result.total;
    }
    is_loading.value = false;
};

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
    is_loading.value = true;
    await fetchPrograms();
};

// 並び順を更新
const updateSortOrder = async (order: SortOrder | MylistSortOrder) => {
    sort_order.value = order as SortOrder;
    current_page.value = 1;  // ページを1に戻す
    is_loading.value = true;
    await fetchPrograms();
};

// TSReplaceエンコード完了イベントを監視
const handleTSReplaceEncodingCompleted = async () => {
    // 録画番組リストを再取得してメタデータの変更を反映
    await fetchPrograms();
};

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    // 録画番組を取得
    await fetchPrograms();

    // TSReplaceエンコード完了イベントのリスナーを追加
    window.addEventListener('tsreplace-encoding-completed', handleTSReplaceEncodingCompleted);
});

// コンポーネントのクリーンアップ
onUnmounted(() => {
    // イベントリスナーを削除
    window.removeEventListener('tsreplace-encoding-completed', handleTSReplaceEncodingCompleted);
});

// エンコード完了時の処理
const handleEncodingCompleted = (taskId: string) => {
    Message.success('エンコードが完了しました。録画一覧を更新します。');
    // 録画一覧を再取得してメタデータの変更を反映
    fetchPrograms();
};

// エンコード失敗時の処理
const handleEncodingFailed = (taskId: string, error: string) => {
    Message.error(`エンコードが失敗しました: ${error}`);
};

// エンコードキャンセル時の処理
const handleEncodingCancelled = (taskId: string) => {
    Message.info('エンコードがキャンセルされました。');
};

</script>
<style lang="scss" scoped>

.videos-home-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.videos-home-container {
    display: flex;
    flex-direction: column;
    width: 100%;
    height: 100%;
    padding: 20px;
    margin: 0 auto;
    min-width: 0;
    max-width: 1000px;
    @include smartphone-horizontal {
        padding: 16px 20px !important;
    }
    @include smartphone-horizontal-short {
        padding: 16px 16px !important;
    }
    @include smartphone-vertical {
        padding-top: 8px !important;
        padding-left: 8px !important;
        padding-right: 8px !important;
        padding-bottom: 20px !important;
    }

    &__programs.videos-home-container__programs--loading {
        // ローディング中にちらつかないように
        :deep(.recorded-program-list__grid) {
            height: calc(125px * 10);
            @include smartphone-vertical {
                height: calc(100px * 10);
            }
        }
    }
}

/* Vuetifyの v-row の負のマージンで左右にズレるのを抑止 */
.container-fix :deep(.v-row) {
  margin-left: 0 !important;
  margin-right: 0 !important;
}
.container-fix :deep(.v-col) {
  padding-left: 0 !important;
  padding-right: 0 !important;
}

</style>