import axios from "axios";
import { currentSessionId, currentToken } from "../context/AuthContext";
import type {
  AuthResponse,
  AuthUser,
  DashboardData,
  DuplicateMatch,
  JobSummary,
  PlatformStatus,
  Report,
  ScamResult,
  SessionInfo,
} from "./types";

const http = axios.create({ baseURL: import.meta.env.VITE_API_BASE_URL ?? "" });

http.interceptors.request.use((config) => {
  const token = currentToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const hadToken = Boolean(error.config?.headers?.Authorization);
    if (hadToken && error.response?.status === 401 && !window.location.pathname.startsWith("/login")) {
      localStorage.removeItem("trustify.session");
      window.location.assign("/login");
    }
    return Promise.reject(error);
  },
);

export function errorMessage(error: unknown, fallback: string) {
  if (axios.isAxiosError(error)) {
    if (!error.response) {
      return "Cannot reach the TRUSTIFY API. Use http://127.0.0.1:5175 with the API running.";
    }
    const detail = error.response.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (detail && typeof detail === "object" && "message" in detail && typeof detail.message === "string") {
      return detail.message;
    }
    if (Array.isArray(detail) && detail[0]?.msg) {
      return String(detail[0].msg);
    }
    if (error.response.status === 403 || error.response.status === 404) {
      return "The API did not accept this request. Confirm you are on the TRUSTIFY UI and the API proxy target is correct.";
    }
  }
  return fallback;
}

export async function getPlatform() {
  const response = await http.get<PlatformStatus>("/api/v1/platform");
  return response.data;
}

export async function registerAccount(body: { full_name: string; email: string; password: string; accepted_terms: boolean }) {
  const response = await http.post<AuthResponse>("/api/v1/auth/register", body);
  return response.data;
}

export async function loginAccount(body: { email: string; password: string }) {
  const response = await http.post<AuthResponse>("/api/v1/auth/login", body);
  return response.data;
}

export async function logoutAccount() {
  const sessionId = currentSessionId();
  if (!sessionId) return;
  await http.post("/api/v1/auth/logout", null, { params: { session_id: sessionId } });
}

export async function googleSignIn() {
  await http.post("/api/v1/auth/google");
}

export async function forgotPassword(email: string) {
  await http.post("/api/v1/auth/forgot-password", { email });
}

export async function updateProfile(body: { full_name: string; email: string }) {
  const response = await http.patch<AuthUser>("/api/v1/auth/me", body);
  return response.data;
}

export async function changePassword(body: { current_password: string; new_password: string }) {
  await http.post("/api/v1/auth/password", body);
}

export async function listSessions() {
  const response = await http.get<SessionInfo[]>("/api/v1/auth/sessions", {
    params: { current_session: currentSessionId() },
  });
  return response.data;
}

export async function revokeSession(sessionId: string) {
  await http.delete(`/api/v1/auth/sessions/${sessionId}`);
}

export async function deleteAllFiles() {
  await http.delete("/api/v1/account/files");
}

export async function deleteAccount() {
  await http.delete("/api/v1/account");
}

export async function getDashboard() {
  const response = await http.get<DashboardData>("/api/v1/dashboard");
  return response.data;
}

export async function listJobs() {
  const response = await http.get<JobSummary[]>("/api/v1/jobs");
  return response.data;
}

export async function getJob(jobId: string) {
  const response = await http.get<Report>(`/api/v1/jobs/${jobId}`);
  return response.data;
}

export async function uploadFile(file: File, onProgress: (fraction: number) => void) {
  const form = new FormData();
  form.append("file", file);
  const response = await http.post<Report>("/api/v1/files", form, {
    onUploadProgress: (event) => {
      if (event.total) onProgress(event.loaded / event.total);
    },
  });
  return response.data;
}

export async function submitUrl(url: string) {
  const response = await http.post<Report>("/api/v1/urls", { url });
  return response.data;
}

export async function deleteJob(jobId: string) {
  await http.delete(`/api/v1/jobs/${jobId}`);
}

export async function downloadReportPdf(jobId: string) {
  await http.get(`/api/v1/reports/${jobId}/pdf`);
}

export async function getFileBlob(fileId: string) {
  const response = await http.get<Blob>(`/api/v1/files/${fileId}/content`, { responseType: "blob" });
  return response.data;
}

export async function listDuplicates() {
  const response = await http.get<DuplicateMatch[]>("/api/v1/duplicates");
  return response.data;
}

export async function submitScam(kind: "media" | "url" | "message" | "claim", content: string) {
  const response = await http.post<ScamResult>("/api/v1/investigations/scam", { kind, content });
  return response.data;
}
