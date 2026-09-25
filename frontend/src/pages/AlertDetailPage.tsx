import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  ArrowLeft,
  Sparkles,
  Shield,
  Network,
  Cpu,
  Workflow,
  BookOpen,
  AlertTriangle,
  RefreshCw,
  CheckCircle2,
  ListChecks,
  ShieldAlert,
} from 'lucide-react';
import { api } from '../services/api';
import { AlertEnrichmentResponse, AlertResponse, AlertSeverity, AlertStatus } from '../types';
import { formatApiError } from '../utils/error';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { ErrorBanner } from '../components/ErrorBanner';
import { Modal } from '../components/Modal';

export const AlertDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const [alert, setAlert] = useState<AlertResponse | null>(null);
  const [enrichment, setEnrichment] = useState<AlertEnrichmentResponse | null>(null);

  const [loading, setLoading] = useState<boolean>(true);
  const [updating, setUpdating] = useState<boolean>(false);
  const [enriching, setEnriching] = useState<boolean>(false);

  const [error, setError] = useState<string | null>(null);
  const [enrichError, setEnrichError] = useState<string | null>(null);

  // Form states for PATCH
  const [newStatus, setNewStatus] = useState<AlertStatus>('NEW');
  const [newSeverity, setNewSeverity] = useState<AlertSeverity>('Medium');
  const [newDescription, setNewDescription] = useState<string>('');

  // Confirmation Modal
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);

  const fetchAlert = async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAlert(id);
      setAlert(data);
      setNewStatus(data.status);
      setNewSeverity(data.severity);
      setNewDescription(data.description);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Alert record not found in database.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlert();
  }, [id]);

  const handleConfirmUpdate = async () => {
    if (!id || !alert) return;
    setUpdating(true);
    setError(null);
    try {
      const updated = await api.updateAlert(id, {
        status: newStatus,
        severity: newSeverity,
        description: newDescription,
      });
      setAlert(updated);
      setShowConfirmModal(false);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to update alert status.'));
    } finally {
      setUpdating(false);
    }
  };

  const handleEnrichAlert = async () => {
    if (!id) return;
    setEnriching(true);
    setEnrichError(null);
    try {
      const res = await api.enrichAlert(id);
      setEnrichment(res);
    } catch (err: unknown) {
      setEnrichError(
        formatApiError(err, 'AI enrichment is temporarily unavailable. The original alert record remains fully operational.')
      );
    } finally {
      setEnriching(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400 text-xs font-mono">
        Loading alert metadata from SQL database...
      </div>
    );
  }

  if (error || !alert) {
    return (
      <div className="space-y-4">
        <button onClick={() => navigate('/alerts')} className="flex items-center space-x-2 text-xs text-slate-400 hover:text-slate-200 font-mono">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Alerts Directory</span>
        </button>
        <ErrorBanner message={error || 'Alert not found.'} />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between font-mono text-xs">
        <button
          onClick={() => navigate('/alerts')}
          className="flex items-center space-x-2 text-slate-400 hover:text-slate-200 transition"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Alerts Directory</span>
        </button>
        <span className="text-slate-500">Alert UUID: {alert.id}</span>
      </div>

      {/* Confirmation Modal */}
      <Modal
        isOpen={showConfirmModal}
        title="Confirm Workflow Status Update"
        description={`Are you sure you want to update alert "${alert.attack_type}" status to "${newStatus}" and severity to "${newSeverity}"?`}
        confirmLabel="Update Alert"
        onConfirm={handleConfirmUpdate}
        onClose={() => setShowConfirmModal(false)}
        loading={updating}
      />

      {/* Section 1: ALERT OVERVIEW */}
      <div className="soc-card p-6 border border-slate-800 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800 pb-4">
          <div>
            <div className="flex items-center space-x-3 mb-1">
              <Shield className="w-6 h-6 text-cyan-400" />
              <h1 className="text-xl font-bold text-slate-100 font-mono">{alert.attack_type}</h1>
              <SeverityBadge severity={alert.severity} />
              <StatusBadge status={alert.status} />
            </div>
            <p className="text-xs text-slate-400 font-mono">
              Detected at {new Date(alert.timestamp).toLocaleString()}
            </p>
          </div>

          <button
            onClick={handleEnrichAlert}
            disabled={enriching}
            className={`flex items-center justify-center space-x-2 px-5 py-2.5 rounded-xl font-mono text-xs font-bold transition-all shadow-lg ${
              enriching
                ? 'bg-purple-950/50 text-purple-300 border border-purple-500/30 cursor-not-allowed'
                : 'bg-purple-600 hover:bg-purple-500 text-white border border-purple-400 shadow-purple-500/20 active:scale-95'
            }`}
          >
            {enriching ? (
              <>
                <RefreshCw className="w-4 h-4 animate-spin text-purple-300" />
                <span>Retrieving Knowledge & Generating AI Analysis...</span>
              </>
            ) : (
              <>
                <Sparkles className="w-4 h-4 text-purple-300 fill-current" />
                <span>AI Enrich Alert</span>
              </>
            )}
          </button>
        </div>

        {/* Section 2: NETWORK DETAILS */}
        <div className="space-y-2 font-mono text-xs">
          <div className="flex items-center space-x-2 text-slate-300 font-bold uppercase mb-2">
            <Network className="w-4 h-4 text-cyan-400" />
            <span>Network Flow Metadata</span>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 uppercase">Source Endpoint</span>
              <p className="text-slate-100 font-bold text-sm mt-1">{alert.source_ip}:{alert.source_port}</p>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 uppercase">Destination Endpoint</span>
              <p className="text-slate-100 font-bold text-sm mt-1">{alert.destination_ip}:{alert.destination_port}</p>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 uppercase">Transport Protocol</span>
              <p className="text-slate-100 font-bold text-sm mt-1">{alert.protocol}</p>
            </div>
            <div className="bg-slate-900/80 p-3 rounded-lg border border-slate-800">
              <span className="text-slate-500 uppercase">Detection Confidence</span>
              <p className="text-slate-100 font-bold text-sm mt-1">{(alert.confidence * 100).toFixed(1)}%</p>
            </div>
          </div>
        </div>

        {/* Section 3: DETECTION DESCRIPTION */}
        <div className="space-y-2 font-mono text-xs pt-2">
          <div className="flex items-center space-x-2 text-slate-300 font-bold uppercase">
            <Cpu className="w-4 h-4 text-cyan-400" />
            <span>Detection Description</span>
          </div>
          <div className="bg-slate-900/40 p-3.5 rounded-lg border border-slate-800 text-slate-300 leading-relaxed">
            {alert.description}
          </div>
        </div>
      </div>

      {/* Section 4: WORKFLOW & STATUS PATCH */}
      <div className="soc-card p-6 border border-slate-800 space-y-4">
        <div className="flex items-center space-x-2 border-b border-slate-800 pb-3 font-mono">
          <Workflow className="w-4 h-4 text-cyan-400" />
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200">
            Analyst Workflow & Status Control
          </h3>
        </div>

        <form
          onSubmit={(e) => {
            e.preventDefault();
            setShowConfirmModal(true);
          }}
          className="space-y-4 font-mono text-xs"
        >
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-slate-400 mb-1">Workflow Status</label>
              <select
                value={newStatus}
                onChange={(e) => setNewStatus(e.target.value as AlertStatus)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg p-2.5 focus:outline-none focus:border-cyan-500 font-mono"
              >
                <option value="NEW">NEW</option>
                <option value="TRIAGED">TRIAGED</option>
                <option value="INVESTIGATING">INVESTIGATING</option>
                <option value="RESOLVED">RESOLVED</option>
              </select>
            </div>

            <div>
              <label className="block text-slate-400 mb-1">Triage Severity Override</label>
              <select
                value={newSeverity}
                onChange={(e) => setNewSeverity(e.target.value as AlertSeverity)}
                className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg p-2.5 focus:outline-none focus:border-cyan-500 font-mono"
              >
                <option value="Informational">Informational</option>
                <option value="Low">Low</option>
                <option value="Medium">Medium</option>
                <option value="High">High</option>
                <option value="Critical">Critical</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-slate-400 mb-1">Analyst Notes / Description</label>
            <textarea
              rows={3}
              value={newDescription}
              onChange={(e) => setNewDescription(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700 text-slate-200 rounded-lg p-2.5 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>

          <div className="flex justify-end">
            <button
              type="submit"
              disabled={updating}
              className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-lg shadow transition disabled:opacity-50"
            >
              Update Alert Status
            </button>
          </div>
        </form>
      </div>

      {/* Section 5: AI ENRICHMENT ERROR BANNER */}
      {enrichError && (
        <div className="bg-rose-500/10 border border-rose-500/30 p-4 rounded-xl flex items-start justify-between space-x-3 text-xs font-mono text-rose-300">
          <div className="flex items-start space-x-3">
            <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-bold">AI Enrichment Unavailable</p>
              <p className="text-rose-200/80">{enrichError}</p>
            </div>
          </div>

          <button
            onClick={handleEnrichAlert}
            disabled={enriching}
            className="px-3 py-1.5 bg-rose-500/20 hover:bg-rose-500/30 text-rose-300 rounded border border-rose-500/40 text-[11px] font-bold transition flex-shrink-0"
          >
            Retry AI Enrichment
          </button>
        </div>
      )}

      {/* Section 6: STRUCTURED RAG AI ANALYSIS OUTPUT */}
      {enrichment && (
        <div className="soc-card p-6 border border-purple-500/40 bg-purple-950/10 space-y-6 font-mono shadow-2xl">
          {/* Section Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-purple-500/20 pb-4">
            <div className="flex items-center space-x-2.5">
              <div className="p-2 bg-purple-500/20 rounded-lg text-purple-300 border border-purple-500/30">
                <Sparkles className="w-5 h-5 fill-current" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">AI Security Analysis</h3>
                <p className="text-[11px] text-purple-300/80">Grounded in retrieved cybersecurity knowledge (SQLite FTS5 + Gemini)</p>
              </div>
            </div>

            <span className="inline-flex items-center px-2.5 py-1 rounded-full text-[10px] font-bold bg-purple-500/15 text-purple-300 border border-purple-500/30 w-fit">
              Analyst Decision Support
            </span>
          </div>

          <div className="space-y-5 text-xs">
            {/* Executive Summary */}
            <div className="space-y-1.5">
              <h4 className="text-purple-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                <CheckCircle2 className="w-4 h-4 text-purple-400" />
                <span>Executive Analyst Summary</span>
              </h4>
              <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800 text-slate-200 leading-relaxed text-xs">
                {enrichment.analysis.summary}
              </div>
            </div>

            {/* Observed Indicators & Security Context Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Observed Indicators */}
              <div className="space-y-1.5">
                <h4 className="text-purple-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <ShieldAlert className="w-4 h-4 text-purple-400" />
                  <span>Observed Indicators</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {enrichment.analysis.observed_indicators.map((ind, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-purple-400 font-bold">•</span>
                        <span>{ind}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Security Context */}
              <div className="space-y-1.5">
                <h4 className="text-purple-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <BookOpen className="w-4 h-4 text-purple-400" />
                  <span>Security Context (MITRE ATT&CK / NIST)</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {enrichment.analysis.security_context.length === 0 ? (
                      <li className="text-slate-500 italic">No specific framework tags mapped.</li>
                    ) : (
                      enrichment.analysis.security_context.map((ctx, i) => (
                        <li key={i} className="flex items-start space-x-2">
                          <span className="text-purple-400 font-bold">•</span>
                          <span>{ctx}</span>
                        </li>
                      ))
                    )}
                  </ul>
                </div>
              </div>
            </div>

            {/* Investigation Steps & Recommended Mitigations Grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
              {/* Investigation Steps */}
              <div className="space-y-1.5">
                <h4 className="text-purple-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <ListChecks className="w-4 h-4 text-purple-400" />
                  <span>Recommended Investigation Steps</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ol className="space-y-2 text-slate-300">
                    {enrichment.analysis.investigation_steps.map((step, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-cyan-400 font-bold">{i + 1}.</span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              {/* Recommended Mitigations */}
              <div className="space-y-1.5">
                <h4 className="text-purple-300 font-bold uppercase tracking-wider flex items-center space-x-2">
                  <Shield className="w-4 h-4 text-purple-400" />
                  <span>Recommended Containment & Mitigations</span>
                </h4>
                <div className="bg-slate-900/90 p-4 rounded-xl border border-slate-800">
                  <ul className="space-y-1.5 text-slate-300">
                    {enrichment.analysis.recommended_mitigations.map((mit, i) => (
                      <li key={i} className="flex items-start space-x-2">
                        <span className="text-emerald-400 font-bold">✓</span>
                        <span>{mit}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </div>

            {/* Cited Knowledge Base Sources */}
            <div className="space-y-2 pt-2 border-t border-purple-500/20">
              <div className="flex items-center space-x-2 text-purple-300 font-bold uppercase">
                <BookOpen className="w-4 h-4 text-purple-400" />
                <span>Cited Cybersecurity Knowledge Sources ({enrichment.sources.length})</span>
              </div>

              <div className="space-y-2">
                {enrichment.sources.length === 0 ? (
                  <p className="text-slate-500 text-xs italic">No specific sources cited for this response.</p>
                ) : (
                  enrichment.sources.map((src, i) => (
                    <div key={i} className="p-3.5 bg-slate-900/90 rounded-xl border border-slate-800 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-[11px]">
                      <div>
                        <p className="text-slate-100 font-bold">{src.title || src.file_name}</p>
                        <p className="text-slate-400 font-mono text-[10px]">Source Reference: {src.source}</p>
                        <p className="text-slate-500 text-[10px]">Document ID: {src.document_id} • Chunk #{src.chunk_index}</p>
                      </div>
                      <span className="px-2.5 py-1 bg-purple-500/15 text-purple-300 rounded-lg border border-purple-500/30 font-mono font-bold w-fit">
                        {(src.score * 100).toFixed(1)}% Relevance
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

export default AlertDetailPage;
