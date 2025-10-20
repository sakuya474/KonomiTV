import { defineStore } from 'pinia';

import BDLibrary, { IBDLibraryItem } from '@/services/BDLibrary';

export const useBDLibraryStore = defineStore('bdLibrary', {
    state: () => ({
        bdList: [] as IBDLibraryItem[],
        total: 0 as number,
        bdItem: null as IBDLibraryItem | null,
    }),
    actions: {
        async fetchBDLibraryList(page: number = 1) {
            const result = await BDLibrary.fetchBDLibraryList(page);
            this.bdList = result.items;
            this.total = result.total;
        },
        async fetchBDLibraryItem(id: number) {
            this.bdItem = await BDLibrary.fetchBDLibraryItem(id);
        },
    },
    getters: {
        groupedByDirectory(state) {
            const groups: Record<string, IBDLibraryItem[]> = {};
            for (const item of state.bdList) {
                const parts = item.path.replace(/\\/g, '/').split('/');
                const dir = parts.length > 1 ? parts[parts.length - 2] : '';
                if (!groups[dir]) groups[dir] = [];
                groups[dir].push(item);
            }
            return groups;
        },
    },
});

