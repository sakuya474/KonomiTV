<template>
    <SettingsBase>
        <h2 class="settings__heading">
            <a v-ripple class="settings__back-button" @click="$router.back()">
                <Icon icon="fluent:chevron-left-12-filled" width="27px" />
            </a>
            <Icon icon="fluent:video-clip-wand-16-filled" width="19px" style="margin: 0 4px;" />
            <span class="ml-3">エンコード</span>
        </h2>
        <div class="settings__description">
            録画終了時の自動エンコードと録画一覧からの手動再エンコードの設定を行えます。<br>
            TSReplaceを使用してH.262-TSからH.264/HEVCへの映像変換を行い、ファイルサイズの削減と互換性の向上を図ります。
        </div>
        <div class="settings__description">
            サーバー設定を変更するには、管理者アカウントでログインしている必要があります。<br>
        </div>
        <div class="settings__description mt-1">
            [サーバー設定を更新] ボタンを押さずにこのページから離れると、変更内容は破棄されます。<br>
            変更を反映するには KonomiTV サーバーの再起動が必要です。<br>
        </div>

        <!-- 基本エンコード設定 -->
        <div class="settings__content" v-if="server_settings">
            <div class="settings__content-heading">
                <Icon icon="fluent:settings-16-filled" width="20px" />
                <span class="ml-3">基本設定</span>
            </div>
            <div class="settings__item settings__item--switch">
                <label class="settings__item-heading" for="auto_encoding">自動エンコード</label>
                <label class="settings__item-label" for="auto_encoding">
                    録画終了時に自動的にエンコードを行います。<br>
                </label>
                <v-switch class="settings__item-switch" color="primary" id="auto_encoding" hide-details
                    v-model="server_settings.tsreplace_encoding.auto_encoding_enabled"
                    :disabled="is_disabled">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">エンコードコーデック</div>
                <div class="settings__item-label">
                    エンコードに使用するビデオコーデックを選択します。<br>
                    H.264は高い互換性、H.265(HEVC)はより高い圧縮効率を提供しますが処理時間が長くなります。
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined"
                    :items="[
                        { title: 'H.264 (AVC)', value: 'h264' },
                        { title: 'H.265 (HEVC)', value: 'hevc' }
                    ]"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.auto_encoding_codec"
                    :disabled="is_auto_encoding_disabled"
                    hide-details>
                </v-select>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">エンコーダー種類</div>
                <div class="settings__item-label">
                    ソフトウェアエンコードは高品質、ハードウェアエンコードは高速処理が可能です。<br>
                    ハードウェアエンコードを使用する場合は、対応するGPUが必要です。
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined"
                    :items="encoder_options"
                    v-model="server_settings.tsreplace_encoding.auto_encoding_encoder"
                    :density="is_form_dense ? 'compact' : 'default'"
                    :disabled="is_auto_encoding_disabled"
                    hide-details
                    item-title="title"
                    item-value="value"
                    item-key="key">
                    <template v-slot:item="{ props, item }">
                        <v-list-item v-bind="props"
                            :disabled="item.raw.disabled"
                            :subtitle="item.raw.subtitle">
                        </v-list-item>
                    </template>
                </v-select>
            </div>
            <div class="settings__item" v-show="server_settings.tsreplace_encoding.auto_encoding_encoder === 'hardware'">
                <div class="settings__item-heading">ハードウェアエンコーダー種類</div>
                <div class="settings__item-label">
                    使用するGPUエンコーダーの種類を選択します。<br>
                    お使いのGPUに対応したエンコーダーを選択してください。
                </div>
                <v-select class="settings__item-form" color="primary" variant="outlined"
                    :items="[
                        { title: 'NVEncC : NVIDIA GPU で利用可能', value: 'nvidia' },
                        { title: 'VCEEncC : AMD GPU で利用可能', value: 'amd' },
                        { title: 'QSVEncC : Intel Graphics 搭載 CPU / Intel Arc GPU で利用可能', value: 'intel' }
                    ]"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.hardware_encoder_type"
                    :disabled="is_auto_encoding_disabled"
                    hide-details>
                </v-select>
            </div>
                <div class="settings__item settings__item--switch">
                <label class="settings__item-heading">エンコード完了後に元ファイルを削除</label>
                <label class="settings__item-label" for="delete_original_after_encoding">
                    エンコード完了後に元のTSファイルを自動的に削除します。<br>
                    ストレージ容量の節約になりますが、元ファイルは復元できないため注意してください。
                </label>
                <v-switch class="settings__item-switch" color="primary" id="delete_original_after_encoding" hide-details
                    v-model="server_settings.tsreplace_encoding.delete_original_after_encoding"
                    :disabled="is_auto_encoding_disabled">
                </v-switch>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">最大同時エンコード数</div>
                <div class="settings__item-label">
                    同時に実行できるエンコード処理の最大数を設定します。<br>
                    値を大きくするとより多くのファイルを並行処理できますが、システムリソースを多く消費します。
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    type="number" min="1" max="10"
                    :rules="[validateMaxConcurrentEncodings]"
                    v-model.number="server_settings.tsreplace_encoding.max_concurrent_encodings"
                    :disabled="is_auto_encoding_disabled">
                </v-text-field>
            </div>
            <div class="settings__item">
                <div class="settings__item-heading">エンコード済みファイルの保存先フォルダ</div>
                <div class="settings__item-label">
                    エンコード済みファイルの保存先フォルダの絶対パスを指定してください。<br>
                    空欄にすると、録画フォルダ内に Encoded フォルダを自動作成します。
                </div>
                <v-text-field class="settings__item-form" color="primary" variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    placeholder="例: E:\Encoded"
                    v-model="server_settings.tsreplace_encoding.encoded_folder"
                    :disabled="is_disabled">
                </v-text-field>
            </div>

            <v-btn class="settings__save-button bg-secondary mt-6" variant="flat"
                :disabled="is_disabled" @click="updateServerSettings()">
                <Icon icon="fluent:save-16-filled" class="mr-2" height="23px" />エンコード設定を更新
            </v-btn>

            <!-- コマンドラインオプション設定 -->
             <div class="settings__content-heading mt-6">
                <Icon icon="fluent:developer-board-16-filled" width="20px" />
                <span class="ml-2">コマンドラインオプション</span>
            </div>
            <div class="settings__description">
                高度なエンコーディング設定です。よくわからない場合はそのままにしてください。<br>
            </div>
            <!-- ソフトウェアエンコード設定 -->
            <div class="settings__item">
                <div class="settings__item-heading">
                    ソフトウェアエンコード (CPU) H.264 オプション
                    <v-chip size="small" color="blue-darken-1" variant="outlined" class="ml-2">
                        <span>libx264</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    TSReplace経由でFFmpegのlibx264エンコーダーを使用します。高い互換性を持ちます。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.ffmpeg_h264_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <div class="settings__item">
                <div class="settings__item-heading">
                    ソフトウェアエンコード (CPU) H.265 オプション
                    <v-chip size="small" color="purple-darken-1" variant="outlined" class="ml-2">
                        <span>libx265</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    TSReplace経由でFFmpegのlibx265エンコーダーを使用します。H.264より高い圧縮効率を持ちますが、エンコード時間が長くなります。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.ffmpeg_hevc_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <!-- ハードウェアエンコード設定 (NVIDIA) -->
            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'nvidia'">
                <div class="settings__item-heading">
                    NVIDIA GPU H.264 エンコードオプション
                    <v-chip size="small" color="green-darken-1" variant="outlined" class="ml-2">
                        <span>NVEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    NVIDIA GPU使用時のH.264エンコード設定です（NVEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.nvidia_h264_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'nvidia'">
                <div class="settings__item-heading">
                    NVIDIA GPU H.265 エンコードオプション
                    <v-chip size="small" color="green-darken-2" variant="outlined" class="ml-2">
                        <span>NVEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    NVIDIA GPU使用時のH.265エンコード設定です（NVEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.nvidia_hevc_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <!-- ハードウェアエンコード設定 (AMD) -->
            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'amd'">
                <div class="settings__item-heading">
                    AMD GPU H.264 エンコードオプション
                    <v-chip size="small" color="red-darken-1" variant="outlined" class="ml-2">
                        <span>VCEEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    AMD GPU使用時のH.264エンコード設定です（VCEEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.amd_h264_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'amd'">
                <div class="settings__item-heading">
                    AMD GPU H.265 エンコードオプション
                    <v-chip size="small" color="red-darken-2" variant="outlined" class="ml-2">
                        <span>VCEEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    AMD GPU使用時のH.265エンコード設定です（VCEEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.amd_hevc_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <!-- ハードウェアエンコード設定 (Intel) -->
            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'intel'">
                <div class="settings__item-heading">
                    Intel GPU H.264 エンコードオプション
                    <v-chip size="small" color="blue-darken-1" variant="outlined" class="ml-2">
                        <span>QSVEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    Intel GPU使用時のH.264エンコード設定です（QSVEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.intel_h264_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>

            <div class="settings__item" v-show="server_settings.tsreplace_encoding.hardware_encoder_type === 'intel'">
                <div class="settings__item-heading">
                    Intel GPU H.265 エンコードオプション
                    <v-chip size="small" color="blue-darken-2" variant="outlined" class="ml-2">
                        <span>QSVEncC</span>
                    </v-chip>
                </div>
                <div class="settings__item-label">
                    Intel GPU使用時のH.265エンコード設定です（QSVEncC経由）。<br>
                    <span v-if="is_auto_encoding_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定は自動エンコードが有効な場合のみ変更可能です。</strong></span>
                    <span v-else-if="is_disabled" class="text-orange-500 d-block mt-1"><strong>※ この設定の変更には管理者権限が必要です。</strong></span>
                </div>
                <v-text-field
                    class="settings__item-form"
                    color="primary"
                    variant="outlined"
                    :density="is_form_dense ? 'compact' : 'default'"
                    v-model="server_settings.tsreplace_encoding.intel_hevc_options"
                    prepend-inner-icon="fluent:code-16-filled"
                    hide-details>
                </v-text-field>
            </div>
        </div>

        <!-- エンコードタスク表示 -->
        <div class="settings__content" v-if="server_settings">
            <div class="settings__content-heading">
                <Icon icon="fluent:task-list-square-16-filled" width="20px" />
                <span class="ml-3">エンコードタスク</span>
            </div>
            <div class="settings__item">
                <div class="settings__item-label">
                    現在実行中および完了したエンコードタスクの一覧です。
                </div>
                <div class="encoding-tasks-container">
                    <div v-if="encodingTasks.length === 0" class="encoding-tasks-empty">
                        エンコードタスクはありません。
                    </div>
                    <div v-else class="encoding-tasks-list">
                        <div v-for="task in encodingTasks" :key="task.taskId" class="encoding-task-item">
                            <div class="encoding-task-header">
                                <div class="encoding-task-title">{{ task.programTitle }}</div>
                                <div class="encoding-task-actions">
                                    <v-btn v-if="canCancelTask(task.status)"
                                        size="x-small"
                                        variant="flat"
                                        color="error"
                                        @click="cancelTask(task.taskId)"
                                        :loading="cancellingTasks.has(task.taskId)">
                                        <Icon icon="fluent:stop-20-regular" width="14px" height="14px" />
                                        <span class="ml-1">キャンセル</span>
                                    </v-btn>
                                    <v-btn v-if="canDeleteTask(task.status)"
                                        size="x-small"
                                        variant="flat"
                                        color="grey"
                                        @click="deleteTask(task.taskId)">
                                        <Icon icon="fluent:delete-20-regular" width="14px" height="14px" />
                                        <span class="ml-1">削除</span>
                                    </v-btn>
                                    <v-chip
                                        :color="getStatusColor(task.status)"
                                        size="small"
                                        variant="flat"
                                    >
                                        {{ getStatusText(task.status) }}
                                    </v-chip>
                                </div>
                            </div>
                            <div class="encoding-task-details">
                                <div class="encoding-task-info">
                                    <span class="encoding-task-codec">{{ task.codec.toUpperCase() }}</span>
                                    <span class="encoding-task-encoder">{{ getEncoderText(task.encoderType) }}</span>
                                </div>
                                <div v-if="task.status === 'processing'" class="encoding-task-progress">
                                    <v-progress-linear
                                        :model-value="task.progress"
                                        color="primary"
                                        height="6"
                                        rounded
                                    ></v-progress-linear>
                                    <span class="encoding-task-progress-text">{{ formatProgress(task.progress) }}%</span>
                                </div>
                                <div v-if="task.errorMessage" class="encoding-task-error">
                                    <Icon icon="fluent:error-circle-16-filled" width="16px" class="text-error" />
                                    <span class="text-error">{{ task.errorMessage }}</span>
                                </div>
                                <div v-if="task.startedAt" class="encoding-task-time">
                                    開始: {{ formatDateTime(task.startedAt) }}
                                </div>
                                <div v-if="task.completedAt" class="encoding-task-time">
                                    完了: {{ formatDateTime(task.completedAt) }}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </SettingsBase>
