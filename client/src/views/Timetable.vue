<template>
    <div class="route-container">
        <HeaderBar />
        <main>
            <Navigation />
            <div class="timetable-container-wrapper">
                <SPHeaderBar />
                <div class="timetable-breadcrumbs-container">
                    <Breadcrumbs :crumbs="[
                        { name: 'ホーム', path: '/' },
                        { name: '番組表', path: '/timetable/', disabled: true },
                    ]" />
                </div>
                <!-- ヘッダー: チャンネルタブ & 日付操作 -->
                <div class="timetable-header">
                    <div class="channels-tab">
                        <div class="channels-tab__buttons" :style="{
                            '--tab-length': channel_types.length,
                            '--active-tab-index': active_tab_index,
                        }">
                            <v-btn variant="flat" class="channels-tab__button"
                                v-for="(type, index) in channel_types" :key="type.id"
                                @click="onClickChannelType(type.id, index)">
                                {{type.name}}
                            </v-btn>
                            <div class="channels-tab__highlight"></div>
                        </div>
                    </div>
                    <div class="timetable-header__date-control">
                        <v-btn variant="flat" icon @click="onClickDateArrow(-1)">
                            <v-icon>mdi-chevron-left</v-icon>
                        </v-btn>
                        <v-menu v-model="is_date_menu_shown" :close-on-content-click="false">
                            <template v-slot:activator="{ props }">
                                <v-btn variant="flat" v-bind="props" class="date-button">
                                    {{ formatDateLabel(selected_date) }}
                                </v-btn>
                            </template>
                            <v-list class="date-list">
                                <v-list-item
                                    v-for="date in dateList"
                                    :key="date.value"
                                    @click="onSelectDate(date.offset)"
                                    :class="{ 'date-list-item--selected': date.offset === timetableStore.selected_day_offset }"
                                >
                                    <v-list-item-title>{{ date.label }}</v-list-item-title>
                                </v-list-item>
                            </v-list>
                        </v-menu>
                        <v-btn variant="flat" icon @click="onClickDateArrow(1)">
                            <v-icon>mdi-chevron-right</v-icon>
                        </v-btn>
                    </div>
                </div>

                <!-- 番組表本体 -->
                <div class="timetable-body">
                    <div v-if="timetableStore.is_loading" class="loading-container">
                        <v-progress-circular indeterminate size="64"></v-progress-circular>
                    </div>
                    <div v-else-if="timetableStore.timetable_channels && timetableStore.timetable_channels.length > 0" class="timetable-grid-container">
                        <div class="corner-cell"></div>
                        <div class="channels-header" :style="gridStyle">
                            <div v-for="channel in timetableStore.timetable_channels" :key="channel.channel.id" class="channel-header-cell">
                                {{ channel.channel.name }}
                            </div>
                        </div>
                        <div class="timeline-container">
                            <div v-for="(label, index) in timelineLabels" :key="index" class="hour-label">
                                <div v-if="label.day !== null" class="day-text">{{ label.day }}</div>
                                <div v-if="label.day !== null" class="dayofweek-text">日</div>
                                <div class="hour-text">{{ label.hour }}</div>
                                <div class="hour-unit">時</div>
                            </div>
                        </div>
                        <div class="programs-grid" :style="programsGridStyle">
                            <div class="current-time-line" :style="currentTimeLineStyle"></div>
                            <div v-for="ch_index in timetableStore.timetable_channels.length" :key="ch_index" class="channel-border" :style="{gridColumn: ch_index}"></div>
                            <div v-for="hour_index in Math.ceil(timetableRange.totalMinutes / 60)" :key="hour_index" class="hour-border" :style="{gridRow: (hour_index * 60) + 1}"></div>
                            <template v-for="(channel, ch_index) in timetableStore.timetable_channels">
                                <template v-for="program in channel.programs" :key="program.id">
                                    <v-tooltip location="top" :disabled="isTooltipDisabled(program)">
                                        <template v-slot:activator="{ props }">
                                            <div v-bind="props" class="program-cell elevation-2"
                                                :style="getProgramStyle(program, ch_index)"
                                                @click="showProgramDetails(program)">
                                                <div class="program-header">
                                                    <div class="program-title">{{ program.title }}</div>
                                                    <div class="program-badges">
                                                        <span v-if="!program.is_free" class="program-badge program-badge--paid">有料</span>
                                                        <span v-if="program.genres.length > 0" class="program-badge program-badge--genre">{{ program.genres[0].major }}</span>
                                                    </div>
                                                </div>
                                                <div class="program-description" v-if="program.description && program.duration >= 900">{{ truncateText(program.description, 50) }}</div>
                                                <div class="program-time">{{ formatTime(program.start_time) }} - {{ formatTime(program.end_time) }} ({{ Math.floor(program.duration / 60) }}分)</div>
                                            </div>
                                        </template>
                                        <span class="tooltip-text">{{ program.title }}</span>
                                    </v-tooltip>
                                </template>
                            </template>
                        </div>
                    </div>
                    <div v-else class="loading-container">
                        <p>番組情報を取得できませんでした。</p>
                        <p>指定された期間・チャンネルに放送される番組がありません。</p>
                    </div>
                </div>

            </div>
        </main>


        <!-- 番組詳細サイドパネル -->
        <v-navigation-drawer v-model="is_panel_shown" location="right" temporary width="600">
            <v-card v-if="selected_program" class="detail-panel">
                <v-card-title class="text-h5 pb-2">{{ selected_program.title }}</v-card-title>
                <v-card-subtitle class="pb-3">{{ formatFullDateTime(selected_program.start_time) }} - {{ formatFullDateTime(selected_program.end_time) }} ({{ Math.floor(selected_program.duration / 60) }}分)</v-card-subtitle>

                <!-- 番組情報バッジ -->
                <v-card-text class="pt-0 pb-2">
                    <div class="program-info-badges">
                        <v-chip v-if="!selected_program.is_free" color="warning" size="small" class="mr-2 mb-2">
                            <v-icon start>mdi-currency-yen</v-icon>
                            有料放送
                        </v-chip>
                        <v-chip v-if="selected_program.video_resolution === '1080i' || selected_program.video_resolution === '1080p'" color="success" size="small" class="mr-2 mb-2">
                            <v-icon start>mdi-high-definition</v-icon>
                            HD
                        </v-chip>
                        <v-chip v-for="genre in selected_program.genres.slice(0, 2)" :key="genre.major" color="primary" variant="outlined" size="small" class="mr-2 mb-2">
                            {{ genre.major }}
                        </v-chip>
                    </div>
                </v-card-text>

                <!-- 番組説明 -->
                <v-card-text class="py-2">
                    <v-divider class="mb-3"></v-divider>
                    <h4 class="text-subtitle-1 mb-2">番組内容</h4>
                    <p class="text-body-2 mb-3">{{ selected_program.description }}</p>

                    <!-- 詳細情報 -->
                    <div v-if="selected_program.detail && Object.keys(selected_program.detail).length > 0" class="program-detail-section">
                        <h4 class="text-subtitle-1 mb-2">詳細情報</h4>
                        <div class="program-detail-grid">
                            <template v-for="(value, key) in selected_program.detail" :key="key">
                                <div class="detail-item">
                                    <span class="detail-key">{{ key }}:</span>
                                    <span class="detail-value">{{ value }}</span>
                                </div>
                            </template>
                        </div>
                    </div>
                </v-card-text>

                <v-card-actions class="detail-panel__actions">
                    <v-spacer></v-spacer>
                    <v-btn :loading="is_reserving" @click="reserveProgram(selected_program.id)" color="primary" variant="elevated">
                        <v-icon start>mdi-record-rec</v-icon>
                        録画予約
                    </v-btn>
                    <v-btn @click="is_panel_shown = false" variant="outlined">閉じる</v-btn>
                </v-card-actions>
            </v-card>
        </v-navigation-drawer>
    </div>
