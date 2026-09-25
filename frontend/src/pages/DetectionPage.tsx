import React, { useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  UploadCloud,
  FileSpreadsheet,
  X,
  Play,
  AlertTriangle,
  CheckCircle2,
  ShieldAlert,
  ArrowRight,
  Info,
  RefreshCw,
  Activity,
  Layers,
  Database,
  Filter,
} from 'lucide-react';
import { api } from '../services/api';
import { CsvAlertResponse } from '../types';

export const DetectionPage: React.FC = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<CsvAlertResponse | null>(null);

  const handleFileChange = (file: File | null) => {
    setError(null);
    if (!file) {
      setSelectedFile(null);
      return;
    }

    if (!file.name.toLowerCase().endsWith('.csv')) {
      setError('Please select a valid CSV file with a .csv extension.');
      setSelectedFile(null);
      return;
    }

    const maxBytes = 10 * 1024 * 1024; // 10 MB limit
    if (file.size > maxBytes) {
      setError(`File size (${(file.size / (1024 * 1024)).toFixed(2)} MB) exceeds maximum allowed limit of 10 MB.`);
      setSelectedFile(null);
      return;
    }

    setSelectedFile(file);
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFileChange(e.dataTransfer.files[0]);
    }
  };

  const handleRunDetection = async () => {
    if (!selectedFile) return;

    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await api.uploadCsvForAlerts(selectedFile);
      setResult(data);
    } catch (err: any) {
      if (err.response) {
        const status = err.response.status;
        const detail = err.response.data?.detail;

        if (status === 401) {
          setError('Session expired. Please log in again.');
        } else if (status === 413) {
          setError('File size exceeds the 10 MB limit supported by the server.');
        } else if (status === 422) {
          setError(typeof detail === 'string' ? detail : 'CSV feature columns do not match the expected IDS training schema.');
        } else if (typeof detail === 'string') {
          setError(detail);
        } else {
          setError(`Detection failed with HTTP status ${status}.`);
        }
      } else if (err.request) {
        setError('Could not connect to the IDS backend service. Please check network connection.');
      } else {
        setError(err.message || 'An unexpected error occurred during detection.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setResult(null);
    setError(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024 * 1024) {
      return `${(bytes / 1024).toFixed(1)} KB`;
    }
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto pb-12">
      {/* Header Banner */}
      <div className="bg-[#0d1322] p-6 rounded-2xl border border-slate-800/80 shadow-xl flex flex-col lg:flex-row justify-between lg:items-center gap-4">
        <div>
          <div className="flex items-center space-x-3 mb-1">
            <Activity className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl font-bold font-mono text-slate-100">IDS Network Flow Detection Center</h1>
          </div>
          <p className="text-xs text-slate-400 font-mono">
            Execute batch anomaly detection using the trained Random Forest model. Detected attacks automatically convert to persistent SOC alerts.
          </p>
        </div>

        {/* Safety & Constraints Chips */}
        <div className="flex flex-wrap gap-2 text-[11px] font-mono">
          <span className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center space-x-1.5">
            <FileSpreadsheet className="w-3.5 h-3.5 text-cyan-400" />
            <span>CSV Format</span>
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center space-x-1.5">
            <Database className="w-3.5 h-3.5 text-purple-400" />
            <span>Max 10 MB</span>
          </span>
          <span className="px-3 py-1.5 rounded-lg bg-slate-900 border border-slate-800 text-slate-300 flex items-center space-x-1.5">
            <Layers className="w-3.5 h-3.5 text-amber-400" />
            <span>Max 10,000 Rows</span>
          </span>
        </div>
      </div>

      {/* Main Grid: Upload & Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Upload Drop Zone (2 Columns) */}
        <div className="lg:col-span-2 space-y-4">
          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            className={`relative p-8 rounded-2xl border-2 border-dashed transition-all cursor-pointer flex flex-col items-center justify-center min-h-[220px] text-center ${
              dragOver
                ? 'border-cyan-400 bg-cyan-500/10'
                : selectedFile
                ? 'border-emerald-500/50 bg-emerald-500/5'
                : 'border-slate-800 bg-[#0d1322] hover:border-slate-700 hover:bg-slate-900/50'
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={(e) => handleFileChange(e.target.files?.[0] || null)}
              accept=".csv"
              className="hidden"
            />

            {!selectedFile ? (
              <>
                <div className="p-4 bg-slate-900/90 rounded-2xl border border-slate-800 text-cyan-400 mb-3 shadow-inner">
                  <UploadCloud className="w-8 h-8" />
                </div>
                <h3 className="text-sm font-bold font-mono text-slate-200">
                  Click to select CSV or drag and drop
                </h3>
                <p className="text-xs text-slate-500 font-mono mt-1">
                  Supports CIC-IDS2017 flow data files (*.csv)
                </p>
              </>
            ) : (
              <div
                className="w-full flex items-center justify-between p-4 bg-slate-900/90 rounded-xl border border-emerald-500/30"
                onClick={(e) => e.stopPropagation()}
              >
                <div className="flex items-center space-x-3 min-w-0">
                  <div className="p-2.5 bg-emerald-500/10 text-emerald-400 rounded-lg border border-emerald-500/30 flex-shrink-0">
                    <FileSpreadsheet className="w-6 h-6" />
                  </div>
                  <div className="text-left min-w-0">
                    <p className="text-xs font-bold font-mono text-slate-200 truncate">{selectedFile.name}</p>
                    <p className="text-[11px] font-mono text-slate-400">{formatFileSize(selectedFile.size)}</p>
                  </div>
                </div>

                <button
                  onClick={handleReset}
                  disabled={loading}
                  title="Remove file"
                  className="p-1.5 bg-slate-800 hover:bg-rose-500/20 text-slate-400 hover:text-rose-400 rounded-lg border border-slate-700 hover:border-rose-500/30 transition ml-2"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            )}
          </div>

          {/* Action Row */}
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-500">
              {selectedFile ? 'Ready to analyze flow batch' : 'Select a file to enable execution'}
            </span>

            <button
              onClick={handleRunDetection}
              disabled={!selectedFile || loading}
              className={`px-6 py-2.5 rounded-xl font-mono text-xs font-bold flex items-center space-x-2 transition-all shadow-lg ${
                !selectedFile || loading
                  ? 'bg-slate-800 text-slate-600 border border-slate-700/50 cursor-not-allowed'
                  : 'bg-cyan-500 hover:bg-cyan-400 text-slate-950 border border-cyan-400 shadow-cyan-500/20 active:scale-95'
              }`}
            >
              {loading ? (
                <>
                  <RefreshCw className="w-4 h-4 animate-spin text-slate-950" />
                  <span>Analyzing Network Flows...</span>
                </>
              ) : (
                <>
                  <Play className="w-4 h-4 fill-current" />
                  <span>Run IDS Detection</span>
                </>
              )}
            </button>
          </div>
        </div>

        {/* Instructions / Guidance Panel (1 Column) */}
        <div className="bg-[#0d1322] p-6 rounded-2xl border border-slate-800/80 space-y-4 font-mono text-xs">
          <div className="flex items-center space-x-2 text-cyan-400 font-bold border-b border-slate-800 pb-3">
            <Info className="w-4 h-4" />
            <span>Detection Pipeline Architecture</span>
          </div>

          <div className="space-y-3 text-slate-400 text-[11px] leading-relaxed">
            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">1.</span>
              <p><strong className="text-slate-200">Cached Model:</strong> Uses pre-loaded Random Forest model trained on CIC-IDS2017 features.</p>
            </div>

            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">2.</span>
              <p><strong className="text-slate-200">BENIGN Filtering:</strong> Normal traffic flows are evaluated and ignored.</p>
            </div>

            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">3.</span>
              <p><strong className="text-slate-200">Deduplication:</strong> Attack flows are hashed against existing SQL database signatures.</p>
            </div>

            <div className="flex items-start space-x-2">
              <span className="text-cyan-400 font-bold">4.</span>
              <p><strong className="text-slate-200">SOC Alerts:</strong> Unique attack flows are converted to persistent Alert records available for correlation.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Error Notification */}
      {error && (
        <div className="bg-rose-500/10 border border-rose-500/30 p-4 rounded-xl flex items-start space-x-3 text-xs font-mono text-rose-300">
          <AlertTriangle className="w-4 h-4 text-rose-400 flex-shrink-0 mt-0.5" />
          <div className="space-y-1">
            <p className="font-bold">Detection Failed</p>
            <p className="text-rose-200/80">{error}</p>
          </div>
        </div>
      )}

      {/* Empty State before run */}
      {!result && !loading && !error && (
        <div className="bg-[#0d1322] border border-slate-800/80 rounded-2xl p-12 text-center space-y-3 font-mono">
          <div className="w-12 h-12 rounded-2xl bg-slate-900 border border-slate-800 text-slate-500 mx-auto flex items-center justify-center">
            <ShieldAlert className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-300">No Detection Run Executed Yet</h3>
          <p className="text-xs text-slate-500 max-w-md mx-auto">
            Upload a CIC-IDS2017 network-flow CSV file to analyze traffic using the trained Random Forest IDS.
            Detected attacks will automatically become persistent SOC alerts.
          </p>
        </div>
      )}

      {/* Loading Indeterminate View */}
      {loading && (
        <div className="bg-[#0d1322] border border-cyan-500/30 rounded-2xl p-12 text-center space-y-4 font-mono shadow-xl animate-pulse">
          <div className="w-12 h-12 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 mx-auto flex items-center justify-center">
            <RefreshCw className="w-6 h-6 animate-spin" />
          </div>
          <div className="space-y-1">
            <h3 className="text-sm font-bold text-slate-200">Analyzing Network Flows...</h3>
            <p className="text-xs text-slate-400">
              Running Random Forest batch inference, filtering benign traffic, and persisting attack alerts...
            </p>
          </div>
        </div>
      )}

      {/* Detection Results Summary Dashboard */}
      {result && (
        <div className="space-y-6">
          {/* Section Title */}
          <div className="flex items-center justify-between border-b border-slate-800 pb-3 font-mono">
            <div className="flex items-center space-x-2">
              <CheckCircle2 className="w-5 h-5 text-emerald-400" />
              <h2 className="text-base font-bold text-slate-200">Detection & Persistence Summary</h2>
            </div>
            <span className="text-xs text-slate-400">Batch Inference Complete</span>
          </div>

          {/* 4 Summary Stat Cards */}
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 font-mono">
            {/* Total Flows */}
            <div className="bg-[#0d1322] p-4 rounded-xl border border-slate-800">
              <p className="text-[11px] text-slate-400 font-medium uppercase">Total Flows</p>
              <p className="text-2xl font-bold text-slate-100 mt-1">{result.total_flows}</p>
            </div>

            {/* Normal Flows */}
            <div className="bg-[#0d1322] p-4 rounded-xl border border-emerald-500/30 bg-emerald-500/5">
              <p className="text-[11px] text-emerald-400 font-medium uppercase">Normal Flows</p>
              <p className="text-2xl font-bold text-emerald-300 mt-1">{result.normal_flows}</p>
            </div>

            {/* Attack Flows */}
            <div className="bg-[#0d1322] p-4 rounded-xl border border-rose-500/30 bg-rose-500/5">
              <p className="text-[11px] text-rose-400 font-medium uppercase">Attack Flows</p>
              <p className="text-2xl font-bold text-rose-300 mt-1">{result.attack_flows}</p>
            </div>

            {/* Alerts Created */}
            <div className="bg-[#0d1322] p-4 rounded-xl border border-cyan-500/30 bg-cyan-500/5">
              <p className="text-[11px] text-cyan-400 font-medium uppercase">Alerts Created</p>
              <p className="text-2xl font-bold text-cyan-300 mt-1">{result.alerts_created}</p>
            </div>

            {/* Duplicates Skipped */}
            <div className="bg-[#0d1322] p-4 rounded-xl border border-purple-500/30 bg-purple-500/5 col-span-2 md:col-span-1">
              <p className="text-[11px] text-purple-400 font-medium uppercase">Dupes Skipped</p>
              <p className="text-2xl font-bold text-purple-300 mt-1">{result.duplicates_skipped}</p>
            </div>
          </div>

          {/* Breakdown Cards Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 font-mono text-xs">
            {/* Attack Types Distribution */}
            <div className="bg-[#0d1322] p-5 rounded-2xl border border-slate-800 space-y-3">
              <div className="flex items-center space-x-2 text-slate-300 font-bold border-b border-slate-800 pb-2.5">
                <ShieldAlert className="w-4 h-4 text-rose-400" />
                <span>Detected Attack Classifications</span>
              </div>

              {Object.keys(result.attack_types).length === 0 ? (
                <p className="text-slate-500 text-xs py-2">No attack classifications detected (100% normal traffic).</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(result.attack_types).map(([type, count]) => (
                    <div key={type} className="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                      <span className="font-bold text-slate-200">{type}</span>
                      <span className="px-2.5 py-0.5 rounded bg-rose-500/15 text-rose-400 border border-rose-500/30 font-bold">
                        {count} {count === 1 ? 'flow' : 'flows'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Severity Distribution */}
            <div className="bg-[#0d1322] p-5 rounded-2xl border border-slate-800 space-y-3">
              <div className="flex items-center space-x-2 text-slate-300 font-bold border-b border-slate-800 pb-2.5">
                <Filter className="w-4 h-4 text-amber-400" />
                <span>Severity Classification Breakdown</span>
              </div>

              {Object.keys(result.severity_counts).length === 0 ? (
                <p className="text-slate-500 text-xs py-2">No severity classifications recorded.</p>
              ) : (
                <div className="space-y-2">
                  {Object.entries(result.severity_counts).map(([sev, count]) => (
                    <div key={sev} className="flex items-center justify-between bg-slate-900/80 p-2.5 rounded-lg border border-slate-800">
                      <span className="font-bold text-slate-200">{sev}</span>
                      <span className="px-2.5 py-0.5 rounded bg-amber-500/15 text-amber-400 border border-amber-500/30 font-bold">
                        {count} {count === 1 ? 'alert' : 'alerts'}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Deduplication Notice Banner if duplicates were skipped */}
          {result.duplicates_skipped > 0 && (
            <div className="bg-purple-500/10 border border-purple-500/30 p-4 rounded-xl flex items-center space-x-3 text-xs font-mono text-purple-300">
              <Info className="w-4 h-4 text-purple-400 flex-shrink-0" />
              <p>
                <strong className="text-purple-200">Deduplication Enforced:</strong> {result.duplicates_skipped} duplicate attack flows were skipped because identical signatures already exist in the alert database.
              </p>
            </div>
          )}

          {/* Navigation Action to Alerts Page */}
          <div className="bg-[#0d1322] p-5 rounded-2xl border border-cyan-500/30 bg-cyan-500/5 flex items-center justify-between font-mono">
            <div>
              <h4 className="text-sm font-bold text-slate-100">Ready to Review SOC Alerts</h4>
              <p className="text-xs text-slate-400">
                {result.alerts_created > 0
                  ? `${result.alerts_created} new alert records persisted to database.`
                  : 'Database state updated. Existing alerts ready for review.'}
              </p>
            </div>

            <button
              onClick={() => navigate('/alerts')}
              className="px-5 py-2.5 bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold rounded-xl flex items-center space-x-2 transition text-xs shadow-lg shadow-cyan-500/20 active:scale-95"
            >
              <span>View Alerts Directory</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default DetectionPage;
