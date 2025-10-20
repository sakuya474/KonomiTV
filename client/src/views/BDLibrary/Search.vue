<template>
  <div class="route-container">
    <HeaderBar />
    <main>
      <Navigation />
      <div class="bd-library-search-container-wrapper">
        <SPHeaderBar />
        <Breadcrumb :crumbs="[{ name: 'BDライブラリ', path: '/bd-library/' }, { name: '検索結果', path: '/bd-library/search', disabled: true }]" />
        <div class="bd-library-search-container">
          <div class="bd-library-header">
            <h2>「{{ searchQuery }}」の検索結果</h2>
            <p class="search-results-count">検索結果: {{ filteredBDList.length }}件</p>
          </div>

          <template v-if="filteredBDList.length === 0">
            <div class="bd-library-empty">
              <v-icon size="48" color="grey">mdi-alert-circle-outline</v-icon>
              <div class="bd-library-empty-title">
                検索結果が見つかりませんでした。
              </div>
              <div class="bd-library-empty-desc">
                別のキーワードで検索してみてください。
              </div>
            </div>
          </template>
          <template v-else>
            <v-row>
              <v-col v-for="item in filteredBDList" :key="item.id" cols="12" sm="6" md="4" lg="3">
                <v-card class="bd-directory-thumb-card" border @click="$router.push(`/bd-library/watch/${item.id}`)">
                  <div class="bd-directory-thumb-img-wrapper">
                    <img class="bd-directory-thumb-img" :src="`/api/bd-library/${item.id}/thumbnail`" alt="サムネイル" @error="onThumbnailError($event)" />
                  </div>
                  <v-card-title class="bd-directory-thumb-title">
                    <span class="bd-directory-thumb-title-text">{{ item.title }}</span>
                    <v-btn
                      icon="mdi-plus"
                      size="small"
                      variant="text"
                      color="white"
                      class="bd-directory-thumb-mylist-btn"
                      @click.stop="addToMylist(item)"
                      :loading="bdLibraryMylistStore.is_loading"
                      v-if="!bdLibraryMylistStore.isInMylist(item.id)"
                    ></v-btn>
                    <v-btn
                      icon="mdi-check"
                      size="small"
                      variant="text"
                      color="pink"
                      class="bd-directory-thumb-mylist-btn"
                      @click.stop="removeFromMylist(item.id)"
                      :loading="bdLibraryMylistStore.is_loading"
                      v-else
                    ></v-btn>
                  </v-card-title>
                </v-card>
              </v-col>
            </v-row>
          </template>
        </div>
      </div>
    </main>
  </div>
</template>

<script lang="ts" setup>
import { onMounted, ref, computed, watch } from 'vue';
import { useRoute } from 'vue-router';

import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import Breadcrumb from '@/components/Breadcrumbs.vue';
import Message from '@/message';
import { useBDLibraryStore } from '@/stores/BDLibraryStore';
import { useBDLibraryMylistStore } from '@/stores/BDLibraryMylistStore';

const bdLibraryStore = useBDLibraryStore();
const bdLibraryMylistStore = useBDLibraryMylistStore();
const route = useRoute();
const searchQuery = ref('');

onMounted(async () => {
    await Promise.all([
        bdLibraryStore.fetchBDLibraryList(1),
        bdLibraryMylistStore.fetchMylistItems(),
    ]);

    // URLクエリパラメータから検索クエリを取得
    if (route.query.query) {
        searchQuery.value = route.query.query as string;
    }
});

// クエリパラメータが変更されたら検索クエリを更新
watch(() => route.query.query, (newQuery) => {
    if (newQuery) {
        searchQuery.value = newQuery as string;
    }
});

// 検索結果をフィルタリング
const filteredBDList = computed(() => {
    if (!searchQuery.value.trim()) {
        return [];
    }

    const query = searchQuery.value.toLowerCase();
    const filtered = bdLibraryStore.bdList.filter(item =>
        item.title.toLowerCase().includes(query) ||
        item.path.toLowerCase().includes(query)
    );

    return filtered;
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

<style scoped>
.bd-library-search-container-wrapper {
  flex: 1;
  padding: 24px;
}

.bd-library-header {
  margin-bottom: 24px;
}

.bd-library-header h2 {
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 8px;
  color: rgb(var(--v-theme-on-surface));
}

.search-results-count {
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
  margin: 0;
}

.bd-directory-thumb-card {
  cursor: pointer;
  transition: transform 0.2s, box-shadow 0.2s;
  height: 100%;

  &:hover {
    transform: translateY(-2px);
    box-shadow: 0px 8px 25px -5px rgb(0 0 0 / 20%),
                0px 10px 10px -5px rgb(0 0 0 / 14%);
  }
}

.bd-directory-thumb-img-wrapper {
  position: relative;
  width: 100%;
  height: 200px;
  overflow: hidden;
  border-radius: 8px 8px 0 0;
}

.bd-directory-thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.2s;

  &:hover {
    transform: scale(1.05);
  }
}

.bd-library-search-container .bd-directory-thumb-title {
  font-size: 1.1rem !important;
  font-weight: 300 !important;
  line-height: 1.4;
  padding: 12px;
  color: #fff;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
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

.bd-library-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 24px;
  text-align: center;
}

.bd-library-empty-title {
  font-size: 18px;
  font-weight: 600;
  margin: 16px 0 8px 0;
  color: rgb(var(--v-theme-on-surface));
}

.bd-library-empty-desc {
  font-size: 14px;
  color: rgb(var(--v-theme-on-surface-variant));
  line-height: 1.5;
}

@media (max-width: 600px) {
  .bd-library-search-container-wrapper {
    padding: 16px;
  }

  .bd-library-header h2 {
    font-size: 20px;
  }
}
</style>