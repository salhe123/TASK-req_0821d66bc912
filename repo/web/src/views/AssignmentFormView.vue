<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { apiGet, apiPost } from "@/lib/api";
import { useSessionStore } from "@/stores/session";
import EvaluationForm from "@/components/EvaluationForm.vue";

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

interface TemplateItem {
  key: string;
  label: string;
  weight: number;
  required: boolean;
  missing_strategy: string;
  min_value?: number | null;
  max_value?: number | null;
}

interface AssignmentForm {
  assignment: AssignmentSummary;
  cycle_name: string;
  deadline_at: string;
  template_version_id: string;
  items: TemplateItem[];
  draft_values: Record<string, unknown>;
}

const route = useRoute();
const router = useRouter();
const session = useSessionStore();
const form = ref<AssignmentForm | null>(null);
const values = ref<Record<string, number | null>>({});
const submittable = ref(true);
const thresholdKeys = ref<string[]>([]);
const status = ref<"idle" | "saving" | "submitting" | "reviewing">("idle");
const message = ref<string | null>(null);
const error = ref<string | null>(null);
const returnReason = ref("");

const assignmentId = computed(() => String(route.params.id ?? ""));
const isEvaluator = computed(
  () => form.value?.assignment.evaluator_user_id === session.user?.userId,
);
const isAssignedReviewer = computed(
  () =>
    !!form.value?.assignment.reviewer_user_id &&
    form.value?.assignment.reviewer_user_id === session.user?.userId &&
    session.hasPermission("cycle", "review"),
);
const readOnly = computed(() => {
  const s = form.value?.assignment.state;
  if (s === "ARCHIVED") return true;
  if (!isEvaluator.value) return true;
  return s === "SUBMITTED";
});
const canReview = computed(
  () =>
    isAssignedReviewer.value &&
    form.value?.assignment.state === "SUBMITTED",
);
const initialValues = computed(() => {
  const out: Record<string, number | null> = {};
  if (!form.value) return out;
  for (const item of form.value.items) {
    const raw = form.value.draft_values?.[item.key];
    if (raw === undefined || raw === null || raw === "") {
      out[item.key] = null;
    } else {
      const num = Number(raw);
      out[item.key] = Number.isFinite(num) ? num : null;
    }
  }
  return out;
});

async function load() {
  error.value = null;
  message.value = null;
  const r = await apiGet<AssignmentForm>(`/api/assignments/${assignmentId.value}/form`);
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  form.value = r.data;
  values.value = { ...initialValues.value };
}

function onValues(v: Record<string, number | null>) {
  values.value = v;
}

function onSubmittable(payload: { submittable: boolean; thresholdKeys: string[] }) {
  submittable.value = payload.submittable;
  thresholdKeys.value = payload.thresholdKeys;
}

function collectPayload(): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(values.value)) {
    if (v === null || v === undefined) continue;
    out[k] = v;
  }
  return out;
}

async function save() {
  status.value = "saving";
  message.value = null;
  error.value = null;
  const r = await apiPost<AssignmentSummary>(
    `/api/assignments/${assignmentId.value}/save`,
    { values: collectPayload() },
  );
  status.value = "idle";
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  if (form.value) form.value.assignment = r.data;
  message.value = "Draft saved.";
}

async function submit() {
  if (!submittable.value) {
    error.value = "Acknowledge the threshold breaches before submitting.";
    return;
  }
  status.value = "submitting";
  message.value = null;
  error.value = null;
  const r = await apiPost<AssignmentSummary>(
    `/api/assignments/${assignmentId.value}/submit`,
    { values: collectPayload() },
  );
  status.value = "idle";
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  if (form.value) form.value.assignment = r.data;
  message.value = "Submitted.";
}

async function returnForRevision() {
  if (!returnReason.value || returnReason.value.length < 3) {
    error.value = "Return reason must be at least 3 characters.";
    return;
  }
  status.value = "reviewing";
  message.value = null;
  error.value = null;
  const r = await apiPost<AssignmentSummary>(
    `/api/assignments/${assignmentId.value}/return`,
    { reason: returnReason.value },
  );
  status.value = "idle";
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  if (form.value) form.value.assignment = r.data;
  returnReason.value = "";
  message.value = "Returned for revision.";
}

