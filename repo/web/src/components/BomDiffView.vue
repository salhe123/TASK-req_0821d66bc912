<script setup lang="ts">
interface BomLine {
  line_identity_key: string;
  part_number: string;
  description: string;
  quantity: string;
  unit: string;
  notes: string;
  tags: string[];
}

interface DiffEntry {
  line_identity_key: string;
  changes: string[];
  base: BomLine | null;
  target: BomLine | null;
}

const props = defineProps<{ entries: DiffEntry[] }>();

function tone(changes: string[]): string {
  if (changes.includes("ADDED")) return "added";
  if (changes.includes("REMOVED")) return "removed";
  return "changed";
}
</script>

<template>
  <table class="diff" data-testid="bom-diff">
    <thead>
      <tr>
        <th>Line</th>
        <th>Changes</th>
        <th>Base</th>
        <th>Target</th>
      </tr>
    </thead>
    <tbody>
      <tr
        v-for="e in entries"
        :key="e.line_identity_key"
        :class="`diff__row diff__row--${tone(e.changes)}`"
        :data-testid="`diff-row-${e.line_identity_key}`"
      >
        <td>{{ e.line_identity_key }}</td>
        <td>
          <span v-for="c in e.changes" :key="c" class="chip" :data-change="c">{{ c }}</span>
        </td>
        <td>
          <div v-if="e.base">
            <code>{{ e.base.part_number }}</code> × {{ e.base.quantity }} {{ e.base.unit }}
            <p v-if="e.base.notes" class="notes">{{ e.base.notes }}</p>
          </div>
          <em v-else>—</em>
        </td>
        <td>
          <div v-if="e.target">
            <code>{{ e.target.part_number }}</code> × {{ e.target.quantity }} {{ e.target.unit }}
            <p v-if="e.target.notes" class="notes">{{ e.target.notes }}</p>
          </div>
          <em v-else>—</em>
        </td>
      </tr>
      <tr v-if="!entries.length">
        <td colspan="4" class="empty">No differences.</td>
      </tr>
    </tbody>
  </table>
</template>

<style scoped>
.diff { width: 100%; border-collapse: collapse; font-size: 13px; }
.diff th, .diff td { padding: 8px 10px; border-bottom: 1px solid #d0d7de; text-align: left; vertical-align: top; }
.diff__row--added    { background: #dafbe1; }
.diff__row--removed  { background: #ffebe9; }
.diff__row--changed  { background: #fff8c5; }
.chip { display: inline-block; background: #fff; border: 1px solid #d0d7de; border-radius: 10px; padding: 2px 8px; margin-right: 4px; font-size: 11px; }
.notes { margin: 4px 0 0; font-size: 12px; color: #57606a; }
.empty { text-align: center; color: #57606a; }
</style>
