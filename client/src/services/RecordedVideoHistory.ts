import APIClient from './APIClient';

// 録画番組視聴履歴アイテムのインターフェース
export interface IRecordedVideoHistoryItem {
    id: string;
    recorded_program_id: number;
    title: string;
    position: number;
    duration: number;
    watched_at: string;
}

class RecordedVideoHistory {

    // 録画番組視聴履歴一覧を取得
    static async fetchHistoryList(): Promise<IRecordedVideoHistoryItem[]> {
        const response = await APIClient.get<IRecordedVideoHistoryItem[]>('/recorded-video-history/history');
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組視聴履歴の取得に失敗しました。');
            return [];
        }
        return response.data;
    }

    // 録画番組視聴履歴に追加
    static async addHistory(recorded_program_id: number, position: number, duration: number): Promise<boolean> {
        const response = await APIClient.post('/recorded-video-history/history', {
            recorded_program_id: recorded_program_id,
            position: position,
            duration: duration,
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組視聴履歴の追加に失敗しました。');
            throw new Error('録画番組視聴履歴の追加に失敗しました。');
        }
        return true;
    }

    // 録画番組視聴履歴から削除
    static async removeHistory(history_id: string): Promise<boolean> {
        const response = await APIClient.delete(`/recorded-video-history/history/${history_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組視聴履歴の削除に失敗しました。');
            throw new Error('録画番組視聴履歴の削除に失敗しました。');
        }
        return true;
    }

    // 録画番組視聴履歴を全削除
    static async clearHistory(): Promise<boolean> {
        const response = await APIClient.delete('/recorded-video-history/history');
        if (response.type === 'error') {
            APIClient.showGenericError(response, '録画番組視聴履歴の全削除に失敗しました。');
            throw new Error('録画番組視聴履歴の全削除に失敗しました。');
        }
        return true;
    }
}

export default RecordedVideoHistory;
