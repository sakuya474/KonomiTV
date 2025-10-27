import { defineStore } from 'pinia';

import { ChannelType } from '@/services/Channels';
import Timetable from '@/services/Timetable';
import { ITimetableChannel } from '@/services/Timetable';

export const useTimetableStore = defineStore('timetable', {
    state: () => ({
        // 番組表のデータ（3日分: 昨日・今日・明日のみキャッシュ）
        _timetable_channels_yesterday: null as ITimetableChannel[] | null,
        _timetable_channels_today: null as ITimetableChannel[] | null,
        _timetable_channels_tomorrow: null as ITimetableChannel[] | null,
        // 現在表示している日付（中央の「今日」の日付）
        current_date: new Date(),
        // 現在選択中のチャンネルタイプ（デフォルトは地デジ）
        selected_channel_type: 'GR' as 'ALL' | ChannelType,
        // 現在表示している日のオフセット (-7 ～ +7: UI用、内部では3日分のみ保持)
        selected_day_offset: 0,
        // ロード中フラグ
        is_loading: false,
    }),
    getters: {
        /**
         * 表示用の番組表データ（3日分: 昨日・今日・明日を結合して返す）
         */
        timetable_channels(state): ITimetableChannel[] | null {
            const yesterday = state.selected_channel_type === 'ALL'
                ? state._timetable_channels_yesterday
                : state._timetable_channels_yesterday?.filter(channel => channel.channel.type === state.selected_channel_type);
            const today = state.selected_channel_type === 'ALL'
                ? state._timetable_channels_today
                : state._timetable_channels_today?.filter(channel => channel.channel.type === state.selected_channel_type);
            const tomorrow = state.selected_channel_type === 'ALL'
                ? state._timetable_channels_tomorrow
                : state._timetable_channels_tomorrow?.filter(channel => channel.channel.type === state.selected_channel_type);

            if (!yesterday || !today || !tomorrow) {
                return null;
            }

            // 各チャンネルごとに3日分の番組を結合
            const channelMap = new Map<string, ITimetableChannel>();

            // 昨日のチャンネルをベースにする
            yesterday.forEach(ch => {
                channelMap.set(ch.channel.id, {
                    channel: ch.channel,
                    programs: [...ch.programs]
                });
            });

            // 今日の番組を追加（重複チェック）
            today.forEach(ch => {
                const existing = channelMap.get(ch.channel.id);
                if (existing) {
                    const existingIds = new Set(existing.programs.map(p => p.id));
                    ch.programs.forEach(program => {
                        if (!existingIds.has(program.id)) {
                            existing.programs.push(program);
                        }
                    });
                } else {
                    channelMap.set(ch.channel.id, {
                        channel: ch.channel,
                        programs: [...ch.programs]
                    });
                }
            });

            // 明日の番組を追加（重複チェック）
            tomorrow.forEach(ch => {
                const existing = channelMap.get(ch.channel.id);
                if (existing) {
                    const existingIds = new Set(existing.programs.map(p => p.id));
                    ch.programs.forEach(program => {
                        if (!existingIds.has(program.id)) {
                            existing.programs.push(program);
                        }
                    });
                } else {
                    channelMap.set(ch.channel.id, {
                        channel: ch.channel,
                        programs: [...ch.programs]
                    });
                }
            });

            // 時刻順にソート
            channelMap.forEach(ch => {
                ch.programs.sort((a, b) => new Date(a.start_time).getTime() - new Date(b.start_time).getTime());
            });

            return Array.from(channelMap.values());
        }
    },
    actions: {
        /**
         * 番組表のデータを取得・更新する（selected_day_offset を中心に3日分を取得）
         * 各日の0時～24時を取得
         */
        async fetchTimetable() {
            if (this.is_loading) return;
            this.is_loading = true;

            try {
                // 選択されたオフセットを基準に、昨日・今日・明日の3日分を取得
                const baseDate = new Date(this.current_date);
                baseDate.setDate(baseDate.getDate() + this.selected_day_offset);

                // 昨日の番組表
                const yesterday_start = new Date(baseDate);
                yesterday_start.setDate(yesterday_start.getDate() - 1);
                yesterday_start.setHours(0, 0, 0, 0);
                const yesterday_end = new Date(yesterday_start);
                yesterday_end.setDate(yesterday_end.getDate() + 1);
                yesterday_end.setHours(0, 0, 0, 0);

                // 今日の番組表
                const today_start = new Date(baseDate);
                today_start.setHours(0, 0, 0, 0);
                const today_end = new Date(today_start);
                today_end.setDate(today_end.getDate() + 1);
                today_end.setHours(0, 0, 0, 0);

                // 明日の番組表
                const tomorrow_start = new Date(baseDate);
                tomorrow_start.setDate(tomorrow_start.getDate() + 1);
                tomorrow_start.setHours(0, 0, 0, 0);
                const tomorrow_end = new Date(tomorrow_start);
                tomorrow_end.setDate(tomorrow_end.getDate() + 1);
                tomorrow_end.setHours(0, 0, 0, 0);

                // 3日分を並列取得
                const [yesterday_data, today_data, tomorrow_data] = await Promise.all([
                    Timetable.fetchTimetable(yesterday_start, yesterday_end),
                    Timetable.fetchTimetable(today_start, today_end),
                    Timetable.fetchTimetable(tomorrow_start, tomorrow_end),
                ]);

                this._timetable_channels_yesterday = yesterday_data;
                this._timetable_channels_today = today_data;
                this._timetable_channels_tomorrow = tomorrow_data;
            } catch (error) {
                console.error('番組表の取得に失敗しました:', error);
                this._timetable_channels_yesterday = null;
                this._timetable_channels_today = null;
                this._timetable_channels_tomorrow = null;
            } finally {
                this.is_loading = false;
            }
        },

        /**
         * 表示するチャンネルタイプを設定する
         * @param type 設定するチャンネルタイプ
         */
        setChannelType(type: 'ALL' | ChannelType) {
            this.selected_channel_type = type;
        },

        /**
         * EPG（番組情報）を取得する
         */
        async updateEPG() {
            if (this.is_loading) return;
            this.is_loading = true;

            try {
                const success = await Timetable.updateEPG();
                if (!success) {
                    throw new Error('EPGの取得に失敗しました。');
                }
                // EPG取得後に番組表を再取得
                await this.fetchTimetable();
            } catch (error) {
                console.error('EPG 取得エラー:', error);
                // エラーを上位に投げ直す
                throw error;
            } finally {
                this.is_loading = false;
            }
        },

        /**
         * EPG（番組情報）を再読み込みする
         */
        async reloadEPG() {
            if (this.is_loading) return;
            this.is_loading = true;

            try {
                const success = await Timetable.reloadEPG();
                if (!success) {
                    throw new Error('EPGの再読み込みに失敗しました。');
                }
                // EPG再読み込み後に番組表を再取得
                await this.fetchTimetable();
            } catch (error) {
                console.error('EPG再読み込みエラー:', error);
                // エラーを上位に投げ直す
                throw error;
            } finally {
                this.is_loading = false;
            }
        }
    }
});

export default useTimetableStore;
