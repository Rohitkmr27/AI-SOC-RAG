import axios from 'axios';
import {
  AlertEnrichmentResponse,
  AlertResponse,
  AlertSeverity,
  AlertStatus,
  AlertUpdate,
  CorrelationResponse,
  CsvAlertResponse,
  HealthResponse,
  IncidentInvestigationResponse,
  IncidentResponse,
  LoginRequest,
  RAGQueryRequest,
  RAGQueryResponse,
  TokenResponse,
  UserResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';
const TOKEN_KEY = 'aisoc_token';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// Request Interceptor: Attach JWT Bearer Token if available
apiClient.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response Interceptor: Handle HTTP 401 Unauthorized globally
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response && error.response.status === 401) {
      // Clear token and notify app to redirect to login
      localStorage.removeItem(TOKEN_KEY);
      window.dispatchEvent(new Event('aisoc_auth_expired'));
    }
    return Promise.reject(error);
  }
);

export const api = {
  // Authentication & User Identity
  async login(credentials: LoginRequest): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', credentials);
    if (response.data.access_token) {
      localStorage.setItem(TOKEN_KEY, response.data.access_token);
    }
    return response.data;
  },

  async getCurrentUser(): Promise<UserResponse> {
    const response = await apiClient.get<UserResponse>('/auth/me');
    return response.data;
  },

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    window.dispatchEvent(new Event('aisoc_logout'));
  },

  getToken(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  },

  // System Health
  async getHealth(): Promise<HealthResponse> {
    try {
      const response = await apiClient.get<HealthResponse>('/api/v1/system-status');
      return response.data;
    } catch (err: any) {
      // If blocked by adblock or /api/v1/system-status unavailable, attempt /health
      if (err?.code === 'ERR_BLOCKED_BY_CLIENT') {
        throw err;
      }
      const response = await apiClient.get<HealthResponse>('/health');
      return response.data;
    }
  },

  // Alert Management
  async getAlerts(params?: {
    severity?: AlertSeverity;
    status?: AlertStatus;
    attack_type?: string;
  }): Promise<AlertResponse[]> {
    const response = await apiClient.get<AlertResponse[]>('/alerts', { params });
    return response.data;
  },

  async seedAlerts(): Promise<AlertResponse[]> {
    const response = await apiClient.post<AlertResponse[]>('/alerts/seed');
    return response.data;
  },

  async getAlert(alertId: string): Promise<AlertResponse> {
    const response = await apiClient.get<AlertResponse>(`/alerts/${alertId}`);
    return response.data;
  },

  async updateAlert(alertId: string, payload: AlertUpdate): Promise<AlertResponse> {
    const response = await apiClient.patch<AlertResponse>(`/alerts/${alertId}`, payload);
    return response.data;
  },

  async enrichAlert(alertId: string): Promise<AlertEnrichmentResponse> {
    const response = await apiClient.post<AlertEnrichmentResponse>(`/alerts/${alertId}/enrich`);
    return response.data;
  },

  // Alert Correlations & Incidents
  async getCorrelations(params?: {
    lookback_minutes?: number;
    correlation_window_minutes?: number;
    source_ip?: string;
    minimum_risk_score?: number;
  }): Promise<CorrelationResponse> {
    const response = await apiClient.get<CorrelationResponse>('/alerts/correlations', { params });
    return response.data;
  },

  async getIncident(
    incidentId: string,
    params?: { lookback_minutes?: number; correlation_window_minutes?: number }
  ): Promise<IncidentResponse> {
    const response = await apiClient.get<IncidentResponse>(`/alerts/correlations/${incidentId}`, { params });
    return response.data;
  },

  async investigateIncident(
    incidentId: string,
    params?: { lookback_minutes?: number; correlation_window_minutes?: number; top_k?: number }
  ): Promise<IncidentInvestigationResponse> {
    const response = await apiClient.post<IncidentInvestigationResponse>(
      `/alerts/correlations/${incidentId}/investigate`,
      null,
      { params }
    );
    return response.data;
  },

  // RAG Knowledge Base Search
  async queryRAG(payload: RAGQueryRequest): Promise<RAGQueryResponse> {
    const response = await apiClient.post<RAGQueryResponse>('/rag/query', payload);
    return response.data;
  },

  // IDS Batch Flow Detection & Alert Persistence
  async uploadCsvForAlerts(file: File): Promise<CsvAlertResponse> {
    const formData = new FormData();
    formData.append('file', file);
    const response = await apiClient.post<CsvAlertResponse>('/alerts/from-csv', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },
};

