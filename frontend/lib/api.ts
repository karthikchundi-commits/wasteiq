import axios from "axios";

// Relative baseURL + paths without leading slash = axios prepends baseURL correctly.
// e.g. api.get("projects/") → /api/proxy/projects/ → proxied to backend
const BASE_URL = "/api/proxy";

export const API_BASE_URL = BASE_URL;

export const api = axios.create({ baseURL: BASE_URL });

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
    api.post("auth/register", data),
  login: (email: string, password: string) =>
    api.postForm("auth/login", { username: email, password }),
};

// --- Projects ---
export const projectsApi = {
  list: () => api.get("projects/"),
  get: (id: string) => api.get(`projects/${id}`),
  create: (data: any) => api.post("projects/", data),
  listCrews: () => api.get("projects/crews/list"),
  createCrew: (data: any) => api.post("projects/crews/", data),
};

// --- Predictions ---
export const predictionsApi = {
  generate: (project_id: string) => api.post("predictions/generate", { project_id }),
  get: (project_id: string) => api.get(`predictions/${project_id}`),
};

// --- Actuals ---
export const actualsApi = {
  record: (data: { material_line_item_id: string; actual_waste_qty: number; notes?: string }) =>
    api.post("actuals/", data),
  getByProject: (project_id: string) => api.get(`actuals/project/${project_id}`),
};

// --- Recommendations ---
export const recommendationsApi = {
  get: (project_id: string) => api.get(`recommendations/${project_id}`),
};

// --- Oracle Fusion ---
export const oracleApi = {
  pushRequisition: (project_id: string, opts?: { requester_name?: string; deliver_to_location?: string; need_by_date?: string }) =>
    api.post("oracle/push-requisition", { project_id, ...opts }),
};