</template>

<script lang="ts" setup>
import { computed, onMounted, onUnmounted, ref, watch ,nextTick} from 'vue';
import { useTimetableStore } from '@/stores/TimetableStore';
import { useSnackbarsStore } from '@/stores/SnackbarsStore';
import { IProgram } from '@/services/Programs';
import Reservations, { IRecordSettings } from '@/services/Reservations';
import Breadcrumbs from '@/components/Breadcrumbs.vue';
import HeaderBar from '@/components/HeaderBar.vue';
import Navigation from '@/components/Navigation.vue';
import SPHeaderBar from '@/components/SPHeaderBar.vue';
import { ChannelType } from '@/services/Channels';

const timetableStore = useTimetableStore();
const snackbarsStore = useSnackbarsStore();

// 録画予約されている番組IDのセット
const reserved_program_ids = ref<Set<string>>(new Set());

const channel_types: {id: 'ALL' | ChannelType, name: string}[] = [
    {id: 'ALL', name: 'すべて'},
    {id: 'GR', name: '地デジ'},
    {id: 'BS', name: 'BS'},
    {id: 'CS', name: 'CS'},
];

const active_tab_index = ref(1); // デフォルトは地デジ（index=1）

const onClickChannelType = (type: 'ALL' | ChannelType, index: number) => {
    timetableStore.setChannelType(type);
    active_tab_index.value = index;
};