</template>

<script setup lang="ts">

import { computed, ref, onMounted, onUnmounted } from 'vue';

import Message from '@/message';
import Settings from '@/services/Settings';
import useUserStore from '@/stores/UserStore';
import useTSReplaceEncodingStore from '@/stores/TSReplaceEncodingStore';
import Utils from '@/utils/Utils';
import SettingsBase from '@/views/Settings/Base.vue';

// ストア
const userStore = useUserStore();
const encodingStore = useTSReplaceEncodingStore();

// サーバー設定を ref として保持（初期値をnullに設定）
const server_settings = ref<any>(null);

// ハードウェアエンコーダーの利用可否
const hardware_encoder_available = ref<boolean>(false);

// キャンセル中のタスクIDを追跡
const cancellingTasks = ref<Set<string>>(new Set());

// サーバー設定をロード
async function loadServerSettings() {
    const settings = await Settings.fetchServerSettings();
    server_settings.value = settings;
}

// ハードウェアエンコーダーの利用可否を確認
async function checkHardwareEncoderAvailability() {
    try {
        const status = await Settings.fetchHardwareEncoderStatus();
        hardware_encoder_available.value = status.hardware_encoder_available;
    } catch (error) {
        console.error('Failed to check hardware encoder availability:', error);
        hardware_encoder_available.value = false;
    }
}

