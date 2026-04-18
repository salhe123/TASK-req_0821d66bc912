<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { apiGet, apiPost } from "@/lib/api";
import { useSessionStore } from "@/stores/session";
import RoutingConsole from "@/components/RoutingConsole.vue";

interface ModelVersion {
  id: string;
  version_no: number;
  status: string;
  feature_schema_hash: string;
}

interface Model {
  id: string;
  name: string;
  description: string;
  live_schema_hash: string | null;
  versions: ModelVersion[];
}

interface Experiment {
  id: string;
  name: string;
  weight_a: number;
  weight_b: number;
  ingest_enabled: boolean;
  apply_enabled: boolean;
  model_a_id: string;
  model_b_id: string | null;
  description: string;
}

interface ModelRun {
  id: string;
  model_version_id: string;
  kind: string;
  status: string;
  metrics: Record<string, unknown>;
  started_at: string;
  completed_at: string | null;
}

const session = useSessionStore();
const models = ref<Model[]>([]);
const experiments = ref<Experiment[]>([]);
const promoteError = ref<string | null>(null);
const runsByVersion = ref<Record<string, ModelRun[]>>({});
const runError = ref<string | null>(null);

const canPromote = computed(() => session.hasPermission("model", "promote"));
const canRoute = computed(() => session.hasPermission("model", "route"));
const canRun = computed(() => session.hasPermission("model", "run"));
const canRegister = computed(() => session.hasPermission("model", "register"));
const canManageExperiment = computed(() => session.hasPermission("experiment", "manage"));

const createModelOpen = ref(false);
const createExperimentOpen = ref(false);
const createError = ref<string | null>(null);
const newModel = reactive({ name: "", description: "", feature_a: "a", feature_b: "b" });
const newExperiment = reactive({ name: "", model_a_version_id: "", weight_a: 100 });

async function refresh() {
  const m = await apiGet<{ items: Model[] }>("/api/models");
  if (m.ok) models.value = m.data.items;
  const e = await apiGet<{ items: Experiment[] }>("/api/experiments");
  if (e.ok) experiments.value = e.data.items;
}

async function loadRuns(modelId: string, versionId: string) {
  const r = await apiGet<{ items: ModelRun[] }>(
    `/api/models/${modelId}/versions/${versionId}/runs`,
  );
  if (r.ok) runsByVersion.value[versionId] = r.data.items;
}

async function startRun(modelId: string, versionId: string, kind: "TRAINING" | "EVALUATION") {
  runError.value = null;
  const start = await apiPost<ModelRun>(
    `/api/models/${modelId}/versions/${versionId}/runs`,
    { kind, dataset_ref: "" },
  );
  if (!start.ok) {
    runError.value = start.message;
    return;
  }
  const done = await apiPost<ModelRun>(
    `/api/models/${modelId}/versions/${versionId}/runs/${start.data.id}/complete`,
    { status: "SUCCEEDED", metrics: {} },
  );
  if (!done.ok) {
    runError.value = done.message;
    return;
  }
  await loadRuns(modelId, versionId);
}

function hasSuccessfulEval(versionId: string): boolean {
  const runs = runsByVersion.value[versionId] || [];
  return runs.some((r) => r.kind === "EVALUATION" && r.status === "SUCCEEDED");
}

async function promote(modelId: string, versionId: string) {
  promoteError.value = null;
  const r = await apiPost<ModelVersion>(
    `/api/models/${modelId}/versions/${versionId}/promote`,
  );
  if (!r.ok) {
    promoteError.value = r.message + (r.error === "feature_schema_mismatch"
      ? ` (hash expected ${r.details.expected_hash})`
      : "");
    return;
  }
  await refresh();
}

function onExperimentUpdated(updated: Experiment) {
  const idx = experiments.value.findIndex((e) => e.id === updated.id);
  if (idx >= 0) experiments.value[idx] = updated;
}

async function createModel() {
  createError.value = null;
  if (!newModel.name) {
    createError.value = "Model name is required.";
    return;
  }
  const m = await apiPost<Model>("/api/models", {
    name: newModel.name,
    description: newModel.description,
  });
  if (!m.ok) {
    createError.value = m.message;
    return;
  }
  const v = await apiPost<ModelVersion>(`/api/models/${m.data.id}/versions`, {
    feature_schema: [
      { name: newModel.feature_a, dtype: "float", transform: "identity", source_query_hash: "q1" },
      { name: newModel.feature_b, dtype: "float", transform: "identity", source_query_hash: "q1" },
    ],
    artifact_uri: "",
    artifact_params: { bias: 0.0, weights: { [newModel.feature_a]: 0.5, [newModel.feature_b]: 0.5 } },
  });
  if (!v.ok) {
    createError.value = v.message;
    return;
  }
  createModelOpen.value = false;
  newModel.name = "";
  newModel.description = "";
  await refresh();
}

async function createExperiment() {
  createError.value = null;
  if (!newExperiment.name || !newExperiment.model_a_version_id) {
    createError.value = "Name and model version are required.";
    return;
  }
  const r = await apiPost<Experiment>("/api/experiments", {
    name: newExperiment.name,
    description: "",
    model_a_version_id: newExperiment.model_a_version_id,
    weight_a: newExperiment.weight_a,
  });
  if (!r.ok) {
    createError.value = r.message;
    return;
  }
  createExperimentOpen.value = false;
  newExperiment.name = "";
  newExperiment.model_a_version_id = "";
  await refresh();
}

const approvedVersions = computed(() => {
  const out: { id: string; label: string }[] = [];
  for (const m of models.value) {
    for (const v of m.versions) {
      if (v.status === "APPROVED") {
        out.push({ id: v.id, label: `${m.name} v${v.version_no}` });
      }
    }
  }
  return out;
});

onMounted(refresh);
</script>

<template>
  <section>
    <div class="header-row">
      <h2>Model registry</h2>
      <button
        v-if="canRegister"
        type="button"
        class="primary"
        @click="createModelOpen = true"
        data-testid="open-create-model"
      >New model</button>
    </div>

    <p v-if="promoteError" class="error" data-testid="promote-error">{{ promoteError }}</p>
    <p v-if="runError" class="error" data-testid="run-error">{{ runError }}</p>

    <div v-if="createModelOpen" class="modal" role="dialog" data-testid="create-model-modal">
      <div class="modal__card">
        <h3>Register a new model</h3>
        <p v-if="createError" class="error">{{ createError }}</p>
        <label>Name<input v-model="newModel.name" type="text" data-testid="new-model-name" /></label>
        <label>Description<input v-model="newModel.description" type="text" /></label>
        <label>Feature A name<input v-model="newModel.feature_a" type="text" /></label>
        <label>Feature B name<input v-model="newModel.feature_b" type="text" /></label>
        <footer>
          <button type="button" @click="createModelOpen = false">Cancel</button>
          <button type="button" class="primary" @click="createModel" data-testid="create-model-submit">
            Create + register v1
          </button>
        </footer>
      </div>
    </div>

    <div v-if="createExperimentOpen" class="modal" role="dialog" data-testid="create-exp-modal">
      <div class="modal__card">
        <h3>Create experiment</h3>
        <p v-if="createError" class="error">{{ createError }}</p>
        <label>Name<input v-model="newExperiment.name" type="text" data-testid="new-exp-name" /></label>
        <label>Model A version
          <select v-model="newExperiment.model_a_version_id" data-testid="new-exp-version">
            <option value="">— select —</option>
            <option v-for="v in approvedVersions" :key="v.id" :value="v.id">{{ v.label }}</option>
          </select>
        </label>
        <label>Weight A
          <input v-model.number="newExperiment.weight_a" type="number" min="0" max="100" />
        </label>
        <footer>
          <button type="button" @click="createExperimentOpen = false">Cancel</button>
          <button type="button" class="primary" @click="createExperiment" data-testid="create-exp-submit">
            Create
          </button>
        </footer>
      </div>
    </div>

    <table class="models" data-testid="models-table">
      <thead>
        <tr>
          <th>Model</th><th>Version</th><th>Status</th><th>Schema hash</th><th></th>
        </tr>
      </thead>
      <tbody>
        <template v-for="m in models" :key="m.id">
          <tr v-for="v in m.versions" :key="v.id">
            <td>{{ m.name }}</td>
            <td>v{{ v.version_no }}</td>
            <td>{{ v.status }}</td>
            <td><code>{{ v.feature_schema_hash.slice(0, 12) }}…</code></td>
            <td>
              <button
                v-if="canRun && v.status === 'DRAFT'"
                @click="startRun(m.id, v.id, 'TRAINING')"
                :data-testid="`train-${v.id}`"
              >Train</button>
              <button
                v-if="canRun && v.status === 'DRAFT'"
                @click="startRun(m.id, v.id, 'EVALUATION')"
                :data-testid="`eval-${v.id}`"
              >Evaluate</button>
              <button
                v-if="canPromote && v.status === 'DRAFT'"
                @click="promote(m.id, v.id)"
                :data-testid="`promote-${v.id}`"
              >Promote</button>
              <ul v-if="runsByVersion[v.id]?.length" class="run-list" :data-testid="`runs-${v.id}`">
                <li v-for="r in runsByVersion[v.id]" :key="r.id">
                  {{ r.kind }} — {{ r.status }}
                </li>
              </ul>
            </td>
          </tr>
          <tr v-if="!m.versions.length">
            <td>{{ m.name }}</td>
            <td colspan="4"><em>no versions</em></td>
          </tr>
        </template>
        <tr v-if="!models.length">
          <td colspan="5" class="empty">No models registered.</td>
        </tr>
      </tbody>
    </table>

    <div class="header-row">
      <h2>Experiments</h2>
      <button
        v-if="canManageExperiment && approvedVersions.length"
        type="button"
        class="primary"
        @click="createExperimentOpen = true"
        data-testid="open-create-experiment"
      >New experiment</button>
    </div>
    <div v-if="!experiments.length" class="empty">No experiments configured.</div>
    <RoutingConsole
      v-for="e in experiments"
      :key="e.id"
      :experiment="e"
      :can-edit="canRoute"
      @updated="onExperimentUpdated"
    />
  </section>
</template>

<style scoped>
.models { width: 100%; border-collapse: collapse; font-size: 13px; margin-bottom: 24px; }
.models th, .models td { padding: 8px 10px; border-bottom: 1px solid #d0d7de; text-align: left; }
.error { color: #cf222e; padding: 8px; background: #ffebe9; border: 1px solid #cf222e; border-radius: 4px; }
.empty { color: #57606a; font-size: 13px; padding: 12px 0; }
button { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; font-size: 12px; margin-right: 4px; }
button:disabled { opacity: 0.5; cursor: not-allowed; }
.run-list { margin: 4px 0 0; padding-left: 16px; font-size: 11px; color: #57606a; }
.header-row { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
.primary { background: #0969da; color: #fff; border-color: #0969da; }
.modal { position: fixed; inset: 0; background: rgba(13, 17, 23, 0.5); display: grid; place-items: center; z-index: 50; }
.modal__card { background: #fff; padding: 24px; border-radius: 8px; width: 420px; }
.modal__card label { display: flex; flex-direction: column; font-size: 12px; color: #57606a; margin-bottom: 8px; }
.modal__card input, .modal__card select { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }
</style>
