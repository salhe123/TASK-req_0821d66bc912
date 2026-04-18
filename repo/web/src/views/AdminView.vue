<script setup lang="ts">
import { onMounted, ref } from "vue";
import { apiGet, apiPost } from "@/lib/api";

interface BackupArchive {
  id: string;
  filename: string;
  size_bytes: number;
  manifest_hash: string;
  kek_fingerprint: string;
  created_at: string;
}

interface AuditRow {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_user_id: string | null;
  created_at: string;
  payload: Record<string, unknown>;
}

const tab = ref<"users" | "audit" | "backups">("users");

const users = ref<Array<{ id: string; username: string; roles: string[]; locked: boolean }>>([]);
const audit = ref<AuditRow[]>([]);
const backups = ref<BackupArchive[]>([]);
const auditFilter = ref({ action: "", resource_type: "" });
const confirmArchive = ref<string | null>(null);
const pendingOp = ref<string | null>(null);
const error = ref<string | null>(null);

async function loadUsers() {
  const r = await apiGet<{ items: typeof users.value }>("/api/admin/users");
  if (r.ok) users.value = r.data.items;
}

async function loadAudit() {
  const params = new URLSearchParams();
  if (auditFilter.value.action) params.set("action", auditFilter.value.action);
  if (auditFilter.value.resource_type) params.set("resource_type", auditFilter.value.resource_type);
  const qs = params.toString();
  const r = await apiGet<{ items: AuditRow[] }>(`/api/admin/audit/logs${qs ? `?${qs}` : ""}`);
  if (r.ok) audit.value = r.data.items;
}

async function loadBackups() {
  const r = await apiGet<{ items: BackupArchive[] }>("/api/admin/backups");
  if (r.ok) backups.value = r.data.items;
}

async function createBackup() {
  pendingOp.value = "create";
  await apiPost("/api/admin/backups");
  pendingOp.value = null;
  await loadBackups();
}

async function stageRestore(id: string) {
  error.value = null;
  pendingOp.value = `stage:${id}`;
  const r = await apiPost<{ maintenance: { active: boolean } }>(
    `/api/admin/backups/${id}/stage`,
  );
  pendingOp.value = null;
  if (!r.ok) {
    error.value = r.message;
    return;
  }
  confirmArchive.value = id;
}

async function commitRestore() {
  if (!confirmArchive.value) return;
  pendingOp.value = "commit";
  const r = await apiPost(`/api/admin/backups/${confirmArchive.value}/commit`);
  pendingOp.value = null;
  if (r.ok) {
    confirmArchive.value = null;
    await loadBackups();
  }
}

async function abortRestore() {
  if (!confirmArchive.value) return;
  pendingOp.value = "abort";
  const r = await apiPost(`/api/admin/backups/${confirmArchive.value}/abort`);
  pendingOp.value = null;
  if (r.ok) {
    confirmArchive.value = null;
    await loadBackups();
  }
}

function switchTab(v: typeof tab.value) {
  tab.value = v;
  if (v === "users") loadUsers();
  if (v === "audit") loadAudit();
  if (v === "backups") loadBackups();
}

onMounted(() => switchTab("users"));
</script>

