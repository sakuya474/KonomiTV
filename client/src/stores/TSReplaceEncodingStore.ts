import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

import Message from '@/message';
import TSReplace, { EncodingTaskStatus } from '@/services/TSReplace';

export interface IActiveEncodingTask {
    taskId: string;
    programTitle: string;
    codec: 'h264' | 'hevc';
    encoderType: 'software' | 'hardware';
    status: EncodingTaskStatus;
    progress: number;
    startedAt?: Date;
    completedAt?: Date;
    errorMessage?: string;
}

const useTSReplaceEncodingStore = defineStore('tsreplace-encoding', () => {
    const activeTasks = ref<Map<string, IActiveEncodingTask>>(new Map());
    const webSocket = ref<WebSocket | null>(null);
    const isWebSocketConnected = ref(false);

    const activeTaskCount = computed(() => {
        return Array.from(activeTasks.value.values()).filter(task =>
            ['queued', 'processing'].includes(task.status)
        ).length;
    });

    const latestActiveTask = computed(() => {
        const tasks = Array.from(activeTasks.value.values())
            .filter(task => ['queued', 'processing'].includes(task.status))
            .sort((a, b) => {
                if (a.startedAt && b.startedAt) {
                    return b.startedAt.getTime() - a.startedAt.getTime();
                }
                return 0;
            });
        return tasks[0] || null;
    });

    const initializeWebSocket = () => {
        if (webSocket.value && webSocket.value.readyState === WebSocket.OPEN) {
            return;
        }

        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/api/tsreplace/progress`;
        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
            console.log('WebSocket connection for progress updates established.');
            isWebSocketConnected.value = true;
            // 再接続時にタスク一覧を再取得して同期
            refreshEncodingQueue();
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);

                // エンコード完了通知の処理
                if (data.type === 'encoding_complete') {
                    console.log('Encoding completed:', data);

                    // 完了タスクの情報を更新または新規作成
                    const existingTask = activeTasks.value.get(data.task_id);
                    if (existingTask) {
                        existingTask.status = 'completed';
                        existingTask.progress = 100;
                        existingTask.completedAt = new Date();
                        activeTasks.value.set(data.task_id, existingTask);
                    } else {
                        // タスクが存在しない場合は新規作成（ページ再読み込みなどでタスクが消えた場合）
                        // codecは大文字で送られてくる可能性があるので、小文字に変換
                        const codec = data.codec?.toLowerCase() === 'hevc' || data.codec?.toUpperCase() === 'HEVC' ? 'hevc' : 'h264';
                        // encoder_typeは日本語で送られてくる可能性があるので、判定
                        const encoderType = data.encoder_type?.includes('ハードウェア') || data.encoder_type === 'hardware' ? 'hardware' : 'software';
                        const task: IActiveEncodingTask = {
                            taskId: data.task_id,
                            programTitle: data.video_title || 'Unknown Video',
                            codec: codec,
                            encoderType: encoderType,
                            status: 'completed',
                            progress: 100,
                            completedAt: new Date(),
                        };
                        activeTasks.value.set(data.task_id, task);
                        console.log(`Created new task from encoding_complete notification: ${data.task_id}`);
                    }
                }

                // エンコード失敗通知の処理
                if (data.type === 'encoding_failed') {
                    console.log('Encoding failed:', data);

                    // 失敗タスクの情報を更新または新規作成
                    const existingTask = activeTasks.value.get(data.task_id);
                    if (existingTask) {
                        existingTask.status = 'failed';
                        existingTask.errorMessage = data.error_message;
                        existingTask.completedAt = new Date();
                        activeTasks.value.set(data.task_id, existingTask);
                    } else {
                        // タスクが存在しない場合は新規作成（ページ再読み込みなどでタスクが消えた場合）
                        // codecは大文字で送られてくる可能性があるので、小文字に変換
                        const codec = data.codec?.toLowerCase() === 'hevc' || data.codec?.toUpperCase() === 'HEVC' ? 'hevc' : 'h264';
                        // encoder_typeは日本語で送られてくる可能性があるので、判定
                        const encoderType = data.encoder_type?.includes('ハードウェア') || data.encoder_type === 'hardware' ? 'hardware' : 'software';
                        const task: IActiveEncodingTask = {
                            taskId: data.task_id,
                            programTitle: data.video_title || 'Unknown Video',
                            codec: codec,
                            encoderType: encoderType,
                            status: 'failed',
                            progress: 0,
                            errorMessage: data.error_message,
                            completedAt: new Date(),
                        };
                        activeTasks.value.set(data.task_id, task);
                        console.log(`Created new task from encoding_failed notification: ${data.task_id}`);
                    }
                }

                // エンコードキャンセル通知の処理
                if (data.type === 'encoding_cancelled') {
                    console.log('Encoding cancelled:', data);

                    // キャンセルタスクの情報を更新または新規作成
                    const existingTask = activeTasks.value.get(data.task_id);
                    if (existingTask) {
                        existingTask.status = 'cancelled';
                        existingTask.completedAt = new Date();
                        activeTasks.value.set(data.task_id, existingTask);
                    } else {
                        // タスクが存在しない場合は新規作成（ページ再読み込みなどでタスクが消えた場合）
                        // codecは大文字で送られてくる可能性があるので、小文字に変換
                        const codec = data.codec?.toLowerCase() === 'hevc' || data.codec?.toUpperCase() === 'HEVC' ? 'hevc' : 'h264';
                        // encoder_typeは日本語で送られてくる可能性があるので、判定
                        const encoderType = data.encoder_type?.includes('ハードウェア') || data.encoder_type === 'hardware' ? 'hardware' : 'software';
                        const task: IActiveEncodingTask = {
                            taskId: data.task_id,
                            programTitle: data.video_title || 'Unknown Video',
                            codec: codec,
                            encoderType: encoderType,
                            status: 'cancelled',
                            progress: 0,
                            completedAt: new Date(),
                        };
                        activeTasks.value.set(data.task_id, task);
                        console.log(`Created new task from encoding_cancelled notification: ${data.task_id}`);
                    }
                }

                // 進捗更新の処理
                if (data.type === 'progress_update' && Array.isArray(data.tasks)) {
                    const seenTaskIds = new Set<string>(); // 重複チェック用
                    for (const taskUpdate of data.tasks) {
                        // 重複チェック: 同じメッセージ内での重複を防ぐ
                        if (seenTaskIds.has(taskUpdate.task_id)) {
                            console.warn(`Duplicate task_id in WebSocket progress_update: ${taskUpdate.task_id}, skipping`);
                            continue;
                        }
                        seenTaskIds.add(taskUpdate.task_id);

                        let existingTask = activeTasks.value.get(taskUpdate.task_id);
                        if (!existingTask) {
                            // 新しいタスクの場合は作成
                            existingTask = {
                                taskId: taskUpdate.task_id,
                                programTitle: taskUpdate.video_title || 'Unknown Video',
                                codec: taskUpdate.codec,
                                encoderType: taskUpdate.encoder_type,
                                status: taskUpdate.status,
                                progress: taskUpdate.progress,
                                errorMessage: taskUpdate.error_message,
                            };
                            activeTasks.value.set(taskUpdate.task_id, existingTask);
                        } else {
                            // 既存のタスクを更新（キャンセルされたタスクは更新しない）
                            if (existingTask.status === 'cancelled' && taskUpdate.status !== 'cancelled') {
                                console.log(`Skipping update for cancelled task: ${taskUpdate.task_id}`);
                                continue;
                            }
                            existingTask.status = taskUpdate.status;
                            existingTask.progress = taskUpdate.progress;
                            if (taskUpdate.error_message) {
                                existingTask.errorMessage = taskUpdate.error_message;
                            }
                        }

                        // タイムスタンプの更新
                        if (taskUpdate.started_at && !existingTask.startedAt) {
                            existingTask.startedAt = new Date(taskUpdate.started_at);
                        }
                        if (taskUpdate.completed_at && !existingTask.completedAt) {
                            existingTask.completedAt = new Date(taskUpdate.completed_at);
                        }
                    }
                }
            } catch (error) {
                console.error('Failed to parse WebSocket message:', error);
            }
        };

        ws.onclose = () => {
            console.log('WebSocket connection for progress updates closed. Reconnecting in 5 seconds...');
            isWebSocketConnected.value = false;
            setTimeout(initializeWebSocket, 5000);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            isWebSocketConnected.value = false;
            ws.close();
        };

        webSocket.value = ws;
    };

    const addTask = (
        taskId: string,
        programTitle: string,
        codec: 'h264' | 'hevc',
        encoderType: 'software' | 'hardware'
    ) => {
        const task: IActiveEncodingTask = {
            taskId,
            programTitle,
            codec,
            encoderType,
            status: 'queued',
            progress: 0,
        };
        activeTasks.value.set(taskId, task);
    };

    const updateTaskStatus = (
        taskId: string,
        status: EncodingTaskStatus,
        progress?: number,
        errorMessage?: string
    ) => {
        const task = activeTasks.value.get(taskId);
        if (task) {
            task.status = status;
            if (progress !== undefined) {
                task.progress = progress;
            }
            if (errorMessage !== undefined) {
                task.errorMessage = errorMessage;
            }
            if (status === 'processing' && !task.startedAt) {
                task.startedAt = new Date();
            }
            if (['completed', 'failed', 'cancelled'].includes(status)) {
                task.completedAt = new Date();
            }
            activeTasks.value.set(taskId, task);
        }
    };

    const removeTask = async (taskId: string) => {
        // サーバー側のAPIを呼び出してDBから削除
        const TSReplace = (await import('@/services/TSReplace')).default;
        const success = await TSReplace.deleteEncodingTask(taskId);
        if (success) {
            activeTasks.value.delete(taskId);
            console.log(`Task ${taskId} removed from store and database`);
        } else {
            console.error(`Failed to delete task ${taskId} from database`);
        }
    };

    const cleanupCompletedTasks = () => {
        const now = Date.now();
        const CLEANUP_DELAY = 24 * 60 * 60 * 1000; // 24時間（完了タスクは長期間保持）
        for (const [taskId, task] of activeTasks.value.entries()) {
            if (['completed', 'failed', 'cancelled'].includes(task.status) &&
                task.completedAt &&
                (now - task.completedAt.getTime()) > CLEANUP_DELAY) {
                // 完了から24時間以上経過したタスクのみ削除
                activeTasks.value.delete(taskId);
            }
        }

    };

    const getTask = (taskId: string): IActiveEncodingTask | undefined => {
        return activeTasks.value.get(taskId);
    };

    const getAllTasks = (): IActiveEncodingTask[] => {
        return Array.from(activeTasks.value.values());
    };

    const refreshEncodingQueue = async () => {
        try {
            const queueResponse = await TSReplace.getEncodingQueue();
            if (queueResponse && queueResponse.success) {
                const allTasks = [
                    ...queueResponse.processing_tasks,
                    ...queueResponse.queued_tasks,
                    ...queueResponse.completed_tasks,
                    ...queueResponse.failed_tasks,
                ];

                // APIから取得したタスクIDのセットを作成（削除対象の判定に使用）
                const apiTaskIds = new Set<string>();
                const seenTaskIds = new Set<string>(); // 重複チェック用

                for (const taskInfo of allTasks) {
                    // 重複チェック: 既に処理したタスクIDはスキップ
                    if (seenTaskIds.has(taskInfo.task_id)) {
                        console.warn(`Duplicate task_id detected in API response: ${taskInfo.task_id}, skipping`);
                        continue;
                    }

                    apiTaskIds.add(taskInfo.task_id);

                    // 既存のタスクがある場合は更新、ない場合は新規作成
                    const existingTask = activeTasks.value.get(taskInfo.task_id);
                    if (existingTask) {
                        // 既存タスクを更新（WebSocketで追加されたタスクも保持）
                        // キャンセルされたタスクは、APIから'cancelled'ステータスが来た場合のみ更新
                        if (existingTask.status === 'cancelled' && taskInfo.status !== 'cancelled') {
                            console.log(`Skipping update for cancelled task from API: ${taskInfo.task_id}`);
                            seenTaskIds.add(taskInfo.task_id);
                            continue;
                        }
                        existingTask.programTitle = taskInfo.video_title;
                        existingTask.codec = taskInfo.codec;
                        existingTask.encoderType = taskInfo.encoder_type;
                        existingTask.status = taskInfo.status;
                        existingTask.progress = taskInfo.progress;
                        existingTask.startedAt = taskInfo.started_at ? new Date(taskInfo.started_at) : existingTask.startedAt;
                        existingTask.completedAt = taskInfo.completed_at ? new Date(taskInfo.completed_at) : existingTask.completedAt;
                        existingTask.errorMessage = taskInfo.error_message;
                    } else {
                        // 新規タスクを作成
                        const task: IActiveEncodingTask = {
                            taskId: taskInfo.task_id,
                            programTitle: taskInfo.video_title,
                            codec: taskInfo.codec,
                            encoderType: taskInfo.encoder_type,
                            status: taskInfo.status,
                            progress: taskInfo.progress,
                            startedAt: taskInfo.started_at ? new Date(taskInfo.started_at) : undefined,
                            completedAt: taskInfo.completed_at ? new Date(taskInfo.completed_at) : undefined,
                            errorMessage: taskInfo.error_message,
                        };
                        activeTasks.value.set(taskInfo.task_id, task);
                    }
                    seenTaskIds.add(taskInfo.task_id);
                }

                // APIに存在しないタスクの処理
                // 完了・失敗・キャンセル済みのタスクはcleanupCompletedTasksで削除するため、ここでは削除しない
                // 実行中・待機中のタスクで、APIに存在しない場合は、WebSocketで追加された可能性があるため保持
                for (const [taskId, task] of activeTasks.value.entries()) {
                    if (!apiTaskIds.has(taskId)) {
                        // 実行中・待機中のタスクは削除しない（WebSocketで追加された可能性がある）
                        if (task.status === 'processing' || task.status === 'queued') {
                            console.log(`Keeping task ${taskId} that is not in API response (status: ${task.status})`);
                            continue;
                        }
                        // 完了・失敗・キャンセル済みのタスクはcleanupCompletedTasksで削除するため、ここでは削除しない
                        // APIの取得タイミングによって一時的に存在しない場合があるため、誤って削除しないようにする
                        console.log(`Keeping task ${taskId} that is not in API response (status: ${task.status}, will be cleaned up by cleanupCompletedTasks if needed)`);
                    }
                }
            }
        } catch (error) {
            console.error('Failed to refresh encoding queue:', error);
        }
    };

    const startPeriodicCleanup = () => {
        setInterval(cleanupCompletedTasks, 60 * 1000); // 1分ごと
    };

    const startPeriodicRefresh = () => {
        // 30秒ごとにAPIからタスク一覧を取得して同期
        setInterval(async () => {
            await refreshEncodingQueue();
        }, 30 * 1000); // 30秒ごと
    };

    return {
        activeTasks: computed(() => activeTasks.value),
        isWebSocketConnected: computed(() => isWebSocketConnected.value),

        activeTaskCount,
        latestActiveTask,

        initializeWebSocket,
        addTask,
        updateTaskStatus,
        removeTask,
        getTask,
        getAllTasks,
        refreshEncodingQueue,
        startPeriodicCleanup,
        startPeriodicRefresh,
    };
});

export default useTSReplaceEncodingStore;