// 日付選択メニューの表示状態
const is_date_menu_shown = ref(false);

// 選択された日付を取得
const selected_date = computed(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const targetDate = new Date(today);
    targetDate.setDate(targetDate.getDate() + timetableStore.selected_day_offset);
    return targetDate;
});

// 日付リストを生成（今日を中心に前後1週間分）
const dateList = computed(() => {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const list: { label: string; value: string; offset: number }[] = [];

    for (let i = -7; i <= 7; i++) {
        const date = new Date(today);
        date.setDate(date.getDate() + i);
        const month = date.getMonth() + 1;
        const day = date.getDate();
        const label = i === 0 ? `${month}/${day} 今日` : `${month}/${day}`;
        list.push({
            label,
            value: date.toISOString(),
            offset: i,
        });
    }

    return list;
});

// 日付ラベルをフォーマット
const formatDateLabel = (date: Date) => {
    const month = date.getMonth() + 1;
    const day = date.getDate();
    return `${month}/${day}`;
};

// 矢印ボタンで日付を変更
const onClickDateArrow = async (direction: number) => {
    const newOffset = timetableStore.selected_day_offset + direction;
    // ±7日の範囲内に制限
    if (newOffset >= -7 && newOffset <= 7) {
        timetableStore.selected_day_offset = newOffset;
        // その日付を中心とした3日分を再取得
        await timetableStore.fetchTimetable();
        scrollToSelectedDate();
    }
};

// 日付リストから日付を選択
const onSelectDate = async (offset: number) => {
    timetableStore.selected_day_offset = offset;
    // その日付を中心とした3日分を再取得
    await timetableStore.fetchTimetable();
    scrollToSelectedDate();
    is_date_menu_shown.value = false;
};

// 選択された日付の0時にスクロール
const scrollToSelectedDate = () => {
    nextTick(() => {
        setTimeout(() => {
            const container = document.querySelector('.timetable-grid-container');
            if (!container) return;

            const range = timetableRange.value;
            if (range.totalMinutes === 0) return;

            // 取得したデータの範囲の先頭（昨日の0時）から、
            // 選択した日（今日）の0時までの分数を計算
            // データ構造: 昨日 | 今日(選択した日) | 明日
            // つまり、rangeStartは「昨日の0時」なので、+24時間すれば「今日の0時」
            const scrollTop = 24 * 60 * 6; // 24時間 * 60分 * 6px/分

            container.scrollTo({
                top: scrollTop,
                behavior: 'smooth'
            });
        }, 100);
    });
};

const genre_colors: { [key: string]: { background: string; text: string } } = {
    'ニュース・報道': { background: '#5a88a7', text: '#ffffff' },
    'スポーツ': { background: '#e07f5a', text: '#ffffff' },
    '情報・ワイドショー': { background: '#e7a355', text: '#ffffff' },
    'ドラマ': { background: '#b464a8', text: '#ffffff' },
    '音楽': { background: '#64b46e', text: '#ffffff' },
    'バラエティ': { background: '#e05a8e', text: '#ffffff' },
    '映画': { background: '#a7647e', text: '#ffffff' },
    'アニメ・特撮': { background: '#e76b55', text: '#ffffff' },
    'ドキュメンタリー・教養': { background: '#5a88a7', text: '#ffffff' },
    '劇場・公演': { background: '#a7647e', text: '#ffffff' },
    '趣味・教育': { background: '#64b46e', text: '#ffffff' },
    '福祉': { background: '#5aa788', text: '#ffffff' },
    'その他': { background: '#7f7f7f', text: '#ffffff' },
};
const default_genre_color = { background: 'rgb(var(--v-theme-background-lighten-3))', text: 'rgb(var(--v-theme-text))' };

