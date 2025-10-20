<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="bd-library-home-container-wrapper">
                <SPHeaderBar />
                <div class="bd-library-home-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: 'BDを見る', path: '/bd-library/', disabled: true },
                    ]" />
                    <BDLibraryList
                        class="bd-library-home-container__bd-list"
                        :class="{'bd-library-home-container__bd-list--loading': filteredBDList.length === 0 && bdLibraryStore.total === 0}"
                        title="BD一覧"
                        :items="filteredBDList.map(i => {
                            // 視聴履歴から進捗情報を取得
                            const history = bdLibraryHistoryStore.history_list.find(h => h.bd_id === i.id);
                            return {
                                id: String(i.id),
                                bd_id: i.id,
                                title: i.title,
                                path: i.path,
                                added_at: i.created_at,
                                position: history?.position,
                                duration: i.duration, // 動画時間表示は常にBDライブラリのdurationを使用
                            };
                        })"
                        :total="bdLibraryStore.total"
                        :hidePagination="false"
                        :hideSort="false"
                        :showMoreButton="false"
                        :showSearch="false"
                        :page="currentPage"
                        @update:page="updatePage"
                        @update:sortOrder="updateSortOrder"
                    />
                </div>
            </div>
        </main>
    </div>
</template>
<script lang="ts" setup>
import { onMounted, ref, computed, watch } from 'vue';
import { useRoute } from 'vue-router';

import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import BDLibraryList from '@/components/Videos/BDLibraryList.vue';
import Message from '@/message';
import { useBDLibraryMylistStore } from '@/stores/BDLibraryMylistStore';
import { useBDLibraryStore } from '@/stores/BDLibraryStore';
import { useBDLibraryHistoryStore } from '@/stores/BDLibraryHistoryStore';
import useUserStore from '@/stores/UserStore';

const bdLibraryStore = useBDLibraryStore();
const bdLibraryMylistStore = useBDLibraryMylistStore();
const bdLibraryHistoryStore = useBDLibraryHistoryStore();
const userStore = useUserStore();
const route = useRoute();
const searchQuery = ref('');

onMounted(async () => {
    // ログイン状態を復元
    await userStore.fetchUser(true);

    await bdLibraryStore.fetchBDLibraryList(currentPage);

    // ログインしている場合のみマイリスト情報と視聴履歴を取得
    if (userStore.is_logged_in) {
        try {
            await bdLibraryMylistStore.fetchMylistItems();
            await bdLibraryHistoryStore.fetchHistoryList();
        } catch (error) {
            // マイリスト取得に失敗した場合は無視（ログインしていない場合）
            // エラーメッセージは表示しない
        }
    }

    // URLクエリパラメータから検索クエリを取得
    if (route.query.search) {
        searchQuery.value = route.query.search as string;
    }
});

// ルートの変更を監視して検索クエリを更新
watch(() => route.query.search, (newSearch) => {
    if (newSearch) {
        searchQuery.value = newSearch as string;
    } else {
        searchQuery.value = '';
    }
});

// 検索結果をフィルタリング
let currentPage = 1;

// ページを更新
const updatePage = async (page: number) => {
    currentPage = page;
    await bdLibraryStore.fetchBDLibraryList(page);
};

// 並び順を更新
const updateSortOrder = async (order: 'added_desc' | 'added_asc') => {
    // BDライブラリの並び替えは現在サポートされていないため、何もしない
    // 将来的に並び替え機能を実装する場合はここに処理を追加
};

const filteredBDList = computed(() => {
    if (!searchQuery.value.trim()) {
        return bdLibraryStore.bdList;
    }

    const query = searchQuery.value.toLowerCase();
    return bdLibraryStore.bdList.filter(item =>
        item.title.toLowerCase().includes(query) ||
        item.path.toLowerCase().includes(query)
    );
});

function onThumbnailError(event: Event) {
    const target = event.target as HTMLImageElement;
    target.src = '/assets/images/icon.svg';
}

// マイリストに追加
const addToMylist = async (item: any) => {
    try {
        await bdLibraryMylistStore.addToMylist(item);
        Message.success('マイリストに追加しました。');
    } catch (error) {
        // エラーメッセージを表示
        Message.error('BDマイリストの追加に失敗しました。ログインし直してください。');
    }
};

// マイリストから削除
const removeFromMylist = async (bd_id: number) => {
    try {
        const mylistItem = bdLibraryMylistStore.mylist_items.find(item => item.bd_id === bd_id);
        if (mylistItem) {
            await bdLibraryMylistStore.removeFromMylist(mylistItem.id);
            Message.show('マイリストから削除しました。');
        }
    } catch (error) {
        // エラーメッセージを表示
        Message.error('BDマイリストの削除に失敗しました。ログインし直してください。');
    }
};
</script>
<style lang="scss" scoped>

.bd-library-home-container-wrapper {
    display: flex;
    flex-direction: column;
    width: 100%;
}

.bd-library-home-container {
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

    &__bd-list.bd-library-home-container__bd-list--loading {
        // ローディング中にちらつかないように
        :deep(.bd-library-list__grid) {
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
.bd-library-header {
  margin-bottom: 24px;
}
.search-info {
  margin-top: 8px;
}
.search-keyword {
  font-size: 1rem;
  color: #ccc;
  margin: 0 0 4px 0;
}
.search-results-count {
  font-size: 0.9rem;
  color: #999;
  margin: 0;
}
.bd-card {
  cursor: pointer;
  transition: box-shadow 0.2s;
}
.bd-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.12);
}
.bd-library-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  margin-top: 80px;
  color: #ccc;
}
.bd-library-empty-title {
  font-size: 1.3rem;
  font-weight: bold;
  margin-top: 16px;
  margin-bottom: 8px;
  color: #fff;
}
.bd-library-empty-desc {
  font-size: 1rem;
  color: #ccc;
}
.bd-directory-group {
  margin-bottom: 32px;
}
.bd-directory-title {
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 12px;
  color: #fff;
}
.bd-directory-card {
  margin-bottom: 32px;
  padding-bottom: 8px;
}
.bd-directory-thumbnail-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 120px;
  background: #222;
}
.bd-directory-thumbnail {
  width: 80px;
  height: 80px;
  object-fit: contain;
  margin: 16px 0;
}
.bd-directory-title {
  font-size: 1.2rem;
  font-weight: bold;
  margin-bottom: 8px;
  color: #fff;
  text-align: center;
}
.bd-file-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.bd-file-list-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid #333;
  cursor: pointer;
  transition: background 0.2s;
}
.bd-file-list-item:hover {
  background: #222;
}
.bd-file-title {
  color: #fff;
}
.bd-file-duration {
  color: #ccc;
  font-size: 0.95em;
}
.bd-directory-thumb-card {
  margin-bottom: 32px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  background: #181818;
  border: 0.5px solid #444;
  border-radius: 8px;
}
.bd-directory-thumb-card:hover {
  box-shadow: 0 4px 16px rgba(0,0,0,0.18);
}
.bd-directory-thumb-img-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  aspect-ratio: 16 / 9;  /* サムネイルを16:9で統一 */
  background: #222;
  /* 画像が枠全体に広がるように overflow: hidden を追加 */
  overflow: hidden;
}
.bd-directory-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  margin: 0;
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.25);
}
.bd-directory-thumb-title {
  font-size: 1.1rem !important;
  font-weight: 300 !important;
  padding: 4px 16px !important;
  color: #fff;
  text-align: center;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.bd-directory-thumb-title-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bd-directory-thumb-mylist-btn {
  flex-shrink: 0;
}
</style>