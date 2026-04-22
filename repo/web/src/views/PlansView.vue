<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from "vue";
import { apiGet, apiPost } from "@/lib/api";
import { useSessionStore } from "@/stores/session";
import BomDiffView from "@/components/BomDiffView.vue";
import ShareLinkModal from "@/components/ShareLinkModal.vue";

interface VersionSummary {
  id: string;
  plan_id: string;
  version_no: number;
  parent_version_id: string | null;
  note: string;
  created_at: string;
}

interface PlanSummary {
  id: string;
  name: string;
  description: string;
  head_version_id: string;
  head_version_no: number;
  versions: VersionSummary[];
}

interface DiffResponse {
  base_version_id: string | null;
  target_version_id: string;
  entries: unknown[];
}

const session = useSessionStore();
const plans = ref<PlanSummary[]>([]);
const selectedPlanId = ref<string | null>(null);
const selectedVersionId = ref<string | null>(null);
const diff = ref<DiffResponse | null>(null);
const shareOpen = ref(false);
const rollbackOpen = ref(false);
const rollbackNote = ref("");
const copyOpen = ref(false);
const copyNote = ref("");
const copyError = ref<string | null>(null);
const createOpen = ref(false);
const createError = ref<string | null>(null);
const newPlan = reactive({
  name: "",
  description: "",
  note: "initial version",
  line_key: "K1",
  part_number: "",
  quantity: "1",
  unit: "ea",
});
const canManage = computed(() => session.hasPermission("build_plan", "manage"));

const selectedPlan = computed(() => plans.value.find((p) => p.id === selectedPlanId.value) ?? null);

async function refresh() {
  const r = await apiGet<{ items: PlanSummary[] }>("/api/plans");
  if (r.ok) plans.value = r.data.items;
}

async function loadDiff() {
  if (!selectedPlanId.value || !selectedVersionId.value) {
    diff.value = null;
    return;
  }
  const r = await apiGet<DiffResponse>(
    `/api/plans/${selectedPlanId.value}/versions/${selectedVersionId.value}/diff`,
  );
  if (r.ok) diff.value = r.data;
}

async function doCopy() {
  copyError.value = null;
  if (!selectedPlanId.value || !selectedVersionId.value) return;
  const r = await apiPost<VersionSummary>(
    `/api/plans/${selectedPlanId.value}/versions/${selectedVersionId.value}/copy`,
    { note: copyNote.value },
  );
  if (!r.ok) {
    copyError.value = r.message;
    return;
  }
  copyOpen.value = false;
  copyNote.value = "";
  await refresh();
  selectedVersionId.value = r.data.id;
}

async function doRollback() {
  if (!selectedPlanId.value || !selectedVersionId.value) return;
  const r = await apiPost<{ id: string; version_no: number }>(
    `/api/plans/${selectedPlanId.value}/versions/${selectedVersionId.value}/rollback`,
    { note: rollbackNote.value || "rollback" },
  );
  if (r.ok) {
    rollbackOpen.value = false;
    rollbackNote.value = "";
    await refresh();
  }
}

async function createPlan() {
  createError.value = null;
  if (!newPlan.name || !newPlan.part_number) {
    createError.value = "Name and part number are required.";
    return;
  }
  const r = await apiPost<PlanSummary>("/api/plans", {
    name: newPlan.name,
    description: newPlan.description,
    note: newPlan.note,
    lines: [
      {
        line_identity_key: newPlan.line_key,
        part_number: newPlan.part_number,
        quantity: newPlan.quantity,
        unit: newPlan.unit,
      },
    ],
  });
  if (!r.ok) {
    createError.value = r.message;
    return;
  }
  createOpen.value = false;
  newPlan.name = "";
  newPlan.description = "";
  newPlan.part_number = "";
  await refresh();
}

watch([selectedPlanId, selectedVersionId], loadDiff);

onMounted(refresh);
</script>