const now = ref(new Date());
const now_timer = setInterval(() => {
    now.value = new Date();
}, 60 * 1000);
onUnmounted(() => {
    clearInterval(now_timer);
});

const formatTime = (time: string) => {
    const date = new Date(time);
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
};

const formatFullDateTime = (time: string) => {
    const date = new Date(time);
    return `${date.getFullYear()}/${date.getMonth() + 1}/${date.getDate()} ${formatTime(time)}`;
};


const truncateText = (text: string, maxLength: number): string => {
    if (text.length <= maxLength) {
        return text;
    }
    return text.substring(0, maxLength) + '...';
};

const timetableRange = computed(() => {
    const channels = timetableStore.timetable_channels;
    if (!channels || channels.length === 0) {
        return { startTime: new Date(), endTime: new Date(), totalMinutes: 0 };
    }

    let minTime: Date | null = null;
    let maxTime: Date | null = null;

    // BS と CS の番組データを基準に時刻範囲を計算（地デジの時刻がずれている可能性があるため）
    // すべての番組の開始時刻と終了時刻から最小・最大を取得
    channels.forEach(channel => {
        // 地デジ (GR) のチャンネルは時刻計算から除外（BS/CS を基準にする）
        if (channel.channel.type === 'GR') {
            return;
        }
        channel.programs.forEach(program => {
            const startTime = new Date(program.start_time);
            const endTime = new Date(program.end_time);

            if (!minTime || startTime < minTime) {
                minTime = startTime;
            }
            if (!maxTime || endTime > maxTime) {
                maxTime = endTime;
            }
        });
    });

    // BS/CS の番組データがない場合は、すべてのチャンネルから計算（フォールバック）
    if (!minTime || !maxTime) {
        channels.forEach(channel => {
            channel.programs.forEach(program => {
                const startTime = new Date(program.start_time);
                const endTime = new Date(program.end_time);

                if (!minTime || startTime < minTime) {
                    minTime = startTime;
                }
                if (!maxTime || endTime > maxTime) {
                    maxTime = endTime;
                }
            });
        });
    }

    if (!minTime || !maxTime) {
        return { startTime: new Date(), endTime: new Date(), totalMinutes: 0 };
    }

    const totalMinutes = Math.floor(((maxTime as Date).getTime() - (minTime as Date).getTime()) / (1000 * 60));

    return { startTime: minTime as Date, endTime: maxTime as Date, totalMinutes };
});

const timelineLabels = computed(() => {
    if (timetableRange.value.totalMinutes === 0) return [];

    const labels: { hour: number, day: number | null }[] = [];
    const start = new Date(timetableRange.value.startTime);
    const end = new Date(timetableRange.value.endTime);

    let current = new Date(start);
    current.setMinutes(0, 0, 0);

    while (current <= end) {
        const hour = current.getHours();
        const isDayStart = hour === 0;

        labels.push({
            hour,
            day: isDayStart ? current.getDate() : null,
        });

        current.setHours(current.getHours() + 1);
    }

    return labels;
});


const gridStyle = computed(() => {
    const channelCount = timetableStore.timetable_channels?.length || 0;
    if (channelCount === 0) {
        return { 'grid-template-columns': 'none' };
    }
    return {
        'grid-template-columns': `repeat(${channelCount}, minmax(200px, 1fr))`,
    };
});

const programsGridStyle = computed(() => {
    const channelCount = timetableStore.timetable_channels?.length || 0;
    if (channelCount === 0) {
        return {
            'grid-template-columns': 'none',
            'grid-template-rows': 'none',
        };
    }
    return {
        'grid-template-columns': `repeat(${channelCount}, minmax(200px, 1fr))`,
        'grid-template-rows': `repeat(${timetableRange.value.totalMinutes}, 6px)`,
    };
});

