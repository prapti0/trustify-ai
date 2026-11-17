export type EngineStatus = "ready" | "not_integrated";
export type ServiceState = "implemented" | "foundation" | "schema_only" | "not_started";

export interface RuntimeProbe {
  name: string;
  present: boolean;
}

export interface EngineCapability {
  id: string;
  name: string;
  status: EngineStatus;
  detail: string;
  runtime: RuntimeProbe[];
}

export interface ServiceCapability {
  id: string;
  name: string;
  phase: number;
  state: ServiceState;
  detail: string;
}

export interface PlatformStatus {
  name: string;
  version: string;
  phase: number;
  max_upload_bytes: number;
  auth_configured: boolean;
  storage_backend: string;
  guarantees: string[];
  services: ServiceCapability[];
  engines: EngineCapability[];
}

export interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  session_id: string;
  user: AuthUser;
}

export interface SessionInfo {
  id: string;
  created_at: string;
  expires_at: string;
  revoked_at: string | null;
  ip_address: string | null;
  user_agent: string | null;
  current: boolean;
}

export interface JobSummary {
  job_id: string;
  file_id: string;
  file_name: string;
  file_type: string;
  category: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  status: string;
  classification: string | null;
}

export interface CountPoint {
  label: string;
  count: number;
}

export interface DashboardData {
  total_files: number;
  ai_generated_indicators: number;
  suspicious_files: number;
  deepfake_indicators: number;
  security_threats: number;
  completed_investigations: number;
  notes: Record<string, string>;
  recent: JobSummary[];
  file_types: CountPoint[];
  risk_distribution: CountPoint[];
  detection_results: CountPoint[];
  activity: { date: string; count: number }[];
}

export interface Stage {
  id: string;
  label: string;
  state: string;
  detail: string;
}

export interface ModuleResult {
  module: string;
  status: string;
  finding_label: string | null;
  confidence: number | null;
  limitations: string;
  details: Record<string, unknown> | null;
}

export interface EvidenceItem {
  category: string;
  observation: string;
  severity: string;
  source_module: string;
}

export interface DuplicateMatch {
  file_id: string;
  file_name: string;
  matched_file_id: string;
  matched_file_name: string;
  match_kind: string;
  distance: number | null;
}

export interface FileMetadataView {
  container: string | null;
  codec: string | null;
  duration_seconds: number | null;
  width: number | null;
  height: number | null;
  exif: Record<string, unknown> | null;
  extra: Record<string, unknown> | null;
}

export interface Report {
  job_id: string;
  file_id: string;
  file_name: string;
  file_type: string;
  category: string;
  size_bytes: number;
  sha256: string;
  created_at: string;
  status: string;
  classification: string | null;
  summary: string | null;
  limitations: string;
  metadata: FileMetadataView | null;
  stages: Stage[];
  modules: ModuleResult[];
  evidence: EvidenceItem[];
  sections: Record<string, unknown>;
  duplicates: DuplicateMatch[];
  warnings: string[];
  unverified_claims: string[];
  recommended_steps: string[];
}

export interface ScamResult {
  status: string;
  summary: string;
  unverified_input: string;
  evidence: string[];
  risk_indicators: string[];
  recommended_steps: string[];
}
