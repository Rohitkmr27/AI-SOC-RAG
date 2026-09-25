import React, { useEffect, useState } from 'react';
import { NavLink } from 'react-router-dom';
import {
  Bell,
  AlertTriangle,
  Radio,
  CheckCircle,
  RefreshCw,
  ExternalLink,
  ShieldAlert,
  BarChart3,
  PieChart as PieChartIcon,
} from 'lucide-react';
import {
  Bar,
  BarChart,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';
import { AlertResponse, CorrelationResponse } from '../types';
import { formatApiError } from '../utils/error';
import { StatCard } from '../components/StatCard';
import { SeverityBadge } from '../components/SeverityBadge';
import { StatusBadge } from '../components/StatusBadge';
import { RiskGauge } from '../components/RiskGauge';
import { ErrorBanner } from '../components/ErrorBanner';
import { TableSkeleton } from '../components/Skeleton';

export const OverviewPage: React.FC = () => {
  const [alerts, setAlerts] = useState<AlertResponse[]>([]);
  const [correlations, setCorrelations] = useState<CorrelationResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const [alertsData, corrData] = await Promise.all([
        api.getAlerts(),
        api.getCorrelations({ lookback_minutes: 1440 }),
      ]);
      setAlerts(alertsData);
      setCorrelations(corrData);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to fetch dashboard data from backend.'));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, []);

  const totalAlerts = alerts.length;
  const newAlerts = alerts.filter((a) => a.status === 'NEW').length;
  const highCriticalAlerts = alerts.filter((a) => a.severity === 'High' || a.severity === 'Critical').length;
  const investigatingAlerts = alerts.filter((a) => a.status === 'INVESTIGATING').length;
  const resolvedAlerts = alerts.filter((a) => a.status === 'RESOLVED').length;
  const totalIncidents = correlations?.total_incidents ?? 0;

  // Real Severity Distribution
  const severityCounts = {
    Critical: alerts.filter((a) => a.severity === 'Critical').length,
    High: alerts.filter((a) => a.severity === 'High').length,
    Medium: alerts.filter((a) => a.severity === 'Medium').length,
    Low: alerts.filter((a) => a.severity === 'Low').length,
    Informational: alerts.filter((a) => a.severity === 'Informational').length,
  };

  const pieChartData = [
    { name: 'Critical', value: severityCounts.Critical, color: '#f43f5e' },
    { name: 'High', value: severityCounts.High, color: '#f97316' },
    { name: 'Medium', value: severityCounts.Medium, color: '#eab308' },
    { name: 'Low', value: severityCounts.Low, color: '#3b82f6' },
    { name: 'Informational', value: severityCounts.Informational, color: '#94a3b8' },
  ].filter((d) => d.value > 0);

  // Real Attack-Type Distribution
  const attackTypeMap: Record<string, number> = {};
  alerts.forEach((a) => {
    const at = a.attack_type || 'Unknown';
    attackTypeMap[at] = (attackTypeMap[at] || 0) + 1;
  });

  const barChartData = Object.entries(attackTypeMap).map(([name, count]) => ({
    name,
    count,
  }));

  const [seeding, setSeeding] = useState<boolean>(false);

  const handleSeed = async () => {
    setSeeding(true);
    try {
      await api.seedAlerts();
      await fetchData();
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to seed sample telemetry into database.'));
    } finally {
      setSeeding(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header Toolbar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-100 font-mono">SOC Threat Intelligence Overview</h2>
          <p className="text-xs text-slate-400 font-mono">Real-time metrics derived strictly from PostgreSQL & FastAPI backend</p>
        </div>
        <div className="flex items-center space-x-3">
          {totalAlerts === 0 && !loading && (
            <button
              onClick={handleSeed}
              disabled={seeding}
              className="flex items-center space-x-2 px-3.5 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-mono font-semibold rounded-lg border border-indigo-500 shadow-md shadow-indigo-950/50 transition disabled:opacity-50"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${seeding ? 'animate-spin' : ''}`} />
              <span>{seeding ? 'Seeding Data...' : 'Seed Sample Telemetry'}</span>
            </button>
          )}
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center space-x-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-mono font-semibold rounded-lg border border-slate-700 transition disabled:opacity-50"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
            <span>Refresh Metrics</span>
          </button>
        </div>
      </div>

      {error && <ErrorBanner message={error} onRetry={fetchData} />}

      {/* Operational KPI Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        <StatCard title="Total Alerts" value={totalAlerts} icon={Bell} loading={loading} />
        <StatCard
          title="New Alerts"
          value={newAlerts}
          icon={AlertTriangle}
          colorClass="text-purple-400 bg-purple-500/10 border-purple-500/20"
          loading={loading}
        />
        <StatCard
          title="High/Critical"
          value={highCriticalAlerts}
          icon={ShieldAlert}
          colorClass="text-rose-400 bg-rose-500/10 border-rose-500/20"
          loading={loading}
        />
        <StatCard
          title="Investigating"
          value={investigatingAlerts}
          icon={Radio}
          colorClass="text-amber-400 bg-amber-500/10 border-amber-500/20"
          loading={loading}
        />
        <StatCard
          title="Resolved"
          value={resolvedAlerts}
          icon={CheckCircle}
          colorClass="text-emerald-400 bg-emerald-500/10 border-emerald-500/20"
          loading={loading}
        />
        <StatCard
          title="Correlated Incidents"
          value={totalIncidents}
          icon={Radio}
          colorClass="text-cyan-400 bg-cyan-500/10 border-cyan-500/20"
          loading={loading}
        />
      </div>

      {/* Visual Analytics Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Severity Distribution Pie Chart */}
        <div className="soc-card p-5 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <PieChartIcon className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
              Severity Distribution (Real API Data)
            </h3>
          </div>
          {loading ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs font-mono">Loading chart...</div>
          ) : pieChartData.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs font-mono">
              Data unavailable (No alert records in database)
            </div>
          ) : (
            <div className="h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie data={pieChartData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} paddingAngle={4} dataKey="value">
                    {pieChartData.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.5rem', color: '#f8fafc' }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="flex flex-wrap justify-center gap-3 text-xs font-mono mt-1">
                {pieChartData.map((item) => (
                  <span key={item.name} className="flex items-center space-x-1.5">
                    <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></span>
                    <span className="text-slate-300">{item.name}: {item.value}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Attack-Type Distribution Bar Chart */}
        <div className="soc-card p-5 border border-slate-800 space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <BarChart3 className="w-4 h-4 text-cyan-400" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
              Attack-Type Frequency (Real API Data)
            </h3>
          </div>
          {loading ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs font-mono">Loading chart...</div>
          ) : barChartData.length === 0 ? (
            <div className="h-56 flex items-center justify-center text-slate-500 text-xs font-mono">
              Data unavailable (No alert records in database)
            </div>
          ) : (
            <div className="h-56 font-mono text-xs">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barChartData} margin={{ top: 10, right: 10, left: -20, bottom: 20 }}>
                  <XAxis dataKey="name" stroke="#64748b" tick={{ fontSize: 10 }} />
                  <YAxis stroke="#64748b" allowDecimals={false} tick={{ fontSize: 10 }} />
                  <Tooltip contentStyle={{ backgroundColor: '#0f172a', borderColor: '#334155', borderRadius: '0.5rem', color: '#f8fafc' }} />
                  <Bar dataKey="count" fill="#06b6d4" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
      </div>

      {/* Correlated Incidents Section */}
      <div className="soc-card p-5 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
            Recent Correlated Incident Campaigns (Last 24h)
          </h3>
          <NavLink to="/incidents" className="text-xs text-cyan-400 hover:underline flex items-center space-x-1 font-mono">
            <span>View All Campaigns</span>
            <ExternalLink className="w-3 h-3" />
          </NavLink>
        </div>

        {loading ? (
          <TableSkeleton rows={3} />
        ) : !correlations || correlations.incidents.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs font-mono">
            Data unavailable (No correlated incidents found in lookback window)
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase">
                  <th className="py-2.5 px-3">Risk Score</th>
                  <th className="py-2.5 px-3">Alert Count</th>
                  <th className="py-2.5 px-3">Attack Types</th>
                  <th className="py-2.5 px-3">Source IPs</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {correlations.incidents.slice(0, 4).map((inc) => (
                  <tr key={inc.incident_id} className="hover:bg-slate-800/40 transition">
                    <td className="py-3 px-3">
                      <RiskGauge score={inc.risk_score} showLabel={false} />
                    </td>
                    <td className="py-3 px-3 text-slate-100 font-bold">{inc.alert_count}</td>
                    <td className="py-3 px-3 text-slate-300">{inc.attack_types.join(', ') || 'N/A'}</td>
                    <td className="py-3 px-3 text-slate-400">{inc.source_ips.join(', ') || 'N/A'}</td>
                    <td className="py-3 px-3 text-right">
                      <NavLink
                        to={`/incidents/${inc.incident_id}`}
                        className="px-2.5 py-1 bg-cyan-500/10 hover:bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 rounded font-semibold text-[11px]"
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

      {/* Recent Alerts List */}
      <div className="soc-card p-5 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <h3 className="text-xs font-bold uppercase tracking-wider text-slate-200 font-mono">
            Latest Registered Alerts
          </h3>
          <NavLink to="/alerts" className="text-xs text-cyan-400 hover:underline flex items-center space-x-1 font-mono">
            <span>View All Alerts</span>
            <ExternalLink className="w-3 h-3" />
          </NavLink>
        </div>

        {loading ? (
          <TableSkeleton rows={5} />
        ) : alerts.length === 0 ? (
          <div className="py-8 text-center text-slate-500 text-xs font-mono">No alerts registered in database.</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs font-mono border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 uppercase">
                  <th className="py-2.5 px-3">Timestamp</th>
                  <th className="py-2.5 px-3">Severity</th>
                  <th className="py-2.5 px-3">Status</th>
                  <th className="py-2.5 px-3">Attack Type</th>
                  <th className="py-2.5 px-3">Source IP</th>
                  <th className="py-2.5 px-3">Destination IP</th>
                  <th className="py-2.5 px-3">Confidence</th>
                  <th className="py-2.5 px-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {alerts.slice(0, 5).map((alert) => (
                  <tr key={alert.id} className="hover:bg-slate-800/40 transition">
                    <td className="py-2.5 px-3 text-slate-400 whitespace-nowrap">
                      {new Date(alert.timestamp).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-3">
                      <SeverityBadge severity={alert.severity} />
                    </td>
                    <td className="py-2.5 px-3">
                      <StatusBadge status={alert.status} />
                    </td>
                    <td className="py-2.5 px-3 text-slate-200 font-bold">{alert.attack_type}</td>
                    <td className="py-2.5 px-3 text-slate-300">{alert.source_ip}</td>
                    <td className="py-2.5 px-3 text-slate-300">{alert.destination_ip}</td>
                    <td className="py-2.5 px-3 text-slate-400">{(alert.confidence * 100).toFixed(0)}%</td>
                    <td className="py-2.5 px-3 text-right">
                      <NavLink
                        to={`/alerts/${alert.id}`}
                        className="px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 border border-slate-700 rounded font-semibold text-[11px]"
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
