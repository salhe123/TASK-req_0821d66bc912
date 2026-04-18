<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet, apiPost } from "@/lib/api";
import { useSessionStore } from "@/stores/session";
import FeedbackControl, { type FeedbackKind } from "@/components/FeedbackControl.vue";

interface Experiment {
  id: string;
  name: string;
  ingest_enabled: boolean;
  apply_enabled: boolean;
}

interface PredictResponse {
  subject_key: string;
  experiment_id: string;
  arm: "A" | "B";
  model_version_id: string;
  score: number;
  latency_ms: number;
}

interface Block {
  target_id: string;
  created_at: string;
}

interface BlocksResponse {
  subject_key: string;
  items: Block[];
}

interface Recommendation extends PredictResponse {
  target_id: string;
  state: FeedbackKind | null;
}

const session = useSessionStore();

const experiments = ref<Experiment[]>([]);
const selectedExperiment = ref<string>("");
const targetId = ref<string>("");
const recommendations = ref<Recommendation[]>([]);
const blocks = ref<Block[]>([]);
const loadingBlocks = ref(true);
const error = ref<string | null>(null);
const feedbackError = ref<string | null>(null);
const predicting = ref(false);

async function loadExperiments() {
  const r = await apiGet<{ items: Experiment[] }>("/api/experiments");
  if (r.ok) {
    experiments.value = r.data.items;
    if (!selectedExperiment.value && experiments.value.length) {
      selectedExperiment.value = experiments.value[0].id;
    }
  }
}

async function loadBlocks() {
  if (!session.user) return;
  loadingBlocks.value = true;
  error.value = null;
  const r = await apiGet<BlocksResponse>(`/api/feedback/blocks/${session.user.userId}`);
  loadingBlocks.value = false;
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  blocks.value = r.data.items;
}

async function predict() {
  if (!selectedExperiment.value || !targetId.value) return;
  feedbackError.value = null;
  predicting.value = true;
  const r = await apiPost<PredictResponse>("/api/inference/predict", {
    experiment_id: selectedExperiment.value,
    subject_key: session.user?.userId ?? "",
    features: { a: 0.5 },
  });
  predicting.value = false;
  if (!r.ok) {
    feedbackError.value = r.message;
    return;
  }
  recommendations.value.unshift({
    ...r.data,
    target_id: targetId.value,
    state: null,
  });
  targetId.value = "";
}

function onFeedbackChange(
  rec: Recommendation,
  payload: { kind: FeedbackKind },
) {
  rec.state = payload.kind;
  if (payload.kind === "BLOCK") {
    // reflect in the blocks list without a round-trip
    blocks.value = [
      { target_id: rec.target_id, created_at: new Date().toISOString() },
      ...blocks.value,
    ];
  }
}

function onFeedbackError(payload: { kind: FeedbackKind; message: string }) {
  feedbackError.value = `${payload.kind}: ${payload.message}`;
}

onMounted(async () => {
  await Promise.all([loadExperiments(), loadBlocks()]);
});
</script>

<template>
  <section>
    <h2>Feedback</h2>
    <p class="intro">
      Close the loop: run inference on a target, then Like / Not interested /
      Block the recommendation. Block decisions persist across experiments and
      appear in the list below.
    </p>

    <div class="predict-panel" data-testid="predict-panel">
      <label>
        Experiment
        <select v-model="selectedExperiment" data-testid="experiment-select">
          <option v-for="e in experiments" :key="e.id" :value="e.id">
            {{ e.name }}
          </option>
        </select>
      </label>
      <label>
        Target id
        <input
          v-model="targetId"
          type="text"
          placeholder="e.g. item-42"
          data-testid="target-id"
        />
      </label>
      <button
        type="button"
        :disabled="!selectedExperiment || !targetId || predicting"
        @click="predict"
        data-testid="predict-btn"
      >
        {{ predicting ? "Predicting…" : "Predict" }}
      </button>
    </div>

    <p v-if="feedbackError" class="error" data-testid="feedback-error">
      {{ feedbackError }}
    </p>

    <div v-if="recommendations.length" class="recos" data-testid="recommendations">
      <h3>Recent recommendations</h3>
      <ul>
        <li v-for="(rec, i) in recommendations" :key="i">
          <div class="row">
            <span class="target">{{ rec.target_id }}</span>
            <span class="meta">
              arm {{ rec.arm }} · score {{ rec.score.toFixed(3) }}
            </span>
          </div>
          <FeedbackControl
            :subject-key="session.user?.userId ?? ''"
            :target-id="rec.target_id"
            :experiment-id="rec.experiment_id"
            :model-version-id="rec.model_version_id"
            :arm="rec.arm"
            :initial-state="rec.state"
            @change="(p) => onFeedbackChange(rec, p)"
            @error="onFeedbackError"
          />
        </li>
      </ul>
    </div>

    <h3>Blocked items</h3>
    <p v-if="loadingBlocks">Loading…</p>
    <p v-else-if="error" class="error" data-testid="blocks-error">{{ error }}</p>
    <table v-else-if="blocks.length" class="blocks" data-testid="blocks-table">
      <thead>
        <tr><th>Target</th><th>Blocked at</th></tr>
      </thead>
      <tbody>
        <tr v-for="b in blocks" :key="b.target_id">
          <td>{{ b.target_id }}</td>
          <td>{{ b.created_at }}</td>
        </tr>
      </tbody>
    </table>
    <p v-else data-testid="blocks-empty">You have no blocked items.</p>
  </section>
</template>

<style scoped>
.intro { color: #57606a; font-size: 13px; margin-bottom: 16px; }
.predict-panel { display: flex; gap: 12px; align-items: flex-end; margin-bottom: 16px; flex-wrap: wrap; }
.predict-panel label { display: flex; flex-direction: column; font-size: 12px; color: #57606a; }
.predict-panel select, .predict-panel input { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 14px; }
.predict-panel button { padding: 6px 14px; border: 1px solid #d0d7de; border-radius: 4px; background: #0969da; color: #fff; cursor: pointer; }
.predict-panel button:disabled { opacity: 0.5; cursor: not-allowed; }
.recos { margin-bottom: 16px; }
.recos ul { list-style: none; padding: 0; }
.recos li { border: 1px solid #d0d7de; border-radius: 6px; padding: 10px 12px; margin-bottom: 8px; display: flex; justify-content: space-between; align-items: center; gap: 12px; }
.row { display: flex; flex-direction: column; }
.target { font-weight: 600; }
.meta { color: #57606a; font-size: 12px; }
.blocks { width: 100%; border-collapse: collapse; font-size: 13px; }
.blocks th, .blocks td { padding: 8px 12px; border-bottom: 1px solid #d0d7de; text-align: left; }
.error { color: #cf222e; background: #ffebe9; border: 1px solid #cf222e; padding: 8px; border-radius: 4px; }
</style>
