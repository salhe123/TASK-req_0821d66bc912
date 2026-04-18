<script setup lang="ts">
import { computed } from "vue";
import { RouterLink, RouterView, useRouter, useRoute } from "vue-router";
import { useSessionStore } from "@/stores/session";

interface NavItem {
  to: string;
  label: string;
  requires?: { resource: string; action: string };
}

const session = useSessionStore();
const router = useRouter();
const route = useRoute();

const allNav: NavItem[] = [
  { to: "/", label: "Dashboard" },
  { to: "/cycles", label: "Evaluation Cycles", requires: { resource: "cycle", action: "participate" } },
  { to: "/plans", label: "Build Plans", requires: { resource: "build_plan", action: "view" } },
  { to: "/models", label: "Model Registry", requires: { resource: "model", action: "register" } },
  { to: "/feedback", label: "Feedback", requires: { resource: "feedback", action: "submit" } },
  { to: "/admin", label: "Administration", requires: { resource: "user", action: "manage" } },
];

const visibleNav = computed(() =>
  allNav.map((item) => ({
    ...item,
    allowed: !item.requires || session.hasPermission(item.requires.resource, item.requires.action),
    enabled: !item.requires || session.hasPermission(item.requires.resource, item.requires.action),
  })),
);

const showShell = computed(() => route.name !== "login");

async function signOut() {
  await session.logout();
  router.push({ name: "login" });
}
</script>

<template>
  <template v-if="!showShell">
    <RouterView />
  </template>
  <div v-else class="app-shell">
    <nav class="app-shell__nav" aria-label="Primary">
      <h1>MGEW</h1>
      <ul>
        <li v-for="item in visibleNav" :key="item.to">
          <RouterLink v-if="item.enabled" :to="item.to">{{ item.label }}</RouterLink>
          <a v-else aria-disabled="true" href="#">{{ item.label }}</a>
        </li>
      </ul>
      <div class="app-shell__user" v-if="session.user">
        <p>{{ session.user.username }}</p>
        <button @click="signOut" data-testid="sign-out">Sign out</button>
      </div>
    </nav>
    <main class="app-shell__main">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.app-shell__user {
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid #30363d;
  font-size: 13px;
  color: #9da7b1;
}
.app-shell__user p {
  margin: 0 0 8px;
}
.app-shell__user button {
  background: transparent;
  color: #e6edf3;
  border: 1px solid #30363d;
  border-radius: 6px;
  padding: 6px 10px;
  font-size: 13px;
  cursor: pointer;
}
</style>