<template>
  <section>
    <h2>Administration</h2>
    <nav class="tabs">
      <button :class="{ active: tab === 'users' }" @click="switchTab('users')" data-testid="tab-users">Users</button>
      <button :class="{ active: tab === 'audit' }" @click="switchTab('audit')" data-testid="tab-audit">Audit</button>
      <button :class="{ active: tab === 'backups' }" @click="switchTab('backups')" data-testid="tab-backups">Backups</button>
    </nav>

    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="tab === 'users'">
      <table class="admin-table">
        <thead><tr><th>Username</th><th>Roles</th><th>Locked</th></tr></thead>
        <tbody>
          <tr v-for="u in users" :key="u.id">
            <td>{{ u.username }}</td>
            <td>{{ u.roles.join(", ") }}</td>
            <td>{{ u.locked ? "yes" : "no" }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="tab === 'audit'">
      <div class="filters">
        <input v-model="auditFilter.action" placeholder="action" data-testid="audit-action" />
        <input v-model="auditFilter.resource_type" placeholder="resource type" data-testid="audit-resource" />
        <button @click="loadAudit">Apply</button>
      </div>
      <table class="admin-table">
        <thead><tr><th>When</th><th>Action</th><th>Resource</th><th>Actor</th></tr></thead>
        <tbody>
          <tr v-for="r in audit" :key="r.id" :data-testid="`audit-row-${r.id}`">
            <td>{{ r.created_at }}</td>
            <td><code>{{ r.action }}</code></td>
            <td>{{ r.resource_type }} / {{ r.resource_id ?? "—" }}</td>
            <td>{{ r.actor_user_id ?? "—" }}</td>
          </tr>
        </tbody>
      </table>
    </template>

    <template v-else-if="tab === 'backups'">
      <div class="backup-actions">
        <button @click="createBackup" :disabled="pendingOp === 'create'" data-testid="backup-create">
          {{ pendingOp === "create" ? "Creating..." : "Create archive now" }}
        </button>
      </div>
      <table class="admin-table">
        <thead>
          <tr><th>Filename</th><th>Size</th><th>Manifest hash</th><th>KEK fingerprint</th><th>Created</th><th></th></tr>
        </thead>
        <tbody>
          <tr v-for="a in backups" :key="a.id" :data-testid="`backup-${a.id}`">
            <td><code>{{ a.filename }}</code></td>
            <td>{{ a.size_bytes }}</td>
            <td><code>{{ a.manifest_hash.slice(0, 12) }}…</code></td>
            <td><code>{{ a.kek_fingerprint.slice(0, 12) }}…</code></td>
            <td>{{ a.created_at }}</td>
            <td>
              <button
                :disabled="pendingOp === `stage:${a.id}`"
                @click="stageRestore(a.id)"
                :data-testid="`stage-${a.id}`"
              >Stage restore</button>
            </td>
          </tr>
        </tbody>
      </table>

      <div v-if="confirmArchive" class="modal" role="dialog" data-testid="restore-confirm">
        <div class="modal__card">
          <h3>Restore staged</h3>
          <p>Maintenance mode is active. Choose whether to atomically swap (commit) or abort.</p>
          <footer>
            <button @click="abortRestore" :disabled="pendingOp === 'abort'" data-testid="restore-abort">Abort</button>
            <button @click="commitRestore" :disabled="pendingOp === 'commit'" data-testid="restore-commit">Commit</button>
          </footer>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.tabs { display: flex; gap: 6px; margin-bottom: 16px; }
.tabs button { padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; font-size: 13px; }
.tabs button.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }
.admin-table { width: 100%; border-collapse: collapse; font-size: 13px; }
.admin-table th, .admin-table td { padding: 8px 10px; border-bottom: 1px solid #d0d7de; text-align: left; }
.filters { display: flex; gap: 8px; margin-bottom: 12px; }
.filters input { padding: 4px 8px; border: 1px solid #d0d7de; border-radius: 4px; font-size: 13px; }
.filters button { padding: 4px 10px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; }
.backup-actions { margin-bottom: 12px; }
.backup-actions button { padding: 6px 12px; border: 1px solid #1f6feb; background: #1f6feb; color: #fff; border-radius: 4px; cursor: pointer; }
.error { color: #cf222e; }
.modal { position: fixed; inset: 0; background: rgba(13, 17, 23, 0.5); display: grid; place-items: center; z-index: 50; }
.modal__card { background: #fff; padding: 24px; border-radius: 8px; width: 420px; }
footer { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
footer button { padding: 6px 12px; border: 1px solid #d0d7de; border-radius: 4px; background: #fff; cursor: pointer; }
footer button[data-testid="restore-commit"] { background: #1f6feb; color: #fff; border-color: #1f6feb; }
footer button[data-testid="restore-abort"] { background: #cf222e; color: #fff; border-color: #cf222e; }
</style>
