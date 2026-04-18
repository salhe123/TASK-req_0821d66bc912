<script setup lang="ts">
import { ref, watch } from "vue";
import { apiPost } from "@/lib/api";

export type FeedbackKind = "LIKE" | "NOT_INTERESTED" | "BLOCK";

interface Payload {
  subjectKey: string;
  targetId: string;
  experimentId: string;
  modelVersionId?: string;
  arm?: "A" | "B";
}

const props = defineProps<{
  subjectKey: string;
  targetId: string;
  experimentId: string;
  modelVersionId?: string;
  arm?: "A" | "B";
  initialState?: FeedbackKind | null;
}>();

const emit = defineEmits<{
  (e: "change", payload: Payload & { kind: FeedbackKind }): void;
  (e: "error", payload: { kind: FeedbackKind; error: string; message: string }): void;
}>();

const state = ref<FeedbackKind | null>(props.initialState ?? null);
const pending = ref(false);

watch(
  () => props.initialState,
  (v) => {
    if (v !== undefined) state.value = v;
  },
);

async function submit(kind: FeedbackKind) {
  if (pending.value) return;
  pending.value = true;
  try {
    const r = await apiPost<{ kind: FeedbackKind }>("/api/feedback", {
      experiment_id: props.experimentId,
      subject_key: props.subjectKey,
      target_id: props.targetId,
      kind,
      arm: props.arm,
      model_version_id: props.modelVersionId,
    });
    if (!r.ok) {
      emit("error", { kind, error: r.error, message: r.message });
      return;
    }
    state.value = kind;
    emit("change", {
      subjectKey: props.subjectKey,
      targetId: props.targetId,
      experimentId: props.experimentId,
      modelVersionId: props.modelVersionId,
      arm: props.arm,
      kind,
    });
  } finally {
    pending.value = false;
  }
}
</script>

<template>
  <div class="feedback" data-testid="feedback-control" :data-state="state ?? ''">
    <button
      type="button"
      :class="{ active: state === 'LIKE' }"
      :disabled="pending"
      data-testid="fb-like"
      :aria-pressed="state === 'LIKE'"
      @click="submit('LIKE')"
    >
      Like
    </button>
    <button
      type="button"
      :class="{ active: state === 'NOT_INTERESTED' }"
      :disabled="pending"
      data-testid="fb-not-interested"
      @click="submit('NOT_INTERESTED')"
    >
      Not interested
    </button>
    <button
      type="button"
      :class="{ active: state === 'BLOCK' }"
      :disabled="pending"
      data-testid="fb-block"
      @click="submit('BLOCK')"
    >
      Block
    </button>
  </div>
</template>

<style scoped>
.feedback { display: inline-flex; gap: 6px; }
.feedback button {
  padding: 4px 10px;
  border: 1px solid #d0d7de;
  border-radius: 16px;
  background: #fff;
  cursor: pointer;
  font-size: 12px;
}
.feedback button.active { background: #ddf4ff; border-color: #0969da; color: #0969da; }
.feedback button:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
