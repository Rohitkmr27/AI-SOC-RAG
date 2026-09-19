import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import { Filter, Radio, RefreshCw } from 'lucide-react';
import { api } from '../services/api';
import { CorrelationResponse, IncidentResponse } from '../types';
import { formatApiError } from '../utils/error';
import { RiskGauge } from '../components/RiskGauge';
import { ErrorBanner } from '../components/ErrorBanner';
import { TableSkeleton } from '../components/Skeleton';

export const IncidentsPage: React.FC = () => {
  const [correlations, setCorrelations] = useState<CorrelationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [lookbackMinutes, setLookbackMinutes] = useState<number>(1440); // default 24h
  const [minRiskScore, setMinRiskScore] = useState<number>(0);

  const fetchIncidents = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getCorrelations({
        lookback_minutes: lookbackMinutes,
        minimum_risk_score: minRiskScore > 0 ? minRiskScore : undefined,
      });
      setCorrelations(data);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to fetch correlated incident campaigns.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchIncidents();
  }, [lookbackMinutes, minRiskScore]);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono">Correlated Incident Campaigns</h2>
          <p className="text-xs text-slate-400 font-mono">Deterministic graph clustering (BFS) & explainable 0–100 risk scoring</p>
        </div>
        <button
          onClick={fetchIncidents}
          disabled={loading}
          className="flex items-center space-x-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-semibold rounded-lg border border-slate-700 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Reload Campaigns</span>
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchIncidents} />}

      {/* Filter Toolbar */}
      <div className="soc-card p-4 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4 font-mono text-xs">
        <div className="flex flex-wrap items-center gap-4 w-full md:w-auto">
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Time Lookback:</span>
            <select
              value={lookbackMinutes}
              onChange={(e) => setLookbackMinutes(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value={60}>1 Hour</option>
              <option value={360}>6 Hours</option>
              <option value={1440}>24 Hours</option>
              <option value={10080}>7 Days</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Min Risk Score:</span>
            <select
              value={minRiskScore}
              onChange={(e) => setMinRiskScore(Number(e.target.value))}
              className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value={0}>All Scores (&ge; 0)</option>
              <option value={25}>Low Risk (&ge; 25)</option>
              <option value={50}>Medium Risk (&ge; 50)</option>
              <option value={75}>High / Critical (&ge; 75)</option>
            </select>
          </div>
        </div>

        {correlations && (
          <div className="text-slate-400">
            Total Correlated Alerts: <strong className="text-cyan-400">{correlations.total_correlated_alerts}</strong>
          </div>
        )}
      </div>

      {/* Incidents List */}
      <div className="soc-card p-5 border border-slate-800">
        {loading ? (
          <TableSkeleton rows={4} />
        ) : !correlations || correlations.incidents.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs font-mono">
            No correlated incident campaigns found for selected time window.
          </div>
        ) : (
          <div className="space-y-4 font-mono">
            {correlations.incidents.map((incident: IncidentResponse) => (
              <div
                key={incident.incident_id}
                className="p-5 bg-slate-900/60 rounded-xl border border-slate-800 hover:border-slate-700 transition space-y-3"
              >
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3">
                  <div className="flex items-center space-x-3">
                    <Radio className="w-5 h-5 text-cyan-400" />
                    <div>
                      <h3 className="text-sm font-bold text-slate-100 font-mono">
                        Incident Campaign: {incident.incident_id}
                      </h3>
                      <p className="text-[11px] text-slate-400 font-mono">
                        Time Window: {new Date(incident.first_seen).toLocaleString()} &rarr; {new Date(incident.last_seen).toLocaleString()}
                      </p>
                    </div>
                  </div>

                  <div className="flex items-center space-x-4">
                    <RiskGauge score={incident.risk_score} />
                    <NavLink
                      to={`/incidents/${incident.incident_id}`}
                      className="px-3.5 py-1.5 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded-lg font-mono font-semibold text-xs transition"
                    >
                      Investigate Workspace
                    </NavLink>
                  </div>
                </div>

                {/* Campaign Data Breakdown */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs font-mono pt-1">
                  <div>
                    <span className="text-slate-500 uppercase block mb-1">Alert Count & Attack Types</span>
                    <p className="text-slate-200">
                      <strong>{incident.alert_count} Alerts</strong> ({incident.attack_types.join(', ') || 'N/A'})
                    </p>
                  </div>

                  <div>
                    <span className="text-slate-500 uppercase block mb-1">Source IP Addresses</span>
                    <p className="text-slate-300 truncate">{incident.source_ips.join(', ') || 'N/A'}</p>
                  </div>

                  <div>
                    <span className="text-slate-500 uppercase block mb-1">Target Destination IPs</span>
                    <p className="text-slate-300 truncate">{incident.destination_ips.join(', ') || 'N/A'}</p>
                  </div>
                </div>

                {/* Risk Factors Bullet List */}
                <div className="bg-slate-950/60 p-3 rounded-lg border border-slate-800/80 text-[11px] font-mono">
                  <span className="text-slate-400 font-semibold uppercase block mb-1">Rule Engine Risk Factors:</span>
                  <div className="flex flex-wrap gap-2">
                    {incident.risk_factors.map((factor, idx) => (
                      <span key={idx} className="px-2 py-0.5 bg-slate-800 text-slate-300 rounded border border-slate-700">
                        • {factor}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
