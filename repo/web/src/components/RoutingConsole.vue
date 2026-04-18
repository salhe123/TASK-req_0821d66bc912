<script setup lang="ts">
import { ref, watch } from "vue";
import { apiPost } from "@/lib/api";

interface Experiment {
  id: string;
  name: string;
  description: string;
  weight_a: number;
  weight_b: number;
  ingest_enabled: boolean;
  apply_enabled: boolean;
  model_a_id: string;
  model_b_id: string | null;
}

const props = defineProps<{ experiment: Experiment; canEdit: boolean }>();
const emit = defineEmits<{ (e: "updated", exp: Experiment): void }>();

const weightA = ref(props.experiment.weight_a);
const ingest = ref(props.experiment.ingest_enabled);
const apply = ref(props.experiment.apply_enabled);
const rollbackReason = ref("");
const confirmingRollback = ref(false);

watch(
  () => props.experiment,
  (e) => {
    weightA.value = e.weight_a;
    ingest.value = e.ingest_enabled;
    apply.value = e.apply_enabled;
  },
);

async function saveWeights() {
  const r = await apiPost<Experiment>(
    `/api/experiments/${props.experiment.id}/routing`,
    { weight_a: weightA.value },
  );
  if (r.ok) emit("updated", r.data);
}

async function saveToggles() {
  const r = await apiPost<Experiment>(
    `/api/experiments/${props.experiment.id}/toggle`,
    { ingest_enabled: ingest.value, apply_enabled: apply.value },
  );
  if (r.ok) emit("updated", r.data);
}

async function doRollback() {
  const r = await apiPost<Experiment>(
    `/api/experiments/${props.experiment.id}/rollback`,
    { trigger: "manual", reason: rollbackReason.value },
  );
  if (r.ok) {
    emit("updated", r.data);
    confirmingRollback.value = false;
    rollbackReason.value = "";
  }
}
</script>

<template>
  <section class="routing" data-testid="routing-console">
    <h3>{{ experiment.name }}</h3>
    <div class="weights">
      <label>
        weight A: <output>{{ weightA }}</output>
        <input
          type="range"
          min="0"
          max="100"
          v-model.number="weightA"
          :disabled="!canEdit"
          data-testid="weight-a-slider"
          @change="saveWeights"
        />
      </label>
      <p>weight B: {{ 100 - weightA }}</p>
    </div>

    <div class="toggles">
      <label>
        <input
          type="checkbox"
          v-model="ingest"
          :disabled="!canEdit"
          data-testid="toggle-ingest"
          @change="saveToggles"
        />
        ingestEnabled
      </label>
      <label>
        <input
          type="checkbox"
          v-model="apply"
          :disabled="!canEdit"
          data-testid="toggle-apply"
          @change="saveToggles"
        />
        applyEnabled
      </label>
    </div>

    <button
      type="button"
      :disabled="!canEdit"
      @click="confirmingRollback = true"
      data-testid="open-rollback"
    >
      Roll back to champion
    </button>

    <div v-if="confirmingRollback" class="confirm" role="dialog" data-testid="rollback-confirm">
      <p>Flip to (100, 0) and record a rollback event?</p>
      <textarea v-model="rollbackReason" placeholder="Reason…" data-testid="rollback-reason" />
      <div>
        <button @click="confirmingRollback = false">Cancel</button>
        <button @click="doRollback" data-testid="rollback-submit">Confirm</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.routing { border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; margin-bottom: 12px; }
.routing h3 { margin: 0 0 8px; font-size: 15px; }
.weights input { width: 100%; }
.toggles { display: flex; gap: 16px; margin: 12px 0; font-size: 13px; }
.confirm { margin-top: 12px; padding: 12px; background: #ffebe9; border: 1px solid #cf222e; border-radius: 6px; }
.confirm textarea { width: 100%; min-height: 60px; }
.confirm div { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
.confirm button:last-child { background: #cf222e; color: #fff; border-color: #cf222e; }
button { padding: 6px 10px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; font-size: 13px; }
</style>