<template>
  <section>
    <div class="header-row">
      <h2>Build plans</h2>
      <button
        v-if="canManage"
        type="button"
        class="primary"
        @click="createOpen = true"
        data-testid="open-create-plan"
      >New plan</button>
    </div>

    <div v-if="createOpen" class="modal" role="dialog" data-testid="create-plan-modal">
      <div class="modal__card">
        <h3>Create plan</h3>
        <p v-if="createError" class="error" data-testid="create-plan-error">{{ createError }}</p>
        <label>Name
          <input v-model="newPlan.name" type="text" data-testid="new-plan-name" />
        </label>
        <label>Description
          <input v-model="newPlan.description" type="text" data-testid="new-plan-desc" />
        </label>
        <label>First line identity key
          <input v-model="newPlan.line_key" type="text" data-testid="new-plan-line-key" />
        </label>
        <label>Part number
          <input v-model="newPlan.part_number" type="text" data-testid="new-plan-part" />
        </label>
        <label>Quantity
          <input v-model="newPlan.quantity" type="text" data-testid="new-plan-qty" />
        </label>
        <footer>
          <button type="button" @click="createOpen = false">Cancel</button>
          <button type="button" class="primary" @click="createPlan" data-testid="create-plan-submit">
            Create
          </button>
        </footer>
      </div>
    </div>

    <div class="plans">
      <ul class="plans__list">
        <li
          v-for="p in plans"
          :key="p.id"
          :class="{ selected: p.id === selectedPlanId }"
          @click="selectedPlanId = p.id; selectedVersionId = p.head_version_id"
          :data-testid="`plan-${p.id}`"
        >
          <strong>{{ p.name }}</strong>
          <span>v{{ p.head_version_no }}</span>
        </li>
        <li v-if="!plans.length" class="empty">No plans yet.</li>
      </ul>

      <aside class="plans__versions" v-if="selectedPlan">
        <h3>Versions</h3>
        <ul>
          <li
            v-for="v in selectedPlan.versions"
            :key="v.id"
            :class="{ selected: v.id === selectedVersionId }"
            @click="selectedVersionId = v.id"
            :data-testid="`version-${v.id}`"
          >
            <strong>v{{ v.version_no }}</strong>
            <em>{{ v.note || '—' }}</em>
          </li>
        </ul>
        <div class="actions">
          <button type="button" @click="shareOpen = true" data-testid="open-share">
            Share link
          </button>
          <button
            v-if="canManage"
            type="button"
            @click="copyOpen = true"
            data-testid="open-copy"
          >
            Copy as new version
          </button>
          <button type="button" @click="rollbackOpen = true" data-testid="open-rollback">
            Roll back to this version
          </button>
        </div>
      </aside>

      <main class="plans__diff" v-if="diff">
        <h3>Compare against parent</h3>
        <BomDiffView :entries="diff.entries as any" />
      </main>
    </div>

    <ShareLinkModal
      v-if="shareOpen && selectedPlanId && selectedVersionId"
      :plan-id="selectedPlanId"
      :version-id="selectedVersionId"
      @close="shareOpen = false"
    />

    <div v-if="copyOpen" class="modal" role="dialog" data-testid="copy-modal">
      <div class="modal__card">
        <h3>Copy as new version</h3>
        <p>
          Duplicate v{{
            selectedPlan?.versions.find((v) => v.id === selectedVersionId)?.version_no
          }} into a new editable version. The new version's parent will be this
          one; no lines are changed.
        </p>
        <p v-if="copyError" class="error" data-testid="copy-error">{{ copyError }}</p>
        <textarea
          v-model="copyNote"
          placeholder="Note (optional)…"
          data-testid="copy-note"
        />
        <footer>
          <button type="button" @click="copyOpen = false">Cancel</button>
          <button
            type="button"
            class="primary"
            @click="doCopy"
            data-testid="copy-confirm"
          >Copy</button>
        </footer>
      </div>
    </div>

    <div v-if="rollbackOpen" class="modal" role="dialog" data-testid="rollback-modal">
      <div class="modal__card">
        <h3>Confirm rollback</h3>
        <p>
          Create a new version from v{{
            selectedPlan?.versions.find((v) => v.id === selectedVersionId)?.version_no
          }}?
        </p>
        <textarea v-model="rollbackNote" placeholder="Reason…" data-testid="rollback-note" />
        <footer>
          <button @click="rollbackOpen = false">Cancel</button>
          <button @click="doRollback" data-testid="rollback-confirm">Roll back</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<style scoped>
.plans { display: grid; grid-template-columns: 240px 240px 1fr; gap: 16px; }
.plans__list, .plans__versions ul { list-style: none; padding: 0; margin: 0; }
.plans__list li, .plans__versions li { padding: 8px 10px; border-radius: 4px; cursor: pointer; display: flex; flex-direction: column; font-size: 13px; }
.plans__list li:hover, .plans__versions li:hover { background: #f6f8fa; }
.plans__list li.selected, .plans__versions li.selected { background: #ddf4ff; }
.plans__list li span, .plans__versions li em { color: #57606a; font-size: 11px; }
.empty { font-size: 13px; color: #57606a; padding: 12px; }
.actions { margin-top: 12px; display: flex; flex-direction: column; gap: 8px; }
.actions button { padding: 6px 10px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; font-size: 13px; }
.modal { position: fixed; inset: 0; background: rgba(13, 17, 23, 0.5); display: grid; place-items: center; z-index: 50; }
.modal__card { background: #fff; padding: 24px; border-radius: 8px; width: 400px; }
.modal__card textarea { width: 100%; min-height: 80px; margin: 8px 0; padding: 6px; border: 1px solid #d0d7de; border-radius: 4px; }
.modal__card label { display: flex; flex-direction: column; font-size: 12px; color: #57606a; margin-bottom: 8px; }
.modal__card input { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
footer { display: flex; justify-content: flex-end; gap: 8px; }
.header-row { display: flex; justify-content: space-between; align-items: center; }
.primary { background: #0969da; color: #fff; border-color: #0969da; }
.error { color: #cf222e; background: #ffebe9; border: 1px solid #cf222e; padding: 6px 8px; border-radius: 4px; font-size: 12px; }
</style>
