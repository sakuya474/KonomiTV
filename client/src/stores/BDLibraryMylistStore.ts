import { defineStore } from 'pinia';
import { ref } from 'vue';

import BDLibrary from '@/services/BDLibrary';

export interface IBDLibraryMylistItem {
    id: string;
    bd_id: number;
    title: string;
    path: string;
    added_at: string;
    position?: number;
    duration?: number;
}

export const useBDLibraryMylistStore = defineStore('bdLibraryMylist', () => {
    const mylist_items = ref<IBDLibraryMylistItem[]>([]);
    const is_loading = ref(false);

    // マイリストを取得
    const fetchMylistItems = async () => {
        try {
            is_loading.value = true;
            const response = await BDLibrary.fetchBDMylistList();
            mylist_items.value = response;
        } catch (error) {
            console.error('BDライブラリマイリストの取得に失敗しました:', error);
        } finally {
            is_loading.value = false;
        }
    };

    // マイリストに追加
    const addToMylist = async (bd_item: { id: number; title: string; path: string }) => {
        try {
            const success = await BDLibrary.addBDMylist(bd_item.id);
            if (success) {
                // 成功した場合はマイリストを再取得
                await fetchMylistItems();
            } else {
                // 失敗した場合は例外を投げる
                throw new Error('BDマイリストの追加に失敗しました');
            }
        } catch (error) {
            console.error('BDライブラリマイリストの追加に失敗しました:', error);
            // エラーを再投げる
            throw error;
        }
    };

    // マイリストから削除
    const removeFromMylist = async (mylist_id: string) => {
        try {
            const success = await BDLibrary.removeBDMylist(mylist_id);
            if (success) {
                // 成功した場合はマイリストを再取得
                await fetchMylistItems();
            } else {
                // 失敗した場合は例外を投げる
                throw new Error('BDマイリストの削除に失敗しました');
            }
        } catch (error) {
            console.error('BDライブラリマイリストの削除に失敗しました:', error);
            // エラーを再投げる
            throw error;
        }
    };

    // マイリストを全削除
    const clearMylist = async () => {
        try {
            const success = await BDLibrary.clearBDMylist();
            if (success) {
                // 成功した場合はマイリストを再取得
                await fetchMylistItems();
            }
        } catch (error) {
            console.error('BDライブラリマイリストの全削除に失敗しました:', error);
            // エラーが発生した場合は再取得をスキップ
        }
    };

    // マイリストに含まれているかチェック
    const isInMylist = (bd_id: number): boolean => {
        return mylist_items.value.some(item => item.bd_id === bd_id);
    };

    return {
        mylist_items,
        is_loading,
        fetchMylistItems,
        addToMylist,
        removeFromMylist,
        clearMylist,
        isInMylist,
    };
});