async function approve() {
  status.value = "reviewing";
  message.value = null;
  error.value = null;
  const r = await apiPost<AssignmentSummary>(
    `/api/assignments/${assignmentId.value}/approve`,
  );
  status.value = "idle";
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  if (form.value) form.value.assignment = r.data;
  message.value = "Approved.";
}

onMounted(load);
</script>

<template>
  <section class="form-view">
    <button class="back" @click="router.push({ name: 'cycles' })">← Back to cycles</button>
    <div v-if="error" class="error" data-testid="form-error">{{ error }}</div>
    <div v-else-if="!form">Loading…</div>
    <template v-else>
      <header>
        <h2>{{ form.cycle_name }}</h2>
        <p class="meta">
          Deadline: {{ form.deadline_at }} · State:
          <span data-testid="assignment-state">{{ form.assignment.state }}</span>
        </p>
        <p v-if="form.assignment.returned_reason" class="returned">
          Returned for revision: {{ form.assignment.returned_reason }}
        </p>
      </header>

      <EvaluationForm
        :items="form.items"
        :readonly="readOnly"
        :initial-values="initialValues"
        @update:values="onValues"
        @submittable="onSubmittable"
      />

      <div
        v-if="isEvaluator"
        class="actions"
        data-testid="assignment-form"
      >
        <button
          type="button"
          :disabled="readOnly || status !== 'idle'"
          @click="save"
          data-testid="save-btn"
        >
          {{ status === "saving" ? "Saving…" : "Save draft" }}
        </button>
        <button
          type="button"
          :disabled="readOnly || status !== 'idle' || !submittable"
          @click="submit"
          data-testid="submit-btn"
        >
          {{ status === "submitting" ? "Submitting…" : "Submit" }}
        </button>
      </div>

      <div
        v-if="canReview"
        class="review-panel"
        data-testid="review-panel"
      >
        <h3>Review actions</h3>
        <label>
          Reason (for return)
          <input
            v-model="returnReason"
            type="text"
            placeholder="what needs to change"
            data-testid="return-reason"
          />
        </label>
        <div class="actions">
          <button
            type="button"
            :disabled="status !== 'idle'"
            @click="returnForRevision"
            data-testid="return-btn"
          >
            Return for revision
          </button>
          <button
            type="button"
            class="approve"
            :disabled="status !== 'idle'"
            @click="approve"
            data-testid="approve-btn"
          >
            Approve
          </button>
        </div>
      </div>

      <p v-if="message" class="ok" data-testid="form-message">{{ message }}</p>
    </template>
  </section>
</template>

<style scoped>
.form-view { max-width: 720px; margin: 0 auto; }
.back { margin-bottom: 16px; background: transparent; border: none; color: #0969da; cursor: pointer; padding: 0; }
.meta { color: #57606a; font-size: 13px; }
.returned { background: #fff8c5; border: 1px solid #d4a72c; border-radius: 4px; padding: 8px; }
.actions { display: flex; gap: 8px; margin-top: 18px; }
.actions button { padding: 6px 14px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; }
.actions button:last-child { background: #2da44e; color: #fff; border-color: #2da44e; }
.actions button:disabled { opacity: 0.5; cursor: not-allowed; }
.ok { color: #1a7f37; margin-top: 12px; }
.error { color: #cf222e; background: #ffebe9; border: 1px solid #cf222e; border-radius: 4px; padding: 8px; }
.review-panel { margin-top: 24px; padding: 12px 14px; border: 1px solid #d0d7de; border-radius: 6px; background: #f6f8fa; }
.review-panel h3 { margin-top: 0; font-size: 14px; }
.review-panel label { display: flex; flex-direction: column; font-size: 12px; color: #57606a; margin-bottom: 10px; }
.review-panel input { padding: 6px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
.review-panel .approve { background: #0969da; color: #fff; border-color: #0969da; }
</style>
