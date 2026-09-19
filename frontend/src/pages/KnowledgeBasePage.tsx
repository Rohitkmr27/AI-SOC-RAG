import React, { useState } from 'react';
import { BookOpen, Search, Sparkles, FileText, Database } from 'lucide-react';
import { api } from '../services/api';
import { RAGQueryResponse } from '../types';
import { formatApiError } from '../utils/error';
import { ErrorBanner } from '../components/ErrorBanner';

export const KnowledgeBasePage: React.FC = () => {
  const [query, setQuery] = useState<string>('What is a brute force attack?');
  const [topK, setTopK] = useState<number>(5);

  const [result, setResult] = useState<RAGQueryResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setLoading(true);
    setError(null);
    try {
      const res = await api.queryRAG({
        query: query.trim(),
        top_k: topK,
      });
      setResult(res);
    } catch (err: unknown) {
      setError(formatApiError(err, 'Failed to execute RAG knowledge base search.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6 font-mono text-xs">
      {/* Header */}
      <div className="bg-slate-900/60 p-4 rounded-xl border border-slate-800">
        <h2 className="text-base font-bold text-slate-100">Cybersecurity Threat Intelligence Search</h2>
        <p className="text-xs text-slate-400">Semantic retrieval (Qdrant + all-MiniLM-L6-v2) & Gemini grounded generation</p>
      </div>

      {/* Search Input Card */}
      <div className="soc-card p-5 border border-slate-800 space-y-4">
        <form onSubmit={handleSearch} className="space-y-4">
          <div className="flex flex-col sm:flex-row gap-3">
            <div className="relative flex-1">
              <Search className="w-4 h-4 text-slate-400 absolute left-3.5 top-3" />
              <input
                type="text"
                placeholder="Ask a cybersecurity question (e.g. What is a brute force attack?)"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-100 font-mono placeholder-slate-500 focus:outline-none focus:border-cyan-500"
              />
            </div>

            <div className="flex items-center space-x-2">
              <span className="text-slate-400">Top-K:</span>
              <select
                value={topK}
                onChange={(e) => setTopK(Number(e.target.value))}
                className="bg-slate-900 border border-slate-700 text-xs font-mono text-slate-200 rounded-lg px-2.5 py-2.5 focus:outline-none focus:border-cyan-500"
              >
                <option value={3}>3 Chunks</option>
                <option value={5}>5 Chunks</option>
                <option value={8}>8 Chunks</option>
              </select>

              <button
                type="submit"
                disabled={loading || !query.trim()}
                className="px-5 py-2.5 bg-cyan-600 hover:bg-cyan-500 text-white font-semibold rounded-lg transition disabled:opacity-50 flex items-center space-x-2"
              >
                <Sparkles className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
                <span>{loading ? 'Searching...' : 'Ask RAG'}</span>
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Error Banner */}
      {error && <ErrorBanner message={error} />}

      {/* Results Display */}
      {result && (
        <div className="space-y-6">
          {/* Grounded Answer */}
          <div className="soc-card p-6 border border-cyan-500/30 bg-cyan-950/10 space-y-3">
            <div className="flex items-center space-x-2 border-b border-cyan-500/20 pb-2">
              <BookOpen className="w-5 h-5 text-cyan-400" />
              <h3 className="text-sm font-bold text-cyan-200">Grounded Knowledge Base Answer</h3>
            </div>
            <p className="text-slate-200 leading-relaxed bg-slate-900/90 p-4 rounded-lg border border-slate-800">
              {result.answer}
            </p>
          </div>

          {/* Sources List */}
          <div className="soc-card p-5 border border-slate-800 space-y-3">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-300">
              Retrieved Knowledge Sources ({result.sources.length})
            </h3>

            {result.sources.length === 0 ? (
              <p className="text-slate-500 py-4">No matching chunks retrieved from Qdrant knowledge base.</p>
            ) : (
              <div className="space-y-3">
                {result.sources.map((src, i) => (
                  <div key={i} className="p-4 bg-slate-900/80 rounded-lg border border-slate-800 space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="text-slate-200 font-bold">{src.title || src.file_name}</span>
                      <span className="px-2.5 py-0.5 bg-cyan-500/10 text-cyan-400 rounded border border-cyan-500/30 text-[11px] font-bold">
                        {(src.score * 100).toFixed(1)}% Match
                      </span>
                    </div>
                    <p className="text-slate-400 text-[11px] truncate">Source Path: {src.source}</p>
                    <p className="text-slate-500 text-[10px]">Document ID: {src.document_id} • Chunk ID: {src.chunk_id}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
