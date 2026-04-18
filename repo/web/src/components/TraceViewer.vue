<script setup lang="ts">
interface Step {
  item_key: string;
  raw_present: boolean;
  raw_value: string | null;
  weight: string;
  effective_value: string;
  effective_weight: string;
  missing_strategy: string;
  flags: string[];
}

interface Totals {
  score: string;
  weighted_sum: string;
  weight_sum: string;
}

interface Trace {
  engine_version: string;
  template_version_id: string;
  rule_set_version_id: string;
  inputs: Record<string, string | null>;
  steps: Step[];
  totals: Totals;
}

const props = defineProps<{ trace: Trace; traceHash: string }>();
</script>

<template>
  <section class="trace" data-testid="trace-viewer">
    <header>
      <h3>Calculation trace</h3>
      <p class="hash">sha256: <code data-testid="trace-hash">{{ traceHash }}</code></p>
      <p class="ver">engine v{{ trace.engine_version }}</p>
    </header>
    <table>
      <thead>
        <tr>
          <th>Item</th>
          <th>Raw</th>
          <th>Weight</th>
          <th>Strategy</th>
          <th>Effective value</th>
          <th>Effective weight</th>
          <th>Flags</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="step in trace.steps" :key="step.item_key" :data-testid="`step-${step.item_key}`">
          <td>{{ step.item_key }}</td>
          <td>{{ step.raw_present ? step.raw_value : "—" }}</td>
          <td>{{ step.weight }}</td>
          <td>{{ step.missing_strategy }}</td>
          <td>{{ step.effective_value }}</td>
          <td>{{ step.effective_weight }}</td>
          <td>
            <span v-for="flag in step.flags" :key="flag" class="chip">{{ flag }}</span>
          </td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="4">Totals</td>
          <td data-testid="trace-weighted-sum">{{ trace.totals.weighted_sum }}</td>
          <td data-testid="trace-weight-sum">{{ trace.totals.weight_sum }}</td>
          <td data-testid="trace-score">score = {{ trace.totals.score }}</td>
        </tr>
      </tfoot>
    </table>
  </section>
</template>

<style scoped>
.trace { border: 1px solid #d0d7de; border-radius: 6px; padding: 16px; margin-top: 16px; }
.trace h3 { margin: 0 0 4px; }
.trace .hash { font-size: 12px; color: #57606a; margin: 0; }
.trace .ver { font-size: 11px; color: #6e7781; margin: 0 0 8px; }
.trace table { width: 100%; border-collapse: collapse; font-size: 13px; }
.trace th, .trace td { padding: 6px 10px; border-bottom: 1px solid #eaeef2; text-align: left; }
.trace tfoot td { font-weight: 600; }
.chip { display: inline-block; background: #fff8c5; border: 1px solid #d4a72c; border-radius: 10px; padding: 2px 8px; margin-right: 4px; font-size: 11px; }
</style>