// エンコーダー選択肢（ハードウェアエンコーダーの利用可否によって動的に変更）
const encoder_options = computed(() => {
    if (hardware_encoder_available.value) {
        return [
            { title: 'ソフトウェア (CPU)', value: 'software', disabled: false, key: 'software' },
            { title: 'ハードウェア (GPU)', value: 'hardware', disabled: false, key: 'hardware' }
        ];
    } else {
        return [
            { title: 'ソフトウェア (CPU)', value: 'software', disabled: false, key: 'software' },
            {
                title: 'ハードウェア (GPU)',
                value: 'hardware',
                disabled: true,
                subtitle: '使用できません（対応するGPUが検出されませんでした）',
                key: 'hardware-disabled'
            }
        ];
    }
});// フォームのサイズ
const is_form_dense = computed(() => Utils.isSmartphoneHorizontal());

// 現在のユーザーが管理者かどうか（管理者のみコマンドラインオプションを変更可能）
const is_disabled = computed(() => userStore.user === null || userStore.user.is_admin === false);

// 自動エンコードが無効かどうか
const is_auto_encoding_disabled = computed(() =>
    !server_settings.value?.tsreplace_encoding?.auto_encoding_enabled || is_disabled.value
);

// エンコードタスク一覧（重複を排除）
const encodingTasks = computed(() => {
    const allTasks = encodingStore.getAllTasks();

    // taskIdで重複を排除（最新のものを保持）
    const taskMap = new Map<string, typeof allTasks[0]>();
    for (const task of allTasks) {
        const existing = taskMap.get(task.taskId);
        if (!existing) {
            taskMap.set(task.taskId, task);
        } else {
            // 既に存在する場合、startedAtが新しい方を保持
            if (task.startedAt && existing.startedAt) {
                if (task.startedAt.getTime() > existing.startedAt.getTime()) {
                    taskMap.set(task.taskId, task);
                }
            } else if (task.startedAt) {
                taskMap.set(task.taskId, task);
            }
        }
    }

    // 重複排除後のタスクをソート
    return Array.from(taskMap.values()).sort((a, b) => {
        // 実行中 > 待機中 > 完了 > 失敗の順で表示
        const statusOrder = { 'processing': 0, 'queued': 1, 'completed': 2, 'failed': 3, 'cancelled': 4 };
        const aOrder = statusOrder[a.status] ?? 5;
        const bOrder = statusOrder[b.status] ?? 5;
        if (aOrder !== bOrder) {
            return aOrder - bOrder;
        }
        // 同じステータスの場合は開始時刻でソート（新しい順）
        if (a.startedAt && b.startedAt) {
            return b.startedAt.getTime() - a.startedAt.getTime();
        }
        return 0;
    });
});

