<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter, type Router } from "vue-router";
import { apiGet } from "@/lib/api";
import { useSessionStore } from "@/stores/session";
import TimelineBadge from "@/components/TimelineBadge.vue";

interface AssignmentSummary {
  id: string;
  cycle_id: string;
  evaluator_user_id: string;
  reviewer_user_id: string | null;
  state: string;
  submitted_at: string | null;
  late_flag: boolean;
  returned_reason: string | null;
  archived_at: string | null;
}

interface CycleSummary {
  id: string;
  name: string;
  starts_on: string;
  ends_on: string;
  deadline_at: string;
  effective_deadline_at: string;
  timezone: string;
  makeup_enabled: boolean;
  makeup_business_days: number;
  template_version_id: string;
}

const session = useSessionStore();
const cycles = ref<CycleSummary[]>([]);
const selectedCycleId = ref<string>("");
const participants = ref<AssignmentSummary[]>([]);
const mine = ref<AssignmentSummary[]>([]);
const loadingCycles = ref(true);
const loadingParticipants = ref(false);
const participantError = ref<string | null>(null);

let router: Router | undefined;
try {
  router = useRouter();
} catch {
  router = undefined;
}

const selectedCycle = computed(() =>
  cycles.value.find((c) => c.id === selectedCycleId.value),
);
const canReview = computed(() => session.hasPermission("cycle", "review"));

async function loadCycles() {
  loadingCycles.value = true;
  const r = await apiGet<{ items: CycleSummary[] }>("/api/cycles");
  loadingCycles.value = false;
  if (r.ok) {
    cycles.value = r.data.items;
    if (cycles.value.length && !selectedCycleId.value) {
      selectedCycleId.value = cycles.value[0].id;
    }
  }
}

async function loadMine() {
  const r = await apiGet<AssignmentSummary[]>("/api/assignments/mine/active");
  if (r.ok) mine.value = r.data;
}

async function loadParticipants() {
  if (!selectedCycleId.value) return;
  loadingParticipants.value = true;
  participantError.value = null;
  const r = await apiGet<{ items: AssignmentSummary[] }>(
    `/api/cycles/${selectedCycleId.value}/assignments`,
  );
  loadingParticipants.value = false;
  if (!r.ok) {
    participantError.value = r.message;
    return;
  }
  participants.value = r.data.items;
}

watch(selectedCycleId, loadParticipants);

function openAssignment(id: string) {
  router?.push({ name: "assignment-form", params: { id } });
}

onMounted(async () => {
  await Promise.all([loadCycles(), loadMine()]);
  if (selectedCycleId.value) await loadParticipants();
});
</script>

<template>
  <section class="cycles-view">
    <h2>Evaluation cycles</h2>
    <p v-if="loadingCycles">Loading…</p>
    <div v-else-if="!cycles.length" class="empty">No cycles you can participate in.</div>
    <div v-else class="cycle-select">
      <label>
        Cycle
        <select v-model="selectedCycleId" data-testid="cycle-select">
          <option v-for="c in cycles" :key="c.id" :value="c.id">
            {{ c.name }} · {{ c.starts_on }} → {{ c.ends_on }}
          </option>
        </select>
      </label>
      <p v-if="selectedCycle" class="meta">
        Deadline: {{ selectedCycle.deadline_at }}
        <span v-if="selectedCycle.effective_deadline_at !== selectedCycle.deadline_at">
          (effective {{ selectedCycle.effective_deadline_at }})
        </span>
      </p>
    </div>

    <h3>My evaluations</h3>
    <table v-if="mine.length" class="table" data-testid="mine-table">
      <thead>
        <tr><th>State</th><th>Submitted</th><th>Reason</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="a in mine" :key="a.id" :data-testid="`row-${a.id}`">
          <td><TimelineBadge :state="a.state" /></td>
          <td>{{ a.submitted_at ?? "—" }}</td>
          <td>{{ a.returned_reason ?? "—" }}</td>
          <td>
            <button
              class="open"
              :data-testid="`open-${a.id}`"
              @click="openAssignment(a.id)"
            >Open</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else class="empty">No active assignments.</p>

    <h3 v-if="selectedCycleId">Cycle participants</h3>
    <p v-if="loadingParticipants">Loading…</p>
    <p v-else-if="participantError" class="error" data-testid="participants-error">
      {{ participantError }}
    </p>
    <table
      v-else-if="selectedCycleId && participants.length"
      class="table"
      data-testid="participants-table"
    >
      <thead>
        <tr><th>Evaluator</th><th>Reviewer</th><th>State</th><th>Submitted</th><th></th></tr>
      </thead>
      <tbody>
        <tr v-for="a in participants" :key="a.id">
          <td>{{ a.evaluator_user_id }}</td>
          <td>{{ a.reviewer_user_id ?? "—" }}</td>
          <td><TimelineBadge :state="a.state" /></td>
          <td>{{ a.submitted_at ?? "—" }}</td>
          <td>
            <button
              v-if="canReview || a.evaluator_user_id === session.user?.userId || a.reviewer_user_id === session.user?.userId"
              class="open"
              :data-testid="`review-${a.id}`"
              @click="openAssignment(a.id)"
            >Open</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else-if="selectedCycleId" class="empty">No participants visible to you.</p>
  </section>
</template>

<style scoped>
.cycles-view { max-width: 960px; }
.cycle-select { margin-bottom: 16px; }
.cycle-select label { display: flex; flex-direction: column; font-size: 12px; color: #57606a; }
.cycle-select select { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 14px; min-width: 320px; }
.meta { color: #57606a; font-size: 12px; margin-top: 6px; }
.empty { color: #57606a; font-size: 13px; padding: 8px 0; }
.error { color: #cf222e; background: #ffebe9; border: 1px solid #cf222e; padding: 8px; border-radius: 4px; }
.table { width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 20px; }
.table th, .table td { padding: 8px 12px; border-bottom: 1px solid #d0d7de; text-align: left; }
.open { padding: 4px 10px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; font-size: 12px; }
</style>
