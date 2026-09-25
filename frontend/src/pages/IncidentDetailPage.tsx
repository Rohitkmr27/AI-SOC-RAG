import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, NavLink } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Radio,
  ShieldAlert,
  BookOpen,
  Clock,
  Activity,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  ListChecks,
  Shield,
  FileText,
  ExternalLink,
} from 'lucide-react';
import { api } from '../services/api';
import { AlertResponse, IncidentInvestigationResponse, IncidentResponse } from '../types';
import { formatApiError } from '../utils/error';
import { RiskGauge } from '../components/RiskGauge';
import { ErrorBanner } from '../components/ErrorBanner';
import { Timeline, TimelineEvent } from '../components/Timeline';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';

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
      setInvestigationError(
        formatApiError(err, 'AI incident investigation is temporarily unavailable. The deterministic incident details remain fully operational.')
      );
    } finally {
      setInvestigating(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400 text-xs font-mono">
        Loading correlated incident campaign from SQL backend...
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
    <div className="space-y-6 font-mono text-xs max-w-7xl mx-auto pb-12">
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
              className={`flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition-all shadow-lg ${
                investigating
                  ? 'bg-cyan-950/50 text-cyan-300 border border-cyan-500/30 cursor-not-allowed'
                  : 'bg-cyan-600 hover:bg-cyan-500 text-white border border-cyan-400 shadow-cyan-500/20 active:scale-95'
              }`}
            >
              {investigating ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-cyan-300" />
                  <span>Retrieving Knowledge & Generating AI Report...</span>
                </>
              ) : (
                <>
                  <Sparkles className="w-4 h-4 text-cyan-300 fill-current" />
                  <span>Investigate Incident</span>
                </>
              )}
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

      {/* SECTION 2: DETERMINISTIC RISK ASSESSMENT */}
      <div className="soc-card p-6 border border-slate-800 space-y-3">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center space-x-2">
            <ShieldAlert className="w-5 h-5 text-rose-400" />
            <h3 className="text-sm font-bold uppercase tracking-wider text-slate-200">
              Deterministic Risk Assessment (Backend Rule Engine)
            </h3>
          </div>
          <span className="text-[11px] text-slate-400 font-mono">
            Score: <strong className="text-slate-100">{incident.risk_score} / 100</strong>
          </span>
        </div>

        <div className="bg-slate-900/40 p-4 rounded-lg border border-slate-800 space-y-2">
          <span className="text-slate-400 font-semibold uppercase block">Correlation Rule Engine Risk Factors:</span>
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
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
              Correlated Alert Cluster ({incident.alert_ids.length})
            </h3>
            <span className="text-[10px] text-slate-500">Click alert to inspect details</span>
          </div>

          <div className="space-y-2.5 max-h-96 overflow-y-auto pr-1">
            {alertsMap.length > 0 ? (
              alertsMap.map((alert, idx) => (
                <div key={alert.id} className="p-3 bg-slate-900/80 rounded-xl border border-slate-800 flex items-center justify-between hover:border-slate-700 transition">
                  <div className="space-y-1">
                    <div className="flex items-center space-x-2">
                      <span className="font-bold text-slate-200">#{idx + 1} {alert.attack_type}</span>
                      <SeverityBadge severity={alert.severity} />
                      <StatusBadge status={alert.status} />
                    </div>
                    <p className="text-[10px] text-slate-400">
                      {alert.source_ip}:{alert.source_port} &rarr; {alert.destination_ip}:{alert.destination_port} ({alert.protocol})
                    </p>
                  </div>

                  <NavLink
                    to={`/alerts/${alert.id}`}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-cyan-500/10 text-cyan-400 hover:text-cyan-300 border border-slate-700 hover:border-cyan-500/30 rounded-lg text-xs font-bold transition flex items-center space-x-1"
                  >
                    <span>Inspect</span>
                    <ExternalLink className="w-3 h-3" />
                  </NavLink>
                </div>
              ))
            ) : (
              incident.alert_ids.map((alertId, idx) => (
                <div key={alertId} className="p-3 bg-slate-900/60 rounded-xl border border-slate-800 flex items-center justify-between">
                  <div>
                    <span className="text-slate-400 font-bold">Alert #{idx + 1}</span>
                    <p className="text-slate-500 text-[10px]">{alertId}</p>
                  </div>
                  <NavLink
                    to={`/alerts/${alertId}`}
                    className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-cyan-400 border border-slate-700 rounded-lg text-xs font-bold transition flex items-center space-x-1"
                  >
                    <span>Inspect</span>
                    <ExternalLink className="w-3 h-3" />
                  </NavLink>
                </div>
              ))
            )}
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

      {/* SECTION 5: AI INVESTIGATION ERROR BANNER */}
      {investigationError && (
        <div className="bg-rose-500/10 border border-rose-500/30 p-4 rounded-xl flex items-start justify-between space-x-3 text-xs font-mono text-rose-300">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold">AI Incident Investigation Unavailable</p>
              <p className="text-rose-200/80">{investigationError}</p>
            </div>
          </div>

          <button
            onClick={handleRunInvestigation}
            disabled={investigating}
            className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 rounded border border-rose-500/40 text-[11px] font-bold transition flex-shrink-0"
          >
            Retry AI Investigation
          </button>
        </div>
      )}

      {/* SECTION 6: STRUCTURED RAG AI INCIDENT INVESTIGATION REPORT */}
      {investigation && (
        <div className="soc-card p-6 border border-cyan-500/40 bg-cyan-950/10 space-y-6 shadow-2xl">
          {/* Section Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-cyan-500/20 pb-4">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-cyan-500/20 rounded-lg text-cyan-300 border border-cyan-500/30">
                <Sparkles className="w-5 h-5 fill-current" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">Grounded AI Incident Investigation Report</h3>
                <p className="text-[11px] text-cyan-300/80">Grounded in retrieved cybersecurity knowledge (SQLite FTS5 + Gemini)</p>
              </div>
            </div>

            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold bg-cyan-500/15 text-cyan-300 border border-cyan-500/30 w-fit">
              Analyst Investigation Support
            </span>
          </div>

          <div className="space-y-5">
            {/* Executive Summary */}
            <div className="space-y-1.5">
              <h4 className="text-cyan-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-cyan-400" />
                <span>Executive Summary</span>
              </h4>
              <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800 text-slate-200 leading-relaxed">
                {investigation.executive_summary}
              </div>
            </div>

            {/* Observed Evidence vs Threat Context */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 text-cyan-400" />
                  <span>Observed Evidence (Raw Facts)</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {investigation.observed_evidence.map((ev, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-cyan-400 font-bold">•</span>
                        <span>{ev}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-cyan-400" />
                  <span>Threat Context (RAG Synthesis)</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {investigation.threat_context.map((ctx, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-cyan-400 font-bold">•</span>
                        <span>{ctx}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Investigation Priorities & Recommended Actions */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <ListChecks className="w-4 h-4 text-cyan-400" />
                  <span>Investigation Priorities</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ol className="space-y-2 text-slate-300">
                    {investigation.investigation_priorities.map((prio, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-cyan-400 font-bold">{i + 1}.</span>
                        <span>{prio}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <Shield className="w-4 h-4 text-cyan-400" />
                  <span>Recommended Containment Actions</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {investigation.recommended_actions.map((act, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-emerald-400 font-bold">✓</span>
                        <span>{act}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* System Mitigations & MITRE ATT&CK */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider">System Mitigations</h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {investigation.mitigations.map((mit, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-cyan-400 font-bold">•</span>
                        <span>{mit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              <div className="space-y-1.5">
                <h4 className="text-cyan-300 font-bold uppercase tracking-wider">Explicit MITRE ATT&CK Context</h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {investigation.mitre_context.length === 0 ? (
                      <li className="text-slate-500 italic">None explicitly present in retrieved context</li>
                    ) : (
                      investigation.mitre_context.map((m, i) => (
                        <li key={i} className="flex items-start space-x-2">
                          <span className="text-cyan-400 font-bold">•</span>
                          <span className="text-cyan-300 font-semibold">{m}</span>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            </div>

            {/* Boundaries & Limitations */}
            <div className="space-y-1.5">
              <h4 className="text-cyan-300 font-bold uppercase tracking-wider">Analytical Boundaries & Limitations</h4>
              <div className="bg-slate-900/90 p-3.5 rounded-xl border border-slate-800 text-slate-400 text-[11px]">
                <ul className="space-y-1">
                  {investigation.limitations.map((lim, i) => (
                    <li key={i} className="flex items-start space-x-2">
                      <span className="text-slate-500">•</span>
                      <span>{lim}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Cited Knowledge Base Sources */}
            <div className="space-y-2 pt-2 border-t border-cyan-500/20">
              <div className="flex items-center space-x-2 text-cyan-300 font-bold uppercase">
                <BookOpen className="w-4 h-4 text-cyan-400" />
                <span>Cited Cybersecurity Knowledge Sources ({sources.length})</span>
              </div>

              <div className="space-y-2">
                {sources.length === 0 ? (
                  <p className="text-slate-500 text-xs italic">No specific sources cited for this response.</p>
                ) : (
                  sources.map((src, i) => (
                    <div key={i} className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
                      <div>
                        <p className="text-slate-100 font-bold">{src.title || src.file_name}</p>
                        <p className="text-slate-400 font-mono text-[10px]">Source Reference: {src.source}</p>
                        <p className="text-slate-500 text-[10px]">Document ID: {src.document_id} • Chunk #{src.chunk_index}</p>
                      </div>
                      <span className="px-2.5 py-1 bg-cyan-500/15 text-cyan-300 rounded-lg border border-cyan-500/30 font-mono font-bold w-fit">
                        {(src.score * 100).toFixed(1)}% Relevance Score
                      </span>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default IncidentDetailPage;
