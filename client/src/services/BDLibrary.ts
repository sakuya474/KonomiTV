import APIClient from './APIClient';

export interface IBDLibraryAudioTrack {
    id: number;
    name: string;
    language: string;
    codec: string;
    channels?: number;
    channel_layout?: string;
}
export interface IBDLibrarySubtitleTrack {
    id: number;
    name: string;
    language: string;
    codec: string;
}
export interface IBDLibraryItem {
    id: number;
    title: string;
    path: string;
    duration: number;
    titles?: any[]; // タイトルリスト（各タイトルのm3u8パス・チャプター情報など）
    chapters?: any[]; // チャプター情報（後から追加される場合がある）
    audio_tracks: any[];
    subtitle_tracks: any[];
    created_at: string;
    updated_at: string;
    available_qualities: string[];
    audio: IBDLibraryAudioTrack[];
    subtitle: IBDLibrarySubtitleTrack[];
}

// BDライブラリ検索条件のインターフェース
export interface IBDLibrarySearchCondition {
    keyword: string;
    is_case_sensitive: boolean;
    is_fuzzy_search_enabled: boolean;
}

class BDLibrary {
    static async fetchBDLibraryList(page: number = 1): Promise<{ items: IBDLibraryItem[]; total: number }> {
        // サーバーが未対応の場合に備え、配列/オブジェクトの両方を受け入れる
        const response = await APIClient.get<any>(`/bd-library/?page=${page}`, {
            // 認証が不要なAPIのため、認証トークンを付与しない
            headers: {
                'Authorization': undefined,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリ一覧の取得に失敗しました。');
            return { items: [], total: 0 };
        }
        const data = response.data;
        if (Array.isArray(data)) {
            return { items: data as IBDLibraryItem[], total: (data as IBDLibraryItem[]).length };
        }
        if (data && Array.isArray(data.items)) {
            return { items: data.items as IBDLibraryItem[], total: Number(data.total ?? data.items.length) };
        }
        // 予期せぬ形式の場合は空で返す
        return { items: [], total: 0 };
    }

    static async fetchBDLibraryItem(id: number): Promise<IBDLibraryItem | null> {
        const response = await APIClient.get<IBDLibraryItem>(`/bd-library/${id}`, {
            // 認証が不要なAPIのため、認証トークンを付与しない
            headers: {
                'Authorization': undefined,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリ情報の取得に失敗しました。');
            return null;
        }
        return response.data;
    }

    static async fetchBDLibraryTracks(id: number): Promise<{ audio: any[]; subtitle: any[] } | null> {
        const response = await APIClient.get<{ audio: any[]; subtitle: any[] }>(`/bd-library/${id}/tracks`, {
            // 認証が不要なAPIのため、認証トークンを付与しない
            headers: {
                'Authorization': undefined,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリの音声・字幕トラック情報の取得に失敗しました。');
            return null;
        }
        return response.data;
    }

    static async fetchBDLibraryChapters(id: number): Promise<any[] | null> {
        const response = await APIClient.get<any[]>(`/bd-library/${id}/chapters`, {
            // 認証が不要なAPIのため、認証トークンを付与しない
            headers: {
                'Authorization': undefined,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリのチャプター情報の取得に失敗しました。');
            return null;
        }
        return response.data;
    }

    static async searchBDLibrary(searchCondition: IBDLibrarySearchCondition): Promise<IBDLibraryItem[]> {
        const response = await APIClient.post<IBDLibraryItem[]>('/bd-library/search', searchCondition, {
            // 認証が不要なAPIのため、認証トークンを付与しない
            headers: {
                'Authorization': undefined,
            },
        });
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリの検索に失敗しました。');
            return [];
        }
        return response.data;
    }

    // BD視聴履歴関連のAPI
    static async fetchBDHistoryList(): Promise<any[]> {
        const response = await APIClient.get<any[]>('/bd-library/history');
        if (response.type === 'error') {
            // 未ログインなど
            if (response.status === 401) return [];
            APIClient.showGenericError(response, 'BD視聴履歴の取得に失敗しました。');
            return [];
        }
        return response.data;
    }

    static async addBDHistory(bd_id: number, position: number, duration: number): Promise<boolean> {
        const response = await APIClient.post<any>('/bd-library/history', {
            bd_id,
            position,
            duration,
        });
        if (response.type === 'error') {
            // 未ログインなど
            if (response.status === 401) return false;
            APIClient.showGenericError(response, 'BD視聴履歴の追加に失敗しました。');
            return false;
        }
        return true;
    }

    static async removeBDHistory(history_id: string): Promise<boolean> {
        const response = await APIClient.delete<any>(`/bd-library/history/${history_id}`);
        if (response.type === 'error') {
            // 未ログインなど
            if (response.status === 401) return false;
            APIClient.showGenericError(response, 'BD視聴履歴の削除に失敗しました。');
            return false;
        }
        return true;
    }

    static async clearBDHistory(): Promise<boolean> {
        const response = await APIClient.delete<any>('/bd-library/history');
        if (response.type === 'error') {
            // 未ログインなど
            if (response.status === 401) return false;
            APIClient.showGenericError(response, 'BD視聴履歴の全削除に失敗しました。');
            return false;
        }
        return true;
    }

    // BDマイリスト関連のAPI
    static async fetchBDMylistList(): Promise<any[]> {
        const response = await APIClient.get<any[]>('/bd-library/mylist');
        if (response.type === 'error') {
            // 未ログインなど
            if (response.status === 401) return [];
            return [];
        }
        return response.data;
    }

    static async addBDMylist(bd_id: number): Promise<boolean> {
        const response = await APIClient.post<any>('/bd-library/mylist', { bd_id });
        if (response.type === 'error') {
            if (response.status === 401) {
                APIClient.showGenericError(response, 'ログインが必要です。');
                return false;
            }
            APIClient.showGenericError(response, 'BDマイリストの追加に失敗しました。');
            return false;
        }
        return true;
    }

    static async removeBDMylist(mylist_id: string): Promise<boolean> {
        const response = await APIClient.delete<any>(`/bd-library/mylist/${mylist_id}`);
        if (response.type === 'error') {
            if (response.status === 401) {
                APIClient.showGenericError(response, 'ログインが必要です。');
                return false;
            }
            APIClient.showGenericError(response, 'BDマイリストの削除に失敗しました。');
            return false;
        }
        return true;
    }

    static async clearBDMylist(): Promise<boolean> {
        const response = await APIClient.delete<any>('/bd-library/mylist');
        if (response.type === 'error') {
            if (response.status === 401) {
                APIClient.showGenericError(response, 'ログインが必要です。');
                return false;
            }
            APIClient.showGenericError(response, 'BDマイリストの全削除に失敗しました。');
            return false;
        }
        return true;
    }

    /**
     * BDライブラリエントリを削除する
     * @param bd_id BDライブラリエントリのID
     * @returns 削除に成功した場合は true
     */
    static async deleteBD(bd_id: number): Promise<boolean> {
        const response = await APIClient.delete<any>(`/bd-library/${bd_id}`);
        if (response.type === 'error') {
            APIClient.showGenericError(response, 'BDライブラリの削除に失敗しました。');
            return false;
        }
        return true;
    }
}

export default BDLibrary;

