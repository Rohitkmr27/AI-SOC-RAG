export type UserRole = 'ANALYST' | 'ADMIN';

export interface UserResponse {
  id: string;
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export type AlertSeverity = 'Informational' | 'Low' | 'Medium' | 'High' | 'Critical';
export type AlertStatus = 'NEW' | 'TRIAGED' | 'INVESTIGATING' | 'RESOLVED';

export interface AlertResponse {
  id: string;
  timestamp: string;
  source_ip: string;
  destination_ip: string;
  source_port: number;
  destination_port: number;
  protocol: string;
  attack_type: string;
  confidence: number;
  severity: AlertSeverity;
  status: AlertStatus;
  description: string;
  created_at: string;
  updated_at: string;
}

export interface AlertCreate {
  timestamp: string;
  source_ip: string;
  destination_ip: string;
  source_port: number;
  destination_port: number;
  protocol: string;
  attack_type: string;
  confidence: number;
  severity: AlertSeverity;
  status?: AlertStatus;
  description: string;
}

export interface AlertUpdate {
  status?: AlertStatus;
  severity?: AlertSeverity;
  description?: string;
}

export interface IncidentResponse {
  incident_id: string;
  alert_count: number;
  first_seen: string;
  last_seen: string;
  source_ips: string[];
  destination_ips: string[];
  attack_types: string[];
  risk_score: number;
  risk_factors: string[];
  alert_ids: string[];
}

export interface CorrelationResponse {
  incidents: IncidentResponse[];
  total_incidents: number;
  total_correlated_alerts: number;
  lookback_minutes: number;
  correlation_window_minutes: number;
}

export interface IncidentInvestigation {
  executive_summary: string;
  observed_evidence: string[];
  threat_context: string[];
  investigation_priorities: string[];
  recommended_actions: string[];
  mitigations: string[];
  mitre_context: string[];
  limitations: string[];
}

export interface RAGSource {
  source: string;
  file_name: string;
  document_id: string;
  chunk_id: string;
  chunk_index: number;
  score: number;
  title: string | null;
}

export interface IncidentInvestigationResponse {
  incident: IncidentResponse;
  investigation: IncidentInvestigation;
  sources: RAGSource[];
}

export interface AlertAnalysis {
  summary: string;
  observed_indicators: string[];
  security_context: string[];
  investigation_steps: string[];
  recommended_mitigations: string[];
}

export interface AlertEnrichmentResponse {
  alert: AlertResponse;
  analysis: AlertAnalysis;
  sources: RAGSource[];
}

export interface RAGQueryRequest {
  query: string;
  top_k?: number;
  score_threshold?: number;
  max_context_chars?: number;
  model?: string;
}

export interface RAGQueryResponse {
  answer: string;
  sources: RAGSource[];
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface IdsPredictionRequest {
  features: Record<string, number | string | boolean>;
}

export interface IdsPredictionResponse {
  prediction: string;
  confidence: number;
  severity: AlertSeverity;
}
