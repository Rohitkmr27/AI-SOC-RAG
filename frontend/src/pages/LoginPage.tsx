import React, { useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { ShieldAlert, Lock, User as UserIcon, LogIn } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { formatApiError } from '../utils/error';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const { login, isAuthenticated } = useAuth();

  const [username, setUsername] = useState<string>('');
  const [password, setPassword] = useState<string>('');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const from = (location.state as any)?.from?.pathname || '/dashboard';

  if (isAuthenticated) {
    navigate(from, { replace: true });
    return null;
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password.trim()) {
      setError('Please enter both username/email and password.');
      return;
    }

    setLoading(true);
    setError(null);
    try {
      await login(username.trim(), password.trim());
      navigate(from, { replace: true });
    } catch (err: unknown) {
      setError(formatApiError(err, 'Authentication failed. Please check your credentials.'));
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#090d16] flex items-center justify-center p-4 font-mono text-xs">
      <div className="w-full max-w-md space-y-6">
        {/* Brand Header */}
        <div className="text-center space-y-3">
          <div className="inline-flex p-3 bg-rose-500/10 border border-rose-500/30 rounded-2xl text-rose-500 shadow-xl">
            <ShieldAlert className="w-10 h-10" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-slate-100 tracking-wider uppercase">AI-SOC Engine</h1>
            <p className="text-slate-400 mt-1">Security Operations Center • Restricted Access</p>
          </div>
        </div>

        {/* Login Card */}
        <div className="soc-card p-6 border border-slate-800 space-y-5 bg-slate-900/90 shadow-2xl">
          <div className="border-b border-slate-800 pb-3 flex items-center space-x-2 text-slate-200 font-bold">
            <LogIn className="w-4 h-4 text-cyan-400" />
            <span>Analyst Authentication</span>
          </div>

          {error && (
            <div className="p-3.5 bg-rose-500/10 border border-rose-500/30 text-rose-400 rounded-lg text-xs leading-relaxed">
              {error}
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-slate-400 mb-1 font-semibold uppercase">Username or Email</label>
              <div className="relative">
                <UserIcon className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="text"
                  placeholder="admin or analyst"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <div>
              <label className="block text-slate-400 mb-1 font-semibold uppercase">Password</label>
              <div className="relative">
                <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
                <input
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-9 pr-3 py-2.5 bg-slate-950 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full py-3 bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-bold rounded-lg shadow-lg transition disabled:opacity-50 flex items-center justify-center space-x-2"
            >
              <LogIn className="w-4 h-4" />
              <span>{loading ? 'Authenticating...' : 'Sign In to SOC Dashboard'}</span>
            </button>
          </form>
        </div>

        {/* Security Notice */}
        <div className="text-center text-[10px] text-slate-600 leading-relaxed">
          Authorized security personnel only. All access attempts are logged and monitored.
        </div>
      </div>
    </div>
  );
};
