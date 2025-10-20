<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="watched-history-container-wrapper">
                <div class="watched-history-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '視聴履歴', path: '/watched-history/', disabled: true },
                    ]" />

                    <!-- タブ切り替え -->
                    <div class="tab-container">
                        <div class="tab-buttons" :style="{
                            '--tab-length': 2,
                            '--active-tab-index': activeTab === 'videos' ? 0 : 1,
                        }">
                            <button
                                :class="['tab-button', { 'active': activeTab === 'videos' }]"
                                @click="activeTab = 'videos'"
                            >
                                録画番組
                            </button>
                            <button
                                :class="['tab-button', { 'active': activeTab === 'bd' }]"
                                @click="activeTab = 'bd'"
                            >
                                BD
                            </button>
                            <div class="tab-highlight"></div>
                        </div>
                    </div>

                    <Swiper class="content-swiper" :space-between="32" :auto-height="true" :touch-start-prevent-default="false"
                        :observer="true" :observe-parents="true" :initial-slide="0"
                        @swiper="swiper_instance = $event"
                        @slide-change="activeTab = $event.activeIndex === 0 ? 'videos' : 'bd'">
                        <SwiperSlide>
                            <RecordedProgramList
                                title="視聴履歴"
                                :programs="programs"
                                :total="total_programs"
                                :page="current_page"
                                :hideSort="true"
                                :isLoading="is_loading"
                                :showBackButton="true"
                                :showEmptyMessage="!is_loading"
                                :emptyIcon="'fluent:history-20-regular'"
                                :emptyMessage="'まだ視聴履歴がありません。'"
                                :emptySubMessage="'録画番組を30秒以上みると、<br class=\'d-sm-none\'>視聴履歴に追加されます。'"
                                :forWatchedHistory="true"
                                @update:page="updatePage" />
                        </SwiperSlide>
                        <SwiperSlide>
                            <BDLibraryList
                                title="BD視聴履歴"
                                :items="bd_history_items"
                                :total="bd_history_total"
                                :page="bd_current_page"
                                :sortOrder="bd_sort_order"
                                :isLoading="bdLibraryHistoryStore.is_loading"
                                :showBackButton="true"
                                :showEmptyMessage="!bdLibraryHistoryStore.is_loading"
                                :emptyIcon="'fluent:history-20-regular'"
                                :emptyMessage="'まだBDの視聴履歴がありません。'"
                                :emptySubMessage="'BDを30秒以上みると、<br class=\'d-sm-none\'>視聴履歴に追加されます。'"
                                :forWatchedHistory="true"
                                @update:page="updateBDPage"
                                @update:sortOrder="updateBDSortOrder" />
                        </SwiperSlide>
                    </Swiper>
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>

