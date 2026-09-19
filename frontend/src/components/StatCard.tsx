import React from 'react';
import { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: LucideIcon;
  colorClass?: string;
  loading?: boolean;
}

export const StatCard: React.FC<StatCardProps> = ({
  title,
  value,
  subtitle,
  icon: Icon,
  colorClass = 'text-cyan-400 bg-cyan-500/10 border-cyan-500/20',
  loading = false,
}) => {
  return (
    <div className="soc-card p-5 border border-slate-800 flex items-center justify-between">
      <div>
        <p className="text-xs uppercase tracking-wider text-slate-400 font-semibold mb-1">{title}</p>
        {loading ? (
          <div className="h-8 w-20 bg-slate-800 animate-pulse rounded my-1"></div>
        ) : (
          <h3 className="text-2xl font-bold text-slate-100 font-mono tracking-tight">{value}</h3>
        )}
        {subtitle && <p className="text-xs text-slate-500 mt-1">{subtitle}</p>}
      </div>
      <div className={`p-3 rounded-lg border ${colorClass}`}>
        <Icon className="w-6 h-6" />
      </div>
    </div>
  );
};
