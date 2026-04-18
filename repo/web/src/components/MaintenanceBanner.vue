<script setup lang="ts">
const props = defineProps<{ reason: string }>();
</script>

<template>
  <div class="maint" role="alert" data-testid="maintenance-banner">
    <strong>System maintenance:</strong> {{ reason || "restore in progress — non-admin actions are paused" }}
  </div>
</template>

<style scoped>
.maint {
  background: #fff8c5;
  border-bottom: 1px solid #d4a72c;
  padding: 8px 16px;
  font-size: 13px;
}
</style>
