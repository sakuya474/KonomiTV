import { defineStore } from 'pinia';
import { ref } from 'vue';
import RecordedVideoHistory, { IRecordedVideoHistoryItem } from '@/services/RecordedVideoHistory';
import Message from '@/message';
import useUserStore from '@/stores/UserStore';

export const useRecordedVideoHistoryStore = defineStore('recordedVideoHistory', () => {
    const history_items = ref<IRecordedVideoHistoryItem[]>([]);
    const is_loading = ref(false);

    // 視聴履歴一覧を取得
    const fetchHistoryItems = async () => {
        const userStore = useUserStore();
        
        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }
        
        try {
            is_loading.value = true;
            const items = await RecordedVideoHistory.fetchHistoryList();
            history_items.value = items;
        } catch (error) {
            console.error('視聴履歴の取得に失敗しました:', error);
            Message.error('視聴履歴の取得に失敗しました。');
        } finally {
            is_loading.value = false;
        }
    };

    // 視聴履歴に追加
    const addHistory = async (recorded_program_id: number, position: number, duration: number) => {
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
            await RecordedVideoHistory.addHistory(recorded_program_id, position, duration);
            // 視聴履歴一覧を再取得
            await fetchHistoryItems();
        } catch (error) {
            console.error('視聴履歴の追加に失敗しました:', error);
            throw error;
        }
    };

    // 視聴履歴から削除
    const removeHistory = async (history_id: string) => {
        const userStore = useUserStore();
        
        // ログインしていない場合は何もしない
        if (!userStore.is_logged_in) {
            return;
        }
        
        try {
            await RecordedVideoHistory.removeHistory(history_id);
            // 視聴履歴一覧を再取得
            await fetchHistoryItems();
        } catch (error) {
            console.error('視聴履歴の削除に失敗しました:', error);
            throw error;
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
            await RecordedVideoHistory.clearHistory();
            history_items.value = [];
        } catch (error) {
            console.error('視聴履歴の全削除に失敗しました:', error);
            throw error;
        }
    };

    return {
        history_items,
        is_loading,
        fetchHistoryItems,
        addHistory,
        removeHistory,
        clearHistory,
    };
});