const getProgramStyle = (program: IProgram, ch_index: number) => {
    const start = new Date(program.start_time);
    const end = new Date(program.end_time);
    const baseTime = timetableRange.value.startTime;

    // 地デジの番組データの時刻が15分ずれている可能性があるため、地デジのチャンネルの場合は15分補正
    const channel = timetableStore.timetable_channels?.[ch_index];
    if (channel && channel.channel.type === 'GR') {
        // 地デジの番組の時刻を15分進める（15分ずれている場合の補正）
        start.setMinutes(start.getMinutes() + 15);
        end.setMinutes(end.getMinutes() + 15);
    }

    // 基準時刻からの経過分数を計算
    const minutesFromStart = Math.floor((start.getTime() - baseTime.getTime()) / (1000 * 60));
    const duration_minutes = program.duration / 60;

    const genre = program.genres[0]?.major || 'その他';
    const color = genre_colors[genre] || default_genre_color;
    const style: { [key: string]: any } = {
        'grid-column': ch_index + 1,
        'grid-row-start': minutesFromStart + 1,
        'grid-row-end': minutesFromStart + duration_minutes + 1,
        'background-color': color.background,
        'color': color.text,
        'border-color': color.background,
    };

    // 録画予約されている番組の場合は白い点線の枠を表示
    if (reserved_program_ids.value.has(program.id)) {
        style['border'] = '2px dashed #FFFFFF';
        style['border-color'] = '#FFFFFF';
    }

    return style;
};

const currentTimeLineStyle = computed(() => {
    if (timetableRange.value.totalMinutes === 0) {
        return { top: '0px' };
    }

    const baseTime = timetableRange.value.startTime;
    const current = new Date(now.value);

    const minutesFromStart = Math.floor((current.getTime() - baseTime.getTime()) / (1000 * 60));

    if (minutesFromStart < 0 || minutesFromStart > timetableRange.value.totalMinutes) {
        return { top: '-9999px' };
    }

    return {
        top: `${minutesFromStart * 6}px`,
    };
});

const isTooltipDisabled = (program: IProgram) => {
    return program.duration / 60 > 15;
};

const is_panel_shown = ref(false);
const selected_program = ref<IProgram | null>(null);
const showProgramDetails = (program: IProgram) => {
    selected_program.value = program;
    is_panel_shown.value = true;
};

// 録画予約一覧を取得する
const fetchReservations = async () => {
    const reservations = await Reservations.fetchReservations();
    if (reservations) {
        // 録画予約されている番組IDのセットを更新
        reserved_program_ids.value = new Set(reservations.reservations.map(r => r.program.id));
    }
};

const is_reserving = ref(false);
const reserveProgram = async (program_id: string) => {
    is_reserving.value = true;
    const default_settings: IRecordSettings = {
        is_enabled: true,
        priority: 3,
        recording_folders: [],
        recording_start_margin: null,
        recording_end_margin: null,
        recording_mode: 'SpecifiedService',
        caption_recording_mode: 'Default',
        data_broadcasting_recording_mode: 'Default',
        post_recording_mode: 'Default',
        post_recording_bat_file_path: null,
        is_event_relay_follow_enabled: true,
        is_exact_recording_enabled: false,
        is_oneseg_separate_output_enabled: false,
        is_sequential_recording_in_single_file_enabled: false,
        forced_tuner_id: null,
    };
    const success = await Reservations.addReservation(program_id, default_settings);
    if (success) {
        snackbarsStore.show('success', '録画予約を追加しました。');
        is_panel_shown.value = false;
        // 録画予約一覧を再取得して表示を更新
        await fetchReservations();
    } else {
        snackbarsStore.show('error', '録画予約の追加に失敗しました。');
    }
    is_reserving.value = false;
};


onMounted(async () => {
    timetableStore.setChannelType('GR');
    timetableStore.current_date = new Date();
    timetableStore.selected_day_offset = 0; // 今日を中心に表示
    // 番組表と録画予約一覧を並行して取得
    await Promise.all([
        timetableStore.fetchTimetable(),
        fetchReservations(),
    ]);
});

const scrollToCurrentTime = () => {
    nextTick(() => {
        setTimeout(() => {
            const container = document.querySelector('.timetable-grid-container');
            if (!container) return;

            if (timetableRange.value.totalMinutes === 0) return;

            const baseTime = timetableRange.value.startTime;
            const current = new Date(now.value);

            const minutesFromStart = Math.floor((current.getTime() - baseTime.getTime()) / (1000 * 60));
            const scroll_top = (minutesFromStart * 6) - 200;
            container.scrollTo({
                top: scroll_top > 0 ? scroll_top : 0,
                behavior: 'smooth',
            });
        }, 100);
    });
};

const is_initial_load = ref(true);
watch(() => timetableStore.timetable_channels, (new_channels) => {
    if (is_initial_load.value && new_channels && new_channels.length > 0) {
        scrollToCurrentTime();
        is_initial_load.value = false;
    }
});

</script>