import { Swiper, SwiperSlide } from 'swiper/vue';
import { onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import 'swiper/css';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import BDLibraryList, { IBDLibraryItem, BDLibrarySortOrder } from '@/components/Videos/BDLibraryList.vue';
import RecordedProgramList from '@/components/Videos/RecordedProgramList.vue';
import { IRecordedProgram } from '@/services/Videos';
import Videos from '@/services/Videos';
import { useBDLibraryHistoryStore } from '@/stores/BDLibraryHistoryStore';
import useSettingsStore from '@/stores/SettingsStore';
import useUserStore from '@/stores/UserStore';

// ルーター
const route = useRoute();
const router = useRouter();
const settingsStore = useSettingsStore();
const bdLibraryHistoryStore = useBDLibraryHistoryStore();

// アクティブなタブ
const activeTab = ref<'videos' | 'bd'>('videos');
const swiper_instance = ref<any>(null);

// 録画番組のリスト
const programs = ref<IRecordedProgram[]>([]);
const total_programs = ref(0);
const is_loading = ref(true);

// 現在のページ番号
const current_page = ref(1);

// 録画番組を取得
const fetchPrograms = async () => {
    // 視聴履歴に登録されている録画番組の ID を取得
    const history_ids = settingsStore.settings.watched_history
        .sort((a, b) => b.updated_at - a.updated_at)  // 最後に視聴した順
        .map(history => history.video_id);

    // 視聴履歴が空の場合は早期リターン
    if (history_ids.length === 0) {
        programs.value = [];
        total_programs.value = 0;
        is_loading.value = false;
        return;
    }

    // 録画番組を取得
    const result = await Videos.fetchVideos('ids', current_page.value, history_ids);
    if (result) {
        programs.value = result.recorded_programs;
        total_programs.value = result.total;
    }
    is_loading.value = false;
};

// --- BD視聴履歴 ---
const bd_history_items = ref<IBDLibraryItem[]>([]);
const bd_history_total = ref(0);
const bd_current_page = ref(1);
const bd_sort_order = ref<BDLibrarySortOrder>('added_desc');

const fetchBDHistory = async () => {
    await bdLibraryHistoryStore.fetchHistoryList();
    let items = bdLibraryHistoryStore.history_items.map(item => ({
        id: item.id,
        bd_id: item.bd_id,
        title: item.title,
        path: item.path,
        watched_at: item.watched_at,
        position: item.position,
        duration: item.duration,
    }));
    switch (bd_sort_order.value) {
        case 'added_asc':
            items.sort((a, b) => new Date(a.watched_at || 0).getTime() - new Date(b.watched_at || 0).getTime());
            break;
        case 'added_desc':
        default:
            items.sort((a, b) => new Date(b.watched_at || 0).getTime() - new Date(a.watched_at || 0).getTime());
            break;
    }
    bd_history_items.value = items;
    bd_history_total.value = bd_history_items.value.length;
};

const updateBDPage = async (page: number) => { bd_current_page.value = page; };
const updateBDSortOrder = async (order: BDLibrarySortOrder) => { bd_sort_order.value = order; bd_current_page.value = 1; await fetchBDHistory(); };

// ページを更新
const updatePage = async (page: number) => {
    current_page.value = page;
    is_loading.value = true;
    await router.replace({
        query: {
            ...route.query,
            page: page.toString(),
        },
    });
};

// クエリパラメータが変更されたら録画番組を再取得
watch(() => route.query, async (newQuery) => {
    // ページ番号を同期
    if (newQuery.page) {
        current_page.value = parseInt(newQuery.page as string);
    }
    await fetchPrograms();
}, { deep: true });

// 視聴履歴の変更を監視して即座に再取得
watch(() => settingsStore.settings.watched_history, async () => {
    await fetchPrograms();
}, { deep: true });

// 開始時に実行
onMounted(async () => {
    // 事前にログイン状態を同期（トークンがあればユーザー情報を取得）
    const userStore = useUserStore();
    await userStore.fetchUser();

    // クエリパラメータから初期値を設定
    if (route.query.page) {
        current_page.value = parseInt(route.query.page as string);
    }

    // 録画番組を取得
    await fetchPrograms();
});

// タブ変更時の処理
watch(activeTab, async (newTab) => {
    if (swiper_instance.value) {
        swiper_instance.value.slideTo(newTab === 'videos' ? 0 : 1);
    }
    if (newTab === 'bd') await fetchBDHistory();
    await router.replace({ query: { ...route.query, tab: newTab } });
});

</script>
<style lang="scss" scoped>

.watched-history-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
    @include smartphone-vertical {
        padding-top: 10px !important;
    }
}

.watched-history-container {
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
        padding: 16px 8px !important;
        padding-top: 8px !important;
    }
}

.tab-container { display: flex; justify-content: center; margin-bottom: 16px; padding-bottom: 12px; background: linear-gradient(to bottom, rgb(var(--v-theme-background)) calc(100% - calc(12px + 3px)), rgb(var(--v-theme-background-lighten-1)) calc(100% - calc(12px + 3px)) calc(100% - 12px), rgb(var(--v-theme-background)) calc(100% - 12px)); }
.tab-buttons { display: flex; position: relative; align-items: center; max-width: 100%; height: 100%; margin-left: auto; margin-right: auto; overflow-x: auto; overflow-y: clip; padding-bottom: 8px; }
.tab-button { display: flex; align-items: center; justify-content: center; width: 98px; height: 100%; padding: 0; border: none; border-radius: 2.5px; color: white !important; background-color: transparent !important; font-size: 16px; letter-spacing: 0.0892857143em !important; text-transform: none; cursor: pointer; transition: color 0.3s ease; }
.tab-button:hover { color: rgb(var(--v-theme-primary)) !important; }
.tab-button.active { color: white !important; }
.tab-highlight { position: absolute; left: 0; bottom: 0; width: calc(100% / var(--tab-length, 0)); height: 3px; background: rgb(var(--v-theme-primary)); transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1); transform: translateX(calc(100% * var(--active-tab-index, 0))); will-change: transform; }
.content-swiper { width: 100%; background: transparent !important; overflow: hidden; }

</style>