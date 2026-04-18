<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet } from "@/lib/api";

interface DigestItem {
  assignment_id: string;
  cycle_id: string;
  cycle_name: string;
  state: string;
  deadline_at: string;
  effective_deadline_at: string;
  late_eligible: boolean;
}

interface DigestPayload {
  show: boolean;
  as_of_local: string;
  items: DigestItem[];
}

const payload = ref<DigestPayload | null>(null);
const dismissed = ref(false);

async function load() {
  const r = await apiGet<DigestPayload>("/api/cycles/digest");
  if (r.ok) payload.value = r.data;
}

function dismiss() {
  dismissed.value = true;
}

onMounted(load);
</script>

<template>
  <section
    v-if="payload && payload.show && !dismissed"
    class="digest"
    role="status"
    data-testid="digest-banner"
  >
    <header>
      <h3>Your day — {{ new Date(payload.as_of_local).toLocaleString() }}</h3>
      <button type="button" @click="dismiss" data-testid="digest-dismiss">Dismiss</button>
    </header>
    <ul v-if="payload.items.length">
      <li v-for="it in payload.items" :key="it.assignment_id">
        <strong>{{ it.cycle_name }}</strong> — {{ it.state }} · due {{ new Date(it.deadline_at).toLocaleDateString() }}
        <span v-if="it.late_eligible" class="late">late eligible</span>
      </li>
    </ul>
    <p v-else class="digest__empty">No active assignments.</p>
  </section>
</template>

<style scoped>
.digest {
  background: #fff8c5;
  border: 1px solid #d4a72c;
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 16px;
}
.digest header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.digest h3 { margin: 0; font-size: 14px; }
.digest button {
  background: transparent;
  border: 1px solid #d4a72c;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
}
.digest ul { margin: 8px 0 0; padding-left: 20px; font-size: 13px; }
.digest .late { margin-left: 8px; color: #cf222e; font-size: 11px; }
.digest__empty { margin: 4px 0 0; font-size: 13px; opacity: 0.7; }
</style>
