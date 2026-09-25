import React, { useEffect, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  ShieldAlert,
  LayoutDashboard,
  UploadCloud,
  Bell,
  Radio,
  BookOpen,
  Server,
  RefreshCw,
  Clock,
  Terminal,
  Activity,
  LogOut,
  UserCheck,
} from 'lucide-react';
import { api } from '../services/api';
import { useAuth } from '../context/AuthContext';

export const RootLayout: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [lastRefreshed, setLastRefreshed] = useState<string>('');
  const [checking, setChecking] = useState<boolean>(false);

  const checkStatus = async () => {
    setChecking(true);
    try {
      const res = await api.getHealth();
      setBackendOnline(res.status === 'ok');
      setLastRefreshed(new Date().toLocaleTimeString());
    } catch {
      setBackendOnline(false);
      setLastRefreshed(new Date().toLocaleTimeString());
    } finally {
      setChecking(false);
    }
  };

  useEffect(() => {
    checkStatus();
    const interval = setInterval(checkStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const navItems = [
    { path: '/dashboard', label: 'Overview', icon: LayoutDashboard },
    { path: '/detection', label: 'Detection Center', icon: UploadCloud },
    { path: '/alerts', label: 'Alerts', icon: Bell },
    { path: '/incidents', label: 'Incidents', icon: Radio },
    { path: '/knowledge-base', label: 'Knowledge Base', icon: BookOpen },
    { path: '/system', label: 'System Status', icon: Server },
  ];

  const getPageTitle = () => {
    if (location.pathname.startsWith('/dashboard')) return 'Executive Security Overview';
    if (location.pathname.startsWith('/detection')) return 'IDS Flow Detection Center';
    if (location.pathname.startsWith('/alerts')) return 'Security Alert Directory';
    if (location.pathname.startsWith('/incidents')) return 'Correlated Incident Campaigns';
    if (location.pathname.startsWith('/knowledge-base')) return 'Cyber Threat Knowledge Search';
    if (location.pathname.startsWith('/system')) return 'System Readiness & Diagnostics';
    return 'Security Operations Center';
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col md:flex-row font-sans">
      {/* Sidebar */}
      <aside className="w-full md:w-64 bg-[#0d1322] border-b md:border-b-0 md:border-r border-slate-800/80 flex-shrink-0 flex flex-col justify-between">
        <div>
          {/* Brand Header */}
          <div className="p-5 border-b border-slate-800/80 flex items-center space-x-3">
            <div className="p-2.5 bg-rose-500/10 border border-rose-500/30 rounded-xl text-rose-500 shadow-md">
              <ShieldAlert className="w-6 h-6" />
            </div>
            <div>
              <h1 className="font-bold text-sm tracking-wider text-slate-100 uppercase font-mono">AI SOC</h1>
              <p className="text-[10px] text-slate-400 font-mono">Security Operations Center</p>
            </div>
          </div>

          {/* Navigation Links */}
          <nav className="p-3 space-y-1">
            <div className="px-3 py-2 text-[10px] uppercase font-mono tracking-widest text-slate-500 font-semibold">
              Operational Views
            </div>
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.path}
                  to={item.path}
                  className={({ isActive }) =>
                    `flex items-center space-x-3 px-3.5 py-2.5 rounded-lg text-xs font-mono font-medium transition-all ${
                      isActive
                        ? 'bg-cyan-500/10 text-cyan-400 border border-cyan-500/30 font-bold shadow-sm'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800/50'
                    }`
                  }
                >
                  <Icon className="w-4 h-4" />
                  <span>{item.label}</span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer Status */}
        <div className="p-4 border-t border-slate-800/80 text-xs text-slate-500 font-mono space-y-2">
          <div className="flex items-center justify-between">
            <span className="flex items-center space-x-1.5">
              <Terminal className="w-3.5 h-3.5 text-slate-400" />
              <span>Backend Status</span>
            </span>
            <span
              className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold ${
                backendOnline === true
                  ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/30'
                  : backendOnline === false
                  ? 'bg-rose-500/15 text-rose-400 border border-rose-500/30'
                  : 'bg-slate-800 text-slate-400'
              }`}
            >
              {backendOnline === true ? 'ONLINE' : backendOnline === false ? 'OFFLINE' : 'CHECKING'}
            </span>
          </div>
          <p className="text-[10px] text-slate-600">AI-SOC-RAG Stage 10 • Authenticated</p>
        </div>
      </aside>

      {/* Main Body */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Top Header */}
        <header className="h-16 bg-[#0d1322]/90 backdrop-blur-md border-b border-slate-800/80 px-6 flex items-center justify-between sticky top-0 z-20">
          <div className="flex items-center space-x-3">
            <Activity className="w-5 h-5 text-cyan-400" />
            <div>
              <h2 className="text-sm font-bold text-slate-200 font-mono tracking-tight">{getPageTitle()}</h2>
              <p className="text-[10px] text-slate-500 font-mono hidden sm:block">AI SOC Security Operations Center</p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Authenticated User Identity */}
            {user && (
              <div className="flex items-center space-x-2 text-xs font-mono bg-slate-900/90 px-3 py-1.5 rounded-lg border border-slate-800">
                <UserCheck className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-200 font-bold">{user.username}</span>
                <span
                  className={`px-1.5 py-0.2 rounded text-[10px] font-bold ${
                    user.role === 'ADMIN'
                      ? 'bg-purple-500/15 text-purple-300 border border-purple-500/30'
                      : 'bg-blue-500/15 text-blue-300 border border-blue-500/30'
                  }`}
                >
                  {user.role}
                </span>
              </div>
            )}

            {lastRefreshed && (
              <div className="hidden xl:flex items-center space-x-1.5 text-[11px] font-mono text-slate-400 bg-slate-900/80 px-2.5 py-1 rounded border border-slate-800">
                <Clock className="w-3 h-3 text-slate-500" />
                <span>Last refresh: {lastRefreshed}</span>
              </div>
            )}

            <button
              onClick={checkStatus}
              disabled={checking}
              title="Refresh backend status"
              className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg border border-slate-700 transition"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${checking ? 'animate-spin' : ''}`} />
            </button>

            <button
              onClick={handleLogout}
              title="Sign Out"
              className="flex items-center space-x-1.5 px-3 py-1.5 bg-rose-500/10 hover:bg-rose-500/20 text-rose-400 font-mono text-xs rounded-lg border border-rose-500/30 transition"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 p-6 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