<style lang="scss">
html:has(.timetable-container-wrapper) {
    scrollbar-gutter: auto !important;
    @media (max-width: 960px) and (orientation: landscape) {
        scrollbar-gutter: stable !important;
    }
    @media (max-width: 600px) and (orientation: portrait) {
        scrollbar-gutter: stable !important;
    }
}
</style>

<style lang="scss" scoped>
.timetable-container-wrapper {
    width: 100%;
    height: calc(100vh - 65px);
    min-width: 0;
    display: flex;
    flex-direction: column;
    @include smartphone-horizontal {
        height: 100vh;
    }
    @include smartphone-vertical {
        height: calc(100vh - 56px - env(safe-area-inset-bottom));
    }
}

.timetable-breadcrumbs-container {
    padding-top: 20px;
    padding-left: 21px;
    padding-right: 21px;
    padding-bottom: 0;
    margin-top: 0;
    margin-bottom: 0;
    flex-shrink: 0;
    @include smartphone-horizontal {
        padding-left: 0;
        padding-right: 0;
    }
    @include smartphone-vertical {
        display: none;
    }
}

.timetable-header {
    width: 100%;
    background: rgb(var(--v-theme-background));
    z-index: 10;
    flex-shrink: 0;
    margin-top: 0;
    margin-bottom: 0;
    padding-top: 0;
    padding-left: 21px;
    padding-right: 21px;
    padding-bottom: 0;

    @include smartphone-horizontal {
        padding-left: 0;
        padding-right: 0;
    }

    @include smartphone-vertical {
        padding-left: 0;
        padding-right: 0;
    }

    &__date-control {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 8px;
        padding: 0;
        border-bottom: 1px solid #333;

        :deep(.v-btn) {
            height: auto;
            min-height: 0;
            border-radius: 2.5px;
            color: rgb(var(--v-theme-text)) !important;
            background-color: transparent !important;
            text-transform: none;
            box-shadow: none !important;
        }

        :deep(.v-btn.date-button) {
            padding: 6px 16px;
            font-size: 15px;
            font-weight: 500;
            letter-spacing: 0.0892857143em !important;
            min-width: 120px;
        }

        :deep(.v-btn[icon]) {
            width: 40px;
            height: 40px;
            padding: 0;
        }
    }
}

.date-list {
    max-height: 400px;
    overflow-y: auto;

    .v-list-item {
        cursor: pointer;
        transition: background-color 0.2s;

        &:hover {
            background-color: rgba(var(--v-theme-primary), 0.1);
        }
    }

    .date-list-item--selected {
        background-color: rgba(var(--v-theme-primary), 0.2);
        font-weight: bold;

        :deep(.v-list-item-title) {
            color: rgb(var(--v-theme-primary));
        }
    }
}

.channels-tab {
    display: flex;
    margin-top: 0;
    margin-bottom: 0;
    padding-top: 0;
    padding-bottom: 0;
    .channels-tab__buttons {
        display: flex;
        position: relative;
        align-items: center;
        margin-top: 0;
        margin-left: auto;
        margin-right: auto;
        margin-bottom: 0;
        padding-top: 0;
        padding-bottom: 0;

        .channels-tab__button {
            display: flex;
            align-items: center;
            justify-content: center;
            width: 98px;
            padding: 6px 0 10px 0;
            border-radius: 2.5px;
            color: rgb(var(--v-theme-text)) !important;
            background-color: transparent !important;
            font-size: 15px;
            letter-spacing: 0.0892857143em !important;
            text-transform: none;
            cursor: pointer;
            @include smartphone-vertical {
                width: 90px;
                font-size: 14px;
            }
        }

        .channels-tab__highlight {
            position: absolute;
            left: 0;
            bottom: 4px;
            width: 98px;
            height: 3px;
            background: rgb(var(--v-theme-primary));
            transition: transform 0.3s cubic-bezier(0.25, 0.8, 0.5, 1);
            transform: translateX(calc(98px * var(--active-tab-index, 0)));
            will-change: transform;
            @include smartphone-vertical {
                width: 90px;
                transform: translateX(calc(90px * var(--active-tab-index, 0)));
            }
        }
    }
}

.timetable-body {
    flex: 1;
    width: 100%;
    overflow: hidden;
    min-height: 0;
}

.loading-container {
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100%;
}

