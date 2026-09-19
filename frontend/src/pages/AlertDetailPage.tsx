import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Sparkles, Shield, Network, Cpu, Workflow, BookOpen } from 'lucide-react';
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
      setEnrichError(formatApiError(err, 'Alert RAG enrichment service unavailable.'));
    } finally {
      setEnriching(false);
    }
  };

  if (loading) {
    return (
      <div className="py-20 text-center text-slate-400 text-xs font-mono">
        Loading alert metadata from PostgreSQL backend...
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
    <div className="space-y-6">
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
            className="flex items-center justify-center space-x-2 px-4 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-semibold font-mono text-xs rounded-lg shadow-lg transition disabled:opacity-50"
          >
            <Sparkles className={`w-4 h-4 ${enriching ? 'animate-spin' : ''}`} />
            <span>{enriching ? 'Synthesizing RAG Enrichment...' : 'Enrich with AI'}</span>
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

      {/* Section 5: AI ENRICHMENT OUTPUT */}
      {enrichError && <ErrorBanner message={enrichError} />}

      {enrichment && (
        <div className="soc-card p-6 border border-purple-500/30 bg-purple-950/10 space-y-5">
          <div className="flex items-center space-x-2 border-b border-purple-500/20 pb-3">
            <Sparkles className="w-5 h-5 text-purple-400" />
            <h3 className="text-sm font-bold text-purple-200 font-mono">Grounded RAG Security Enrichment</h3>
          </div>

          <div className="space-y-4 text-xs font-mono">
            <div>
              <h4 className="text-purple-300 font-bold uppercase mb-1">Executive Analyst Summary</h4>
              <p className="text-slate-200 leading-relaxed bg-slate-900/80 p-3.5 rounded border border-slate-800">
                {enrichment.analysis.summary}
              </p>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-purple-300 font-bold uppercase mb-1">Observed Indicators</h4>
                <ul className="list-disc list-inside space-y-1 bg-slate-900/80 p-3.5 rounded border border-slate-800 text-slate-300">
                  {enrichment.analysis.observed_indicators.map((ind, i) => (
                    <li key={i}>{ind}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-purple-300 font-bold uppercase mb-1">Security Context (MITRE ATT&CK / NIST)</h4>
                <ul className="list-disc list-inside space-y-1 bg-slate-900/80 p-3.5 rounded border border-slate-800 text-slate-300">
                  {enrichment.analysis.security_context.map((ctx, i) => (
                    <li key={i}>{ctx}</li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <h4 className="text-purple-300 font-bold uppercase mb-1">Recommended Investigation Steps</h4>
                <ul className="list-disc list-inside space-y-1 bg-slate-900/80 p-3.5 rounded border border-slate-800 text-slate-300">
                  {enrichment.analysis.investigation_steps.map((step, i) => (
                    <li key={i}>{step}</li>
                  ))}
                </ul>
              </div>

              <div>
                <h4 className="text-purple-300 font-bold uppercase mb-1">Recommended Mitigations</h4>
                <ul className="list-disc list-inside space-y-1 bg-slate-900/80 p-3.5 rounded border border-slate-800 text-slate-300">
                  {enrichment.analysis.recommended_mitigations.map((mit, i) => (
                    <li key={i}>{mit}</li>
                  ))}
                </ul>
              </div>
            </div>

            {/* Retrieved Knowledge Base Sources */}
            <div className="pt-2">
              <div className="flex items-center space-x-2 text-purple-300 font-bold uppercase mb-2">
                <BookOpen className="w-4 h-4" />
                <span>Cited Knowledge Base Sources ({enrichment.sources.length})</span>
              </div>
              <div className="space-y-2">
                {enrichment.sources.map((src, i) => (
                  <div key={i} className="p-3 bg-slate-900/90 rounded border border-slate-800 flex items-center justify-between text-[11px]">
                    <div>
                      <p className="text-slate-200 font-bold">{src.title || src.file_name}</p>
                      <p className="text-slate-500 font-mono">Source Path: {src.source}</p>
                      <p className="text-slate-500 text-[10px]">Document ID: {src.document_id} • Chunk #{src.chunk_index}</p>
                    </div>
                    <span className="px-2.5 py-1 bg-purple-500/10 text-purple-400 rounded border border-purple-500/20 font-mono font-bold">
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
