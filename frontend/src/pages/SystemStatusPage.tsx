import React, { useEffect, useState } from 'react';
import { Server, CheckCircle2, XCircle, RefreshCw, Activity, Terminal } from 'lucide-react';
import { api } from '../services/api';
import { HealthResponse } from '../types';
import { formatApiError } from '../utils/error';

export const SystemStatusPage: React.FC = () => {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const checkHealth = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getHealth();
      setHealth(data);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Unable to reach backend service.'));
      setHealth(null);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    checkHealth();
  }, []);

  const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

  const systemModules = [
    { name: 'React + Vite Frontend', status: 'ONLINE', desc: 'Vite single page app & router client' },
    { name: 'FastAPI Backend API', status: health ? 'ONLINE' : 'OFFLINE', desc: 'GET /health readiness check' },
    { name: 'Random Forest IDS Pipeline', status: health ? 'ONLINE' : 'UNKNOWN', desc: 'CIC-IDS2017 flow classifier' },
    { name: 'PostgreSQL Alert Database', status: health ? 'ONLINE' : 'UNKNOWN', desc: 'Alert persistence & state transitions' },
    { name: 'Qdrant Vector Engine', status: health ? 'ONLINE' : 'UNKNOWN', desc: 'Sentence-Transformers embeddings store' },
    { name: 'Gemini LLM Integration', status: 'CONFIGURED', desc: 'RAG answer generation & investigation' },
  ];

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <div>
          <h2 className="text-base font-bold text-slate-100">System Readiness & Diagnostics</h2>
          <p className="text-xs text-slate-400">Backend health status check, service readiness, and active modules</p>
        </div>
        <button
          onClick={checkHealth}
          disabled={loading}
          className="flex items-center space-x-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold rounded-lg border border-slate-700 transition disabled:opacity-50"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>Run Health Check</span>
        </button>
      </div>

      {/* Primary Health Check Card */}
      <div className="soc-card p-6 border border-slate-800 space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <div className="flex items-center space-x-3">
            <Server className="w-6 h-6 text-cyan-400" />
            <div>
              <h3 className="text-sm font-bold text-slate-100">FastAPI Backend Status (GET /api/v1/system-status)</h3>
              <p className="text-slate-400 text-[11px]">Endpoint: {apiBaseUrl}/api/v1/system-status</p>
            </div>
          </div>

          <div>
            {loading ? (
              <span className="px-3 py-1 bg-slate-800 text-slate-400 rounded">Checking...</span>
            ) : health ? (
              <span className="px-3 py-1 bg-emerald-500/15 text-emerald-400 border border-emerald-500/30 rounded font-bold flex items-center space-x-1.5">
                <CheckCircle2 className="w-4 h-4" />
                <span>ONLINE (HTTP 200)</span>
              </span>
            ) : (
              <span className="px-3 py-1 bg-rose-500/15 text-rose-400 border border-rose-500/30 rounded font-bold flex items-center space-x-1.5">
                <XCircle className="w-4 h-4" />
                <span>OFFLINE</span>
              </span>
            )}
          </div>
        </div>

        {health && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-3 bg-slate-900/80 rounded border border-slate-800">
              <span className="text-slate-500 uppercase">Service Identifier</span>
              <p className="text-slate-200 font-bold mt-1">{health.service}</p>
            </div>
            <div className="p-3 bg-slate-900/80 rounded border border-slate-800">
              <span className="text-slate-500 uppercase">Health Payload</span>
              <p className="text-emerald-400 font-bold mt-1">status: "{health.status}"</p>
            </div>
          </div>
        )}

        {error && (
          <div className="p-4 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-lg">
            {error}
          </div>
        )}
      </div>

      {/* Modules Status Overview */}
      <div className="soc-card p-5 border border-slate-800 space-y-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
          Component Status Overview
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {systemModules.map((mod, i) => (
            <div key={i} className="p-4 bg-slate-900/60 rounded-lg border border-slate-800 flex items-center justify-between">
              <div>
                <h4 className="font-bold text-slate-200">{mod.name}</h4>
                <p className="text-slate-400 text-[11px]">{mod.desc}</p>
              </div>
              <span className={`px-2.5 py-1 rounded border font-bold text-[10px] ${
                mod.status === 'ONLINE' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' :
                mod.status === 'OFFLINE' ? 'bg-rose-500/10 text-rose-400 border-rose-500/30' :
                mod.status === 'CONFIGURED' ? 'bg-purple-500/10 text-purple-400 border-purple-500/30' :
                'bg-slate-800 text-slate-400 border-slate-700'
              }`}>
                {mod.status}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
