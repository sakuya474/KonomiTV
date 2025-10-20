<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="mylist-container-wrapper">
                <div class="mylist-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'マイリスト', path: '/mylist/', disabled: true },
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

                    <!-- Swiperコンテンツ -->
                    <Swiper class="content-swiper" :space-between="32" :auto-height="true" :touch-start-prevent-default="false"
                        :observer="true" :observe-parents="true" :initial-slide="0"
                        @swiper="swiper_instance = $event"
                        @slide-change="activeTab = $event.activeIndex === 0 ? 'videos' : 'bd'">
                        <SwiperSlide>
                            <!-- 録画番組タブ -->
                            <RecordedProgramList
                            title="録画マイリスト"
                            :programs="programs"
                            :total="total_programs"
                            :page="current_page"
                            :sortOrder="sort_order"
                            :isLoading="is_loading"
                            :showBackButton="true"
                            :showEmptyMessage="!is_loading"
                            :emptyIcon="'ic:round-playlist-play'"
                            :emptyMessage="'あとで見たい番組を<br class=\'d-sm-none\'>マイリストに保存できます。'"
                            :emptySubMessage="'録画番組の右上にある ＋ ボタンから、<br class=\'d-sm-none\'>番組をマイリストに追加できます。'"
                            :forMylist="true"
                            @update:page="updatePage"
                            @update:sortOrder="updateSortOrder($event as MylistSortOrder)" />
                        </SwiperSlide>
                        <SwiperSlide>
                            <!-- BDライブラリタブ -->
                            <BDLibraryList
                            title="BDマイリスト"
                            :items="bd_mylist_items"
                            :total="bd_mylist_total"
                            :page="bd_current_page"
                            :sortOrder="bd_sort_order"
                            :isLoading="bdLibraryMylistStore.is_loading"
                            :showBackButton="true"
                            :showEmptyMessage="!bdLibraryMylistStore.is_loading"
                            :emptyIcon="'ic:round-playlist-play'"
                            :emptyMessage="'あとで見たいBDを<br class=\'d-sm-none\'>マイリストに保存できます。'"
                            :emptySubMessage="'BDライブラリの右下にある ＋ ボタンから、<br class=\'d-sm-none\'>BDをマイリストに追加できます。'"
                            :forMylist="true"
                            @update:page="updateBDPage"
                            @update:sortOrder="updateBDSortOrder"
                            @deleted="handleBDItemDeleted" />
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
    import Message from '@/message';
    import { IRecordedProgram, MylistSortOrder } from '@/services/Videos';
    import Videos from '@/services/Videos';
    import { useBDLibraryMylistStore } from '@/stores/BDLibraryMylistStore';
    import useSettingsStore from '@/stores/SettingsStore';
    import useUserStore from '@/stores/UserStore';

    // ルーター
    const route = useRoute();
    const router = useRouter();
    const settingsStore = useSettingsStore();
    const bdLibraryMylistStore = useBDLibraryMylistStore();

    // アクティブなタブ
    const activeTab = ref<'videos' | 'bd'>('videos');
    const swiper_instance = ref<any>(null);

    // 録画番組のリスト
    const programs = ref<IRecordedProgram[]>([]);
    const total_programs = ref(0);
    const is_loading = ref(true);

    // 現在のページ番号
    const current_page = ref(1);

    // 並び順
    const sort_order = ref<MylistSortOrder>('mylist_added_desc');

    // BDマイリスト用
    const bd_mylist_items = ref<IBDLibraryItem[]>([]);
    const bd_mylist_total = ref(0);
    const bd_current_page = ref(1);
    const bd_sort_order = ref<BDLibrarySortOrder>('added_desc');

    // 録画番組を取得
    const fetchPrograms = async () => {
        const mylist_ids = settingsStore.settings.mylist
            .filter(item => item.type === 'RecordedProgram')
            .sort((a, b) => {
                switch (sort_order.value) {
                    case 'mylist_added_desc':
                        return b.created_at - a.created_at;
                    case 'mylist_added_asc':
                        return a.created_at - b.created_at;
                    case 'recorded_desc':
                    case 'recorded_asc':
                        return b.created_at - a.created_at;
                    default:
                        return 0;
                }
            })
            .map(item => item.id);
        if (mylist_ids.length === 0) {
            programs.value = [];
            total_programs.value = 0;
            is_loading.value = false;
            return;
        }
        let order: 'desc' | 'asc' | 'ids' = 'ids';
        if (sort_order.value === 'recorded_desc') order = 'desc';
        else if (sort_order.value === 'recorded_asc') order = 'asc';
        const result = await Videos.fetchVideos(order, current_page.value, mylist_ids);
        if (result) {
            programs.value = result.recorded_programs;
            total_programs.value = result.total;
        }
        is_loading.value = false;
    };

    const updatePage = async (page: number) => {
        current_page.value = page;
        is_loading.value = true;
        await router.replace({
            query: { ...route.query, page: page.toString() },
        });
    };

    const updateSortOrder = async (order: MylistSortOrder) => {
        sort_order.value = order;
        current_page.value = 1;
        is_loading.value = true;
        await router.replace({
            query: { ...route.query, order, page: '1' },
        });
    };

    watch(() => route.query, async (newQuery) => {
        if (newQuery.page) current_page.value = parseInt(newQuery.page as string);
        if (newQuery.order) sort_order.value = newQuery.order as MylistSortOrder;
        await fetchPrograms();
    }, { deep: true });

    watch(() => settingsStore.settings.mylist, async () => {
        if (activeTab.value === 'videos') await fetchPrograms();
    }, { deep: true });

    // BDマイリストを取得
    const fetchBDMylist = async () => {
        await bdLibraryMylistStore.fetchMylistItems();
        let items = bdLibraryMylistStore.mylist_items.map(item => ({
            id: item.id,
            bd_id: item.bd_id,
            title: item.title,
            path: item.path,
            added_at: item.added_at,
            position: item.position,
            duration: item.duration,
        }));
        switch (bd_sort_order.value) {
            case 'added_asc':
                items.sort((a, b) => new Date(a.added_at).getTime() - new Date(b.added_at).getTime());
                break;
            case 'added_desc':
            default:
                items.sort((a, b) => new Date(b.added_at).getTime() - new Date(a.added_at).getTime());
                break;
        }
        bd_mylist_items.value = items;
        bd_mylist_total.value = bd_mylist_items.value.length;
    };

    const updateBDPage = async (page: number) => { bd_current_page.value = page; };
    const updateBDSortOrder = async (order: BDLibrarySortOrder) => { bd_sort_order.value = order; bd_current_page.value = 1; await fetchBDMylist(); };
    const handleBDItemDeleted = async () => { await fetchBDMylist(); };

    onMounted(async () => {
        const userStore = useUserStore();
        await userStore.fetchUser();
        if (route.query.page) current_page.value = parseInt(route.query.page as string);
        if (route.query.order) sort_order.value = route.query.order as MylistSortOrder;
        await fetchPrograms();
    });

    // タブ変更時の処理
    watch(activeTab, async (newTab) => {
        if (swiper_instance.value) {
            swiper_instance.value.slideTo(newTab === 'videos' ? 0 : 1);
        }
        if (newTab === 'bd') await fetchBDMylist();
        await router.replace({ query: { ...route.query, tab: newTab } });
    });

    </script>
    <style lang="scss" scoped>

    .mylist-container-wrapper {
        display: flex;
        flex-direction: column;
        width: 100%;
        @include smartphone-vertical {
            padding-top: 10px !important;
        }
    }

    .mylist-container {
        display: flex;
        flex-direction: column;
        width: 100%;
        height: 100%;
        padding: 20px;
        margin: 0 auto;
        min-width: 0;
        max-width: 1000px;
        @include smartphone-horizontal { padding: 16px 20px !important; }
        @include smartphone-horizontal-short { padding: 16px 16px !important; }
        @include smartphone-vertical { padding: 16px 8px !important; padding-top: 8px !important; }
    }

    .tab-container { display: flex; justify-content: center; margin-bottom: 16px; padding-bottom: 12px; background: linear-gradient(to bottom, rgb(var(--v-theme-background)) calc(100% - calc(12px + 3px)), rgb(var(--v-theme-background-lighten-1)) calc(100% - calc(12px + 3px)) calc(100% - 12px), rgb(var(--v-theme-background)) calc(100% - 12px)); }
    .tab-buttons { display: flex; position: relative; align-items: center; max-width: 100%; height: 100%; margin-left: auto; margin-right: auto; overflow-x: auto; overflow-y: clip; padding-bottom: 8px; }
    .tab-button { display: flex; align-items: center; justify-content: center; width: 98px; height: 100%; padding: 0; border: none; border-radius: 2.5px; color: white !important; background-color: transparent !important; font-size: 16px; letter-spacing: 0.0892857143em !important; text-transform: none; cursor: pointer; transition: color 0.3s ease; }
    .tab-button:hover { color: rgb(var(--v-theme-primary)) !important; }
    .tab-button.active { color: white !important; }
    .tab-highlight { position: absolute; left: 0; bottom: 0; width: calc(100% / var(--tab-length, 0)); height: 3px; background: rgb(var(--v-theme-primary)); transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1); transform: translateX(calc(100% * var(--active-tab-index, 0))); will-change: transform; }
    .content-swiper { width: 100%; background: transparent !important; overflow: hidden; }

    </style>