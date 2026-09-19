import axios from 'axios';
import {
  AlertEnrichmentResponse,
  AlertResponse,
  AlertSeverity,
  AlertStatus,
  AlertUpdate,
  CorrelationResponse,
  HealthResponse,
  IncidentInvestigationResponse,
  IncidentResponse,
  RAGQueryRequest,
  RAGQueryResponse,
} from '../types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

export const api = {
  // System Health
  async getHealth(): Promise<HealthResponse> {
    const response = await apiClient.get<HealthResponse>('/health');
    return response.data;
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
};