// バリデーション
function validateMaxConcurrentEncodings(value: number): boolean | string {
    if (value < 1 || value > 10) {
        return '1以上10以下の値を入力してください。';
    }
    return true;
}

// エンコードタスク表示用のヘルパー関数
function getStatusColor(status: string): string {
    switch (status) {
        case 'processing': return 'primary';
        case 'queued': return 'warning';
        case 'completed': return 'success';
        case 'failed': return 'error';
        case 'cancelled': return 'grey';
        default: return 'grey';
    }
}

function getStatusText(status: string): string {
    switch (status) {
        case 'processing': return '実行中';
        case 'queued': return '待機中';
        case 'completed': return '完了';
        case 'failed': return '失敗';
        case 'cancelled': return 'キャンセル';
        default: return status;
    }
}

function getEncoderText(encoderType: string): string {
    switch (encoderType) {
        case 'software': return 'ソフトウェア';
        case 'hardware': return 'ハードウェア';
        default: return encoderType;
    }
}

function formatDateTime(date: Date): string {
    return date.toLocaleString('ja-JP', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });
}

function formatProgress(progress: number): string {
    return progress.toFixed(1);
}

// エンコードタスクの操作関数
function canCancelTask(status: string): boolean {
    const isAdmin = userStore.user !== null && userStore.user.is_admin === true;
    return isAdmin && ['queued', 'processing'].includes(status);
}

