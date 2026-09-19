import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, NavLink } from 'react-router-dom';
import { ArrowLeft, Sparkles, Radio, ShieldAlert, BookOpen, Clock, Activity, FileText } from 'lucide-react';
import { api } from '../services/api';
import { AlertResponse, IncidentInvestigationResponse, IncidentResponse } from '../types';
import { formatApiError } from '../utils/error';
import { RiskGauge } from '../components/RiskGauge';
import { ErrorBanner } from '../components/ErrorBanner';
import { Timeline, TimelineEvent } from '../components/Timeline';

export const IncidentDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [incident, setIncident] = useState<IncidentResponse | null>(null);
  const [alertsMap, setAlertsMap] = useState<AlertResponse[]>([]);
  const [investigationData, setInvestigationData] = useState<IncidentInvestigationResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [investigating, setInvestigating] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);
  const [investigationError, setInvestigationError] = useState<string | null>(null);

  const fetchIncidentData = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const [incData, allAlerts] = await Promise.all([
        api.getIncident(id, { lookback_minutes: 10080 }),
        api.getAlerts(),
      ]);
      setIncident(incData);

      // Match correlated alerts by ID
      const incAlertIds = new Set(incData.alert_ids);
      const matchedAlerts = allAlerts.filter((a) => incAlertIds.has(a.id));
      setAlertsMap(matchedAlerts);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Incident campaign not found.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidentData();
  }, [id]);

  const handleRunInvestigation = async () => {
    if (!id) return;
    setInvestigating(true);
    setInvestigationError(null);
    try {
      const res = await api.investigateIncident(id, { lookback_minutes: 10080, top_k: 5 });
      setInvestigationData(res);
    } catch (err: unknown) {
      setInvestigationError(formatApiError(err, 'AI Investigation synthesis service unavailable.'));
    } finally {
      setInvestigating(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400 text-xs font-mono">
        Loading correlated incident campaign from backend...
      </div>
    );
  }

  if (error || !incident) {
    return (
      <div className="space-y-4">
        <button onClick={() => navigate('/incidents')} className="flex items-center space-x-2 text-xs text-slate-400 hover:text-slate-200 font-mono">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Incidents Directory</span>
        </button>
        <ErrorBanner message={error || 'Incident campaign not found.'} />
      </div>
    );
  }

  const investigation = investigationData?.investigation;
  const sources = investigationData?.sources || [];

  // Build timeline events from real alert data
  const timelineEvents: TimelineEvent[] = alertsMap.map((a) => ({
    id: a.id,
    timestamp: a.timestamp,
    attack_type: a.attack_type,
    severity: a.severity,
    status: a.status,
    source_ip: a.source_ip,
    destination_ip: a.destination_ip,
    destination_port: a.destination_port,
  }));

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between">
        <button
          onClick={() => navigate('/incidents')}
          className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Incidents Directory</span>
        </button>
        <span className="text-slate-500">Incident UUID: {incident.incident_id}</span>
      </div>

      {/* SECTION 1: INCIDENT SUMMARY */}
      <div className="soc-card p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <Radio className="w-6 h-6 text-cyan-400" />
              <h1 className="text-xl font-bold text-slate-100">
                Correlated Incident Workspace
              </h1>
            </div>
            <p className="text-slate-400">
              Active Time Window: {new Date(incident.first_seen).toLocaleString()} &rarr; {new Date(incident.last_seen).toLocaleString()}
            </p>
          </div>

          <div className="flex items-center space-x-4">
            <RiskGauge score={incident.risk_score} />
            <button
              onClick={handleRunInvestigation}
              disabled={investigating}
              className="flex items-center space-x-2 px-4 py-2.5 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-semibold text-xs rounded-lg shadow-lg transition disabled:opacity-50"
            >
              <Sparkles className={`w-4 h-4 ${investigating ? 'animate-spin' : ''}`} />
              <span>{investigating ? 'Synthesizing RAG AI Report...' : 'AI Investigation'}</span>
            </button>
          </div>
        </div>

        {/* Campaign Metrics */}
        <div className="grid grid-cols-1 sm:grid-cols-4 gap-4 pt-2">
          <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500 uppercase">Correlated Alerts</span>
            <p className="text-slate-100 font-bold text-base mt-1">{incident.alert_count} Alerts</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500 uppercase">Distinct Attack Types</span>
            <p className="text-slate-100 font-bold text-xs mt-1 truncate">{incident.attack_types.join(', ') || 'N/A'}</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500 uppercase">Source IPs</span>
            <p className="text-slate-100 font-bold text-xs mt-1 truncate">{incident.source_ips.join(', ') || 'N/A'}</p>
          </div>
          <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500 uppercase">Target Destination IPs</span>
            <p className="text-slate-100 font-bold text-xs mt-1 truncate">{incident.destination_ips.join(', ') || 'N/A'}</p>
          </div>
        </div>
      </div>

      {/* SECTION 2: RISK ASSESSMENT */}
      <div className="soc-card p-6 border border-slate-800 space-y-3">
        <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
          <ShieldAlert className="w-5 h-5 text-rose-400" />
          <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
            Deterministic Risk Assessment (0–100 Security Rules)
          </h3>
        </div>

        <div className="bg-slate-900/40 p-4 rounded-lg border border-slate-800 space-y-2">
          <span className="text-slate-400 font-semibold uppercase block">Risk Score Breakdown:</span>
          <div className="flex flex-wrap gap-2">
            {incident.risk_factors.map((factor, idx) => (
              <span key={idx} className="px-2.5 py-1 bg-slate-800 text-slate-300 rounded border border-slate-700">
                • {factor}
              </span>
            ))}
          </div>
        </div>
      </div>

      {/* SECTION 3: CORRELATED ALERTS & SECTION 4: TIMELINE */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Correlated Alerts List */}
        <div className="soc-card p-5 border border-slate-800 space-y-4">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 border-b border-slate-800 pb-3">
            Correlated Alert Cluster ({incident.alert_ids.length})
          </h3>
          <div className="space-y-2 max-h-96 overflow-y-auto pr-1">
            {incident.alert_ids.map((alertId, idx) => (
              <div key={alertId} className="p-3 bg-slate-900/60 rounded-lg border border-slate-800 flex items-center justify-between">
                <div>
                  <span className="text-slate-400 font-bold">Alert #{idx + 1}</span>
                  <p className="text-slate-500 text-[10px]">{alertId}</p>
                </div>
                <NavLink
                  to={`/alerts/${alertId}`}
                  className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 rounded text-[11px]"
                >
                  Inspect
                </NavLink>
              </div>
            ))}
          </div>
        </div>

        {/* Real Timestamps Timeline */}
        <div className="soc-card p-5 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <Clock className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Chronological Alert Sequence (Real Timestamps)
            </h3>
          </div>
          <Timeline events={timelineEvents} />
        </div>
      </div>

      {/* SECTION 5: AI INVESTIGATION & SECTION 6: SOURCES */}
      {investigationError && <ErrorBanner message={investigationError} />}

      {investigation && (
        <div className="soc-card p-6 border border-cyan-500/30 bg-cyan-950/10 space-y-6">
          <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
            <div className="flex items-center space-x-2">
              <Sparkles className="w-5 h-5 text-cyan-400" />
              <h3 className="text-base font-bold text-cyan-200">Grounded AI SOC Investigation Report</h3>
            </div>
            <span className="px-2.5 py-1 bg-cyan-500/20 text-cyan-300 rounded border border-cyan-500/40 font-bold text-[10px]">
              Stage 8 Synthesized
            </span>
          </div>

          <div className="space-y-5">
            {/* Executive Summary */}
            <div>
              <h4 className="text-cyan-300 font-bold uppercase mb-1">Executive Summary</h4>
              <p className="text-slate-200 leading-relaxed bg-slate-900/90 p-4 rounded-lg border border-slate-800">
                {investigation.executive_summary}
              </p>
            </div>

            {/* Observed Evidence vs AI Analysis */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">Observed Evidence (Facts)</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.observed_evidence.map((ev, i) => (
                    <li key={i}>{ev}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">Threat Context (RAG Synthesis)</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.threat_context.map((ctx, i) => (
                    <li key={i}>{ctx}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Recommended Steps */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">Investigation Priorities</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.investigation_priorities.map((prio, i) => (
                    <li key={i}>{prio}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">Recommended Containment Actions</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.recommended_actions.map((act, i) => (
                    <li key={i}>{act}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Mitigations & MITRE */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">System Mitigations</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.mitigations.map((mit, i) => (
                    <li key={i}>{mit}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-cyan-300 font-bold uppercase mb-1">Explicit MITRE ATT&CK Context</h4>
                <ul className="list-disc list-inside space-y-1.5 bg-slate-900/90 p-4 rounded-lg border border-slate-800 text-slate-300">
                  {investigation.mitre_context.length === 0 ? (
                    <li className="text-slate-500">None explicitly present in retrieved context</li>
                  ) : (
                    investigation.mitre_context.map((m, i) => (
                      <li key={i} className="text-cyan-300 font-semibold">{m}</li>
                    ))
                  )}
                </ul>
              </div>
            </div>

            {/* Limitations & Boundaries */}
            <div>
              <h4 className="text-cyan-300 font-bold uppercase mb-1">Analytical Boundaries & Limitations</h4>
              <ul className="list-disc list-inside space-y-1 bg-slate-900/90 p-3 rounded-lg border border-slate-800 text-slate-400 text-[11px]">
                {investigation.limitations.map((lim, i) => (
                  <li key={i}>{lim}</li>
                ))}
              </ul>
            </div>

            {/* Cited Knowledge Sources */}
            <div>
              <div className="flex items-center space-x-2 text-cyan-300 font-bold uppercase mb-2">
                <BookOpen className="w-4 h-4" />
                <span>Cited Knowledge Base Sources ({sources.length})</span>
              </div>
              <div className="space-y-2">
                {sources.map((src, i) => (
                  <div key={i} className="p-3.5 bg-slate-900/90 rounded-lg border border-slate-800 flex items-center justify-between text-[11px]">
                    <div>
                      <p className="text-slate-200 font-semibold">{src.title || src.file_name}</p>
                      <p className="text-slate-500">Source Path: {src.source}</p>
                      <p className="text-slate-500 text-[10px]">Document ID: {src.document_id} • Chunk #{src.chunk_index}</p>
                    </div>
                    <span className="px-2.5 py-1 bg-cyan-500/10 text-cyan-400 rounded-md border border-cyan-500/30 font-bold">
                      {(src.score * 100).toFixed(1)}% Match
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
