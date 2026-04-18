<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{ state: string }>();

const meta = computed(() => {
  switch (props.state) {
    case "NOT_STARTED":
      return { label: "Not started", tone: "neutral", nextAction: "Open and save to begin" };
    case "IN_PROGRESS":
      return { label: "In progress", tone: "info", nextAction: "Submit when complete" };
    case "SUBMITTED":
      return { label: "Submitted", tone: "warn", nextAction: "Awaiting reviewer" };
    case "RETURNED_FOR_REVISION":
      return { label: "Returned for revision", tone: "danger", nextAction: "Address feedback and resubmit" };
    case "ARCHIVED":
      return { label: "Archived", tone: "done", nextAction: "Complete" };
    default:
      return { label: props.state, tone: "neutral", nextAction: "" };
  }
});
</script>

<template>
  <span
    class="tl-badge"
    :class="`tl-badge--${meta.tone}`"
    :title="meta.nextAction"
    :data-state="state"
    :data-testid="`timeline-${state}`"
  >
    <strong>{{ meta.label }}</strong>
    <em v-if="meta.nextAction">{{ meta.nextAction }}</em>
  </span>
</template>

<style scoped>
.tl-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-style: normal;
}
.tl-badge strong {
  font-weight: 600;
}
.tl-badge em {
  font-style: normal;
  opacity: 0.75;
  font-size: 11px;
}
.tl-badge--neutral { background: #eaeef2; color: #1f2328; }
.tl-badge--info    { background: #ddf4ff; color: #0969da; }
.tl-badge--warn    { background: #fff8c5; color: #9a6700; }
.tl-badge--danger  { background: #ffebe9; color: #cf222e; }
.tl-badge--done    { background: #dafbe1; color: #116329; }
</style>
