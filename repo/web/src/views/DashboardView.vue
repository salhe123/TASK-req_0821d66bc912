<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet } from "@/lib/api";

const status = ref<string>("checking...");
const dbCheck = ref<string>("");

onMounted(async () => {
  const result = await apiGet<{ status: string; checks?: Record<string, string> }>(
    "/api/health/ready",
  );
  if (result.ok) {
    status.value = result.data.status;
    dbCheck.value = result.data.checks?.db ?? "";
  } else {
    status.value = `error: ${result.error}`;
  }
});
</script>

<template>
  <section>
    <h2>Dashboard</h2>
    <p>Readiness: <strong data-testid="ready-status">{{ status }}</strong></p>
    <p v-if="dbCheck">Database: {{ dbCheck }}</p>
  </section>
</template>
