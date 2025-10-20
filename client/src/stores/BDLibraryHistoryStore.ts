import { defineStore } from 'pinia';
import { ref } from 'vue';

import BDLibrary from '@/services/BDLibrary';
import useUserStore from '@/stores/UserStore';

export interface IBDLibraryHistoryItem {
    id: string;
    bd_id: number;
    title: string;
    path: string;
    watched_at: string;
    duration: number;
    position: number;
}

export const useBDLibraryHistoryStore = defineStore('bdLibraryHistory', () => {
    const history_list = ref<IBDLibraryHistoryItem[]>([]);
    const history_items = ref<IBDLibraryHistoryItem[]>([]);
    const is_loading = ref(false);

    // 視聴履歴を取得
    const fetchHistoryList = async () => {
        const userStore = useUserStore();

        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }

        try {
            is_loading.value = true;
            const response = await BDLibrary.fetchBDHistoryList();
            history_list.value = response;
            history_items.value = response;
        } catch (error) {
            console.error('BDライブラリ視聴履歴の取得に失敗しました:', error);
        } finally {
            is_loading.value = false;
        }
    };

    // 視聴履歴を追加
    const addHistory = async (bd_item: { id: number; title: string; path: string }, position: number, duration: number) => {
        const userStore = useUserStore();

        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }

        // 無効な値の場合は何もしない
        if (isNaN(position) || isNaN(duration) || position < 0 || duration <= 0) {
            return;
        }

        try {
            const success = await BDLibrary.addBDHistory(bd_item.id, position, duration);
            if (success) {
                // 成功した場合は履歴を再取得
                await fetchHistoryList();
            }
        } catch (error) {
            console.error('BDライブラリ視聴履歴の追加に失敗しました:', error);
        }
    };

    // 視聴履歴を削除
    const removeHistory = async (history_id: string) => {
        const userStore = useUserStore();

        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }

        try {
            const success = await BDLibrary.removeBDHistory(history_id);
            // 削除後の再取得は呼び出し元で行う（無限ループ防止のためここでは呼ばない）
            // if (success) {
            //     await fetchHistoryList();
            // }
        } catch (error) {
            console.error('BDライブラリ視聴履歴の削除に失敗しました:', error);
        }
    };

    // 視聴履歴を全削除
    const clearHistory = async () => {
        const userStore = useUserStore();

        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }

        try {
            const success = await BDLibrary.clearBDHistory();
            if (success) {
                // 成功した場合は履歴を再取得
                await fetchHistoryList();
            }
        } catch (error) {
            console.error('BDライブラリ視聴履歴の全削除に失敗しました:', error);
        }
    };

    return {
        history_list,
        history_items,
        is_loading,
        fetchHistoryList,
        addHistory,
        removeHistory,
        clearHistory,
    };
});

