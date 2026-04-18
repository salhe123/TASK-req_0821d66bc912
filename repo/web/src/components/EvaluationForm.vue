<script setup lang="ts">
import { computed, ref, watch } from "vue";

interface TemplateItem {
  key: string;
  label: string;
  weight: number;
  required: boolean;
  missing_strategy: string;
  min_value?: number | null;
  max_value?: number | null;
}

const props = defineProps<{
  items: TemplateItem[];
  readonly?: boolean;
  initialValues?: Record<string, number | null>;
}>();

const emit = defineEmits<{
  (e: "update:values", values: Record<string, number | null>): void;
  (e: "submittable", payload: { submittable: boolean; thresholdKeys: string[] }): void;
}>();

const thresholdsAcknowledged = ref(false);

const values = ref<Record<string, number | null>>({ ...(props.initialValues ?? {}) });

watch(values, (v) => emit("update:values", v), { deep: true });

const subtotal = computed(() => {
  let weighted = 0;
  let weightSum = 0;
  for (const item of props.items) {
    const raw = values.value[item.key];
    if (raw === null || raw === undefined) continue;
    weighted += raw * item.weight;
    weightSum += item.weight;
  }
  return weightSum === 0 ? 0 : weighted / weightSum;
});

function flagsFor(item: TemplateItem): string[] {
  const flags: string[] = [];
  const raw = values.value[item.key];
  if (raw === null || raw === undefined) {
    if (item.required) flags.push("missing");
    return flags;
  }
  if (item.min_value != null && raw < item.min_value) flags.push("threshold_exceeded");
  if (item.max_value != null && raw > item.max_value) flags.push("threshold_exceeded");
  return flags;
}

const thresholdKeys = computed(() =>
  props.items.filter((it) => flagsFor(it).includes("threshold_exceeded")).map((it) => it.key),
);

const submittable = computed(
  () => thresholdKeys.value.length === 0 || thresholdsAcknowledged.value,
);

watch(
  [submittable, thresholdKeys],
  ([ok, keys]) => emit("submittable", { submittable: ok, thresholdKeys: keys }),
  { immediate: true },
);

defineExpose({ submittable, thresholdKeys });
</script>

<template>
  <form class="eval-form" data-testid="evaluation-form" @submit.prevent>
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Weight</th>
          <th>Value</th>
          <th>Flags</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="item in items" :key="item.key">
          <td>
            {{ item.label }}
            <span v-if="item.required" class="req">*</span>
          </td>
          <td>{{ item.weight }}</td>
          <td>
            <input
              type="number"
              step="any"
              :value="values[item.key] ?? ''"
              :disabled="readonly"
              :data-testid="`input-${item.key}`"
              @input="(e) => {
                const v = (e.target as HTMLInputElement).value;
                values[item.key] = v === '' ? null : Number(v);
              }"
            />
          </td>
          <td>
            <span v-for="flag in flagsFor(item)" :key="flag" class="chip" :data-flag="flag">{{ flag }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="subtotal" data-testid="subtotal">Weighted subtotal: {{ subtotal.toFixed(4) }}</p>
    <label v-if="thresholdKeys.length" class="ack" data-testid="threshold-ack">
      <input
        type="checkbox"
        :checked="thresholdsAcknowledged"
        data-testid="threshold-ack-checkbox"
        @change="(e) => (thresholdsAcknowledged = (e.target as HTMLInputElement).checked)"
      />
      I acknowledge the {{ thresholdKeys.length }} threshold breach(es) and want to submit anyway.
    </label>
  </form>
</template>

<style scoped>
.eval-form table { width: 100%; border-collapse: collapse; font-size: 14px; }
.eval-form th, .eval-form td { padding: 8px 10px; border-bottom: 1px solid #d0d7de; text-align: left; }
.eval-form input { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; width: 120px; }
.eval-form .req { color: #cf222e; margin-left: 4px; }
.chip { display: inline-block; background: #fff8c5; border: 1px solid #d4a72c; border-radius: 10px; padding: 2px 8px; margin-right: 4px; font-size: 11px; }
.subtotal { margin-top: 12px; font-size: 13px; color: #57606a; }
</style>
