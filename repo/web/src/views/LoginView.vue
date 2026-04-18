<script setup lang="ts">
import { ref } from "vue";
import { useRouter, useRoute } from "vue-router";
import { useSessionStore } from "@/stores/session";

const session = useSessionStore();
const router = useRouter();
const route = useRoute();

const username = ref("");
const password = ref("");
const pending = ref(false);
const errorMessage = ref<string | null>(null);

async function submit() {
  errorMessage.value = null;
  pending.value = true;
  try {
    const result = await session.login(username.value, password.value);
    if (!result.ok) {
      if (result.error === "account_locked") {
        errorMessage.value = session.lockoutMessage ?? "account locked";
      } else {
        errorMessage.value = "invalid username or password";
      }
      return;
    }
    const next = typeof route.query.next === "string" ? route.query.next : "/";
    await router.push(next);
  } finally {
    pending.value = false;
  }
}
</script>

<template>
  <div class="login">
    <form class="login__card" @submit.prevent="submit" aria-label="login">
      <h2>Sign in</h2>
      <label>
        <span>Username</span>
        <input v-model="username" autocomplete="username" required data-testid="username" />
      </label>
      <label>
        <span>Password</span>
        <input v-model="password" type="password" autocomplete="current-password" required data-testid="password" />
      </label>
      <p v-if="errorMessage" class="login__error" role="alert" data-testid="login-error">{{ errorMessage }}</p>
      <button type="submit" :disabled="pending" data-testid="login-submit">
        {{ pending ? "Signing in..." : "Sign in" }}
      </button>
    </form>
  </div>
</template>

<style scoped>
.login {
  display: grid;
  place-items: center;
  min-height: 100vh;
  background: #f6f8fa;
}
.login__card {
  background: #fff;
  padding: 32px;
  border: 1px solid #d0d7de;
  border-radius: 8px;
  width: 360px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.login__card h2 {
  margin: 0;
  font-size: 20px;
}
.login__card label {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 13px;
  color: #57606a;
}
.login__card input {
  padding: 8px 10px;
  border: 1px solid #d0d7de;
  border-radius: 6px;
  font-size: 14px;
}
.login__card button {
  background: #1f6feb;
  color: #fff;
  border: none;
  padding: 10px;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
}
.login__card button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.login__error {
  color: #cf222e;
  font-size: 13px;
  margin: 0;
}
</style>
