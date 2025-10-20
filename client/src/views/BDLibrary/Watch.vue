<template>
    <BDLibraryWatch :playback_mode="'Video'" />
</template>
<script lang="ts">
import { defineComponent } from 'vue';

import BDLibraryWatch from '@/components/Watch/BDLibraryWatch.vue';

export default defineComponent({
    name: 'BDLibrary-Watch',
    components: {
        BDLibraryWatch,
    },
});
</script>