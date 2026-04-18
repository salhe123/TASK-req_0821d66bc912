import { createRouter, createWebHistory } from "vue-router";
import AssignmentFormView from "@/views/AssignmentFormView.vue";
import CyclesView from "@/views/CyclesView.vue";
import DashboardView from "@/views/DashboardView.vue";
import FeedbackView from "@/views/FeedbackView.vue";
import LoginView from "@/views/LoginView.vue";
import AdminView from "@/views/AdminView.vue";
import ModelsView from "@/views/ModelsView.vue";
import PlansView from "@/views/PlansView.vue";
import { useSessionStore } from "@/stores/session";
import { setUnauthorizedHandler } from "@/lib/api";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/login", name: "login", component: LoginView, meta: { public: true } },
    { path: "/", name: "dashboard", component: DashboardView },
    { path: "/cycles", name: "cycles", component: CyclesView },
    { path: "/assignments/:id", name: "assignment-form", component: AssignmentFormView },
    { path: "/plans", name: "plans", component: PlansView },
    { path: "/models", name: "models", component: ModelsView },
    { path: "/feedback", name: "feedback", component: FeedbackView },
    { path: "/admin", name: "admin", component: AdminView },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});

router.beforeEach(async (to) => {
  const session = useSessionStore();
  if (to.meta.public) return true;
  if (session.isAuthenticated) return true;
  await session.refresh();
  if (session.isAuthenticated) return true;
  return { name: "login", query: { next: to.fullPath } };
});

setUnauthorizedHandler(() => {
  const session = useSessionStore();
  session.clear();
  if (router.currentRoute.value.name !== "login") {
    router.push({ name: "login", query: { next: router.currentRoute.value.fullPath } });
  }
});