.timetable-grid-container {
    height: 100%;
    width: 100%;
    display: grid;
    grid-template-rows: auto 1fr;
    grid-template-columns: auto 1fr;
    overflow: scroll;

    @include smartphone-horizontal {
        scrollbar-width: none;
        -ms-overflow-style: none;
        &::-webkit-scrollbar {
            display: none;
        }
    }

    @include smartphone-vertical {
        grid-template-rows: auto auto 1fr;
        scrollbar-width: none;
        -ms-overflow-style: none;
        &::-webkit-scrollbar {
            display: none;
        }
    }
}

.corner-cell {
    position: sticky;
    top: 0;
    left: 0;
    z-index: 7;
    background: rgb(var(--v-theme-background));
}

.channels-header {
    grid-column: 2;
    display: grid;
    position: sticky;
    top: 0;
    z-index: 5;
    background: rgb(var(--v-theme-background));

    .channel-header-cell {
        padding: 6px 8px;
        text-align: center;
        font-weight: bold;
        font-size: 14px;
        border-right: 1px solid #333;
    }
}

.timeline-container {
    grid-row: 2;
    width: 30px;
    position: sticky;
    left: 0;
    z-index: 6;
    background: rgb(var(--v-theme-background));

    .hour-label {
        position: relative;
        height: 360px;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-start;
        padding-top: 4px;
        font-size: 14px;
        color: rgb(var(--v-theme-text));

        .day-text,
        .dayofweek-text,
        .hour-text,
        .hour-unit {
            font-size: 14px;
            font-weight: normal;
            line-height: 1.4;
        }
    }
}

.programs-grid {
    grid-row: 2;
    grid-column: 2;
    display: grid;
    position: relative;

    .channel-border {
        grid-row: 1 / -1;
        border-right: 1px solid #333;
    }
    .hour-border {
        grid-column: 1 / -1;
        border-top: 1px dotted #333;
    }

    .current-time-line {
        position: absolute;
        width: 100%;
        height: 3px;
        background: #E53935;
        z-index: 3;
    }
}

.program-cell {
    margin: 1px;
    padding: 4px;
    border-radius: 4px;
    cursor: pointer;
    overflow: hidden;
    transition: filter 0.2s, transform 0.2s;
    text-orientation: mixed;
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: 30px;

    &:hover {
        filter: brightness(1.1);
        transform: scale(1.02);
        z-index: 2;
    }

    .program-header {
        display: flex;
        flex-direction: column;
        gap: 4px;
    }

    .program-title {
        font-weight: bold;
        font-size: 0.8em;
        line-height: 1.2;
        word-break: break-word;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
        overflow: hidden;
    }

    .program-badges {
        display: flex;
        flex-wrap: wrap;
        gap: 2px;
    }

    .program-badge {
        font-size: 0.7em;
        padding: 1px 4px;
        border-radius: 3px;
        font-weight: 500;
        white-space: nowrap;

        &--paid {
            background-color: rgba(255, 193, 7, 0.9);
            color: #000;
        }

        &--genre {
            background-color: rgba(255, 255, 255, 0.2);
            color: inherit;
        }
    }

    .program-description {
        font-size: 0.7em;
        line-height: 1.2;
        opacity: 0.9;
        word-break: break-word;
        flex-grow: 1;
        overflow: hidden;
        display: -webkit-box;
        -webkit-line-clamp: 2;
        line-clamp: 2;
        -webkit-box-orient: vertical;
    }

    .program-time {
        font-size: 0.8em;
        opacity: 0.8;
        margin-top: auto;
        white-space: nowrap;
    }
}

.tooltip-text {
    font-size: 14px;
    color: rgb(var(--v-theme-text));
}

.detail-panel {
    &__actions {
        position: sticky;
        bottom: 0;
        background: rgb(var(--v-theme-background));
        border-top: 1px solid rgb(var(--v-theme-background-lighten-2));
        padding: 16px;
    }
}

.program-info-badges {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}

.program-detail-section {
    margin-bottom: 16px;
}

.program-detail-grid {
    display: flex;
    flex-direction: column;
    gap: 8px;

    .detail-item {
        display: flex;
        padding: 8px 0;
        border-bottom: 1px solid rgba(var(--v-theme-on-surface), 0.1);

        .detail-key {
            font-weight: 600;
            min-width: 80px;
            margin-right: 12px;
            color: rgb(var(--v-theme-primary));
        }

        .detail-value {
            flex: 1;
            word-break: break-word;
        }
    }
}

</style>
