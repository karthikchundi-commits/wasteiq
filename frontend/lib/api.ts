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

// --- Analytics ---
export const analyticsApi = {
  overview: () => api.get("analytics/overview"),
};

// --- Procurement Middleware ---
export const procurementApi = {
  stage: (project_id: string, opts?: {
    erp_type?: string;
    push_url?: string;
    default_need_by_days?: number;
    deliver_to_location?: string;
    requester_name?: string;
    notes?: string;
  }) => api.post(`procurement/stage/${project_id}`, opts ?? {}),

  get: (project_id: string) => api.get(`procurement/${project_id}`),

  updateLine: (line_id: string, data: {
    requested_qty?: number;
    need_by_date?: string;
    deliver_to_location?: string;
    requester_name?: string;
    erp_item_code?: string;
    unit_price?: number;
  }) => api.put(`procurement/lines/${line_id}`, data),

  push: (requisition_id: string, opts?: {
    push_url?: string;
    erp_type?: string;
    auth_header?: string;
  }) => api.post(`procurement/push/${requisition_id}`, opts ?? {}),

  exportUrl: (requisition_id: string, format: "json" | "csv") =>
    `/api/proxy/procurement/export/${requisition_id}?format=${format}`,
};