function canDeleteTask(status: string): boolean {
    const isAdmin = userStore.user !== null && userStore.user.is_admin === true;
    return isAdmin && ['completed', 'failed', 'cancelled'].includes(status);
}

async function cancelTask(taskId: string) {
    if (cancellingTasks.value.has(taskId)) return;

    cancellingTasks.value.add(taskId);
    try {
        const TSReplace = await import('@/services/TSReplace');
        const success = await TSReplace.default.cancelEncoding(taskId);
        // キャンセル要求は静かに実行（ポップアップを表示しない）
    } catch (error) {
        console.error('Failed to cancel encoding:', error);
        Message.error('エンコードのキャンセルに失敗しました。');
    } finally {
        cancellingTasks.value.delete(taskId);
    }
}

async function deleteTask(taskId: string) {
    await encodingStore.removeTask(taskId);
    // ポップアップを表示せずに静かに削除
}

// サーバー設定を更新する関数
async function updateServerSettings() {
    if (server_settings.value === null) return;

    // ハードウェアエンコーダーが利用できない場合で、ハードウェアが選択されている場合はソフトウェアに切り替え
    if (!hardware_encoder_available.value && server_settings.value.tsreplace_encoding.auto_encoding_encoder === 'hardware') {
        server_settings.value.tsreplace_encoding.auto_encoding_encoder = 'software';
        Message.warning('ハードウェアエンコーダーが利用できないため、ソフトウェアエンコードに切り替えました。');
    }

    // サーバー設定を更新
    const result = await Settings.updateServerSettings(server_settings.value);

    // 成功した場合のみメッセージを表示
    // エラー処理は Services 層で行われるため、ここではエラー処理は不要
    // 再起動するまでは設定データは反映されないため、再起動せずにページをリロードすると反映されてないように見える点に注意
    if (result === true) {
        Message.success('エンコード設定を更新しました。\n変更を反映するためには、KonomiTV サーバーを再起動してください。');
    }
}

