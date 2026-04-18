<script setup lang="ts">
import { ref } from "vue";
import { apiPost } from "@/lib/api";

const props = defineProps<{ planId: string; versionId: string }>();
const emit = defineEmits<{ (e: "close"): void }>();

const role = ref("Plan Owner");
const expiresInDays = ref(7);
const issuedToken = ref<string | null>(null);
const error = ref<string | null>(null);
const submitting = ref(false);

async function issue() {
  error.value = null;
  submitting.value = true;
  const r = await apiPost<{ token: string; expires_at: string }>(
    `/api/plans/${props.planId}/versions/${props.versionId}/share`,
    { role: role.value, expires_in_days: expiresInDays.value },
  );
  submitting.value = false;
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  issuedToken.value = r.data.token;
}
</script>

<template>
  <div class="modal" role="dialog" aria-label="Issue share link" data-testid="share-modal">
    <div class="modal__card">
      <h3>Issue share link</h3>
      <label>
        <span>Role</span>
        <select v-model="role" data-testid="share-role">
          <option>Plan Owner</option>
          <option>Administrator</option>
          <option>Reviewer</option>
        </select>
      </label>
      <label>
        <span>Expires in days (max 7)</span>
        <input
          type="number"
          v-model.number="expiresInDays"
          min="1"
          max="7"
          data-testid="share-days"
        />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <div v-if="issuedToken" class="token">
        <p>One-time — copy now:</p>
        <code data-testid="share-token">{{ issuedToken }}</code>
      </div>
      <footer>
        <button type="button" @click="emit('close')">Close</button>
        <button
          v-if="!issuedToken"
          type="button"
          :disabled="submitting"
          @click="issue"
          data-testid="share-issue"
        >
          {{ submitting ? "Issuing…" : "Issue" }}
        </button>
      </footer>
    </div>
  </div>
</template>

<style scoped>
.modal { position: fixed; inset: 0; background: rgba(13, 17, 23, 0.5); display: grid; place-items: center; z-index: 50; }
.modal__card { background: #fff; padding: 24px; border-radius: 8px; width: 400px; display: flex; flex-direction: column; gap: 12px; }
.modal label { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: #57606a; }
.modal input, .modal select { padding: 6px 10px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 14px; }
.error { color: #cf222e; font-size: 13px; margin: 0; }
.token { background: #f6f8fa; padding: 12px; border-radius: 6px; font-size: 12px; word-break: break-all; }
.token code { display: block; margin-top: 6px; font-family: ui-monospace, monospace; }
footer { display: flex; justify-content: flex-end; gap: 8px; }
footer button { padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; }
footer button[data-testid="share-issue"] { background: #1f6feb; color: #fff; border-color: #1f6feb; }
</style>
