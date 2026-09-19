import React, { useEffect, useState } from 'react';
import { useNavigate, NavLink } from 'react-router-dom';
import { Filter, RefreshCw, Search } from 'lucide-react';
import { api } from '../services/api';
import { AlertResponse, AlertSeverity, AlertStatus } from '../types';
import { formatApiError } from '../utils/error';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { ErrorBanner } from '../components/ErrorBanner';
import { TableSkeleton } from '../components/Skeleton';

export const AlertsPage: React.FC = () => {
  const navigate = useNavigate();
  const [alerts, setAlerts] = useState<AlertResponse[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  // Filters
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState<string>('');

  const fetchAlerts = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getAlerts({
        severity: selectedSeverity ? (selectedSeverity as AlertSeverity) : undefined,
        status: selectedStatus ? (selectedStatus as AlertStatus) : undefined,
        attack_type: searchQuery.trim() || undefined,
      });
      setAlerts(data);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to fetch alerts directory from backend.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, [selectedSeverity, selectedStatus]);

  const handleSearchSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    fetchAlerts();
  };

  // Client-side IP filtering if query contains dot/IP format
  const filteredAlerts = alerts.filter((alert) => {
    if (!searchQuery.trim()) return true;
    const q = searchQuery.toLowerCase().trim();
    return (
      alert.attack_type.toLowerCase().includes(q) ||
      alert.source_ip.toLowerCase().includes(q) ||
      alert.destination_ip.toLowerCase().includes(q)
    );
  });

  return (
    <div className="space-y-6">
      {/* Header Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono">Security Alerts Directory</h2>
          <p className="text-xs text-slate-400 font-mono">Real-time alert records and flow classifications from PostgreSQL</p>
        </div>
        <button
          onClick={fetchAlerts}
          disabled={loading}
          className="flex items-center space-x-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-semibold rounded-lg border border-slate-700 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Reload Directory</span>
        </button>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchAlerts} />}

      {/* Filter Controls Toolbar */}
      <div className="soc-card p-4 border border-slate-800 flex flex-col md:flex-row items-center justify-between gap-4 font-mono text-xs">
        <form onSubmit={handleSearchSubmit} className="w-full md:w-auto flex items-center space-x-2">
          <div className="relative w-full sm:w-64">
            <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
            <input
              type="text"
              placeholder="Search IP or Attack Type..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3 py-1.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-500 font-mono"
            />
          </div>
          <button
            type="submit"
            className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-xs text-slate-200 font-semibold rounded-lg border border-slate-700"
          >
            Search
          </button>
        </form>

        <div className="w-full md:w-auto flex flex-wrap items-center gap-3">
          <div className="flex items-center space-x-2">
            <Filter className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-slate-400">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value="">All Severities</option>
              <option value="Critical">Critical</option>
              <option value="High">High</option>
              <option value="Medium">Medium</option>
              <option value="Low">Low</option>
              <option value="Informational">Informational</option>
            </select>
          </div>

          <div className="flex items-center space-x-2">
            <span className="text-slate-400">Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-slate-900 border border-slate-700 text-slate-200 rounded-lg px-2.5 py-1.5 focus:outline-none focus:border-cyan-500 font-mono"
            >
              <option value="">All Statuses</option>
              <option value="NEW">NEW</option>
              <option value="TRIAGED">TRIAGED</option>
              <option value="INVESTIGATING">INVESTIGATING</option>
              <option value="RESOLVED">RESOLVED</option>
            </select>
          </div>
        </div>
      </div>

      {/* Alerts Table */}
      <div className="soc-card p-5 border border-slate-800">
        {loading ? (
          <TableSkeleton rows={6} />
        ) : filteredAlerts.length === 0 ? (
          <div className="py-16 text-center text-slate-500 text-xs font-mono">
            No alerts found matching filter query.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase">
                  <th className="py-3 px-3">Timestamp</th>
                  <th className="py-3 px-3">Severity</th>
                  <th className="py-3 px-3">Status</th>
                  <th className="py-3 px-3">Attack Type</th>
                  <th className="py-3 px-3">Source Endpoint</th>
                  <th className="py-3 px-3">Destination Endpoint</th>
                  <th className="py-3 px-3">Protocol</th>
                  <th className="py-3 px-3">Confidence</th>
                  <th className="py-3 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {filteredAlerts.map((alert) => (
                  <tr
                    key={alert.id}
                    onClick={() => navigate(`/alerts/${alert.id}`)}
                    className="hover:bg-slate-800/40 cursor-pointer transition"
                  >
                    <td className="py-3 px-3 text-slate-400 whitespace-nowrap">
                      {new Date(alert.timestamp).toLocaleString()}
                    </td>
                    <td className="py-3 px-3">
                      <SeverityBadge severity={alert.severity} />
                    </td>
                    <td className="py-3 px-3">
                      <StatusBadge status={alert.status} />
                    </td>
                    <td className="py-3 px-3 text-slate-100 font-bold">{alert.attack_type}</td>
                    <td className="py-3 px-3 text-slate-300">
                      {alert.source_ip}:{alert.source_port}
                    </td>
                    <td className="py-3 px-3 text-slate-300">
                      {alert.destination_ip}:{alert.destination_port}
                    </td>
                    <td className="py-3 px-3 text-slate-400 uppercase">{alert.protocol}</td>
                    <td className="py-3 px-3 text-slate-400">{(alert.confidence * 100).toFixed(0)}%</td>
                    <td className="py-3 px-3 text-right">
                      <NavLink
                        to={`/alerts/${alert.id}`}
                        onClick={(e) => e.stopPropagation()}
                        className="px-3 py-1 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded font-semibold text-[11px]"
                      >
                        Inspect
                      </NavLink>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