// コンポーネントマウント時に設定をロード
onMounted(async () => {
    await Promise.all([
        loadServerSettings(),
        checkHardwareEncoderAvailability()
    ]);

    // エンコードストアを初期化
    encodingStore.initializeWebSocket();
    encodingStore.startPeriodicCleanup();
    encodingStore.startPeriodicRefresh();
    await encodingStore.refreshEncodingQueue();
});

// コンポーネントアンマウント時のクリーンアップ
onUnmounted(() => {
    // WebSocket接続は他のコンポーネントでも使用される可能性があるため、
    // ここでは明示的に切断しない
});

</script>

<style scoped>
/* エンコードタスク表示用のスタイル */
.encoding-tasks-container {
    margin-top: 16px;
}

.encoding-tasks-empty {
    text-align: center;
    color: rgb(var(--v-theme-on-surface-variant));
    padding: 24px;
    font-style: italic;
}

.encoding-tasks-list {
    display: flex;
    flex-direction: column;
    gap: 12px;
}

.encoding-task-item {
    border: 1px solid rgb(var(--v-theme-outline-variant));
    border-radius: 8px;
    padding: 16px;
    background: rgb(var(--v-theme-surface));
}

.encoding-task-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}

.encoding-task-title {
    font-weight: 600;
    font-size: 14px;
    color: rgb(var(--v-theme-on-surface));
    flex: 1;
    margin-right: 12px;
    word-break: break-word;
    line-height: 1.4;
}

.encoding-task-actions {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-shrink: 0;
}

.encoding-task-details {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.encoding-task-info {
    display: flex;
    gap: 12px;
    font-size: 12px;
    color: rgb(var(--v-theme-on-surface));
}

.encoding-task-codec {
    background: rgb(var(--v-theme-primary-container));
    color: rgb(var(--v-theme-on-primary-container));
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 500;
}

.encoding-task-encoder {
    background: rgb(var(--v-theme-secondary-container));
    color: rgb(var(--v-theme-on-secondary-container));
    padding: 2px 6px;
    border-radius: 4px;
    font-weight: 500;
}

.encoding-task-progress {
    display: flex;
    align-items: center;
    gap: 8px;
}

.encoding-task-progress-text {
    font-size: 12px;
    color: rgb(var(--v-theme-on-surface));
    min-width: 40px;
    text-align: right;
    font-weight: 500;
}

.encoding-task-error {
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
}

.encoding-task-time {
    font-size: 12px;
    color: rgb(var(--v-theme-on-surface));
    font-weight: 500;
}
</style>