import axios from "axios";

// All API calls go through a Next.js API route (/api/proxy → backend).
// This avoids CORS and explicitly forwards the Authorization header.
const BASE_URL = "/api/proxy";

export const API_BASE_URL = BASE_URL;

export const api = axios.create({ baseURL: BASE_URL });

// Attach JWT token from localStorage to every request
api.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("wasteiq_token");
    if (token) config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// --- Auth ---
export const authApi = {
  register: (data: { email: string; password: string; full_name: string; company_name: string }) =>
    api.post("/auth/register", data),
  login: (email: string, password: string) =>
    api.postForm("/auth/login", { username: email, password }),
};

// --- Projects ---
export const projectsApi = {
  list: () => api.get("/projects/"),
  get: (id: string) => api.get(`/projects/${id}`),
  create: (data: any) => api.post("/projects/", data),
  listCrews: () => api.get("/projects/crews/list"),
  createCrew: (data: any) => api.post("/projects/crews/", data),
};

// --- Predictions ---
export const predictionsApi = {
  generate: (project_id: string) => api.post("/predictions/generate", { project_id }),
  get: (project_id: string) => api.get(`/predictions/${project_id}`),
};

// --- Actuals ---
export const actualsApi = {
  record: (data: { material_line_item_id: string; actual_waste_qty: number; notes?: string }) =>
    api.post("/actuals/", data),
  getByProject: (project_id: string) => api.get(`/actuals/project/${project_id}`),
};
