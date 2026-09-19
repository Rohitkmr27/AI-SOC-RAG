import React from 'react';
import { AlertStatus } from '../types';

interface StatusBadgeProps {
  status: AlertStatus;
}

export const StatusBadge: React.FC<StatusBadgeProps> = ({ status }) => {
  const getBadgeStyle = () => {
    switch (status) {
      case 'NEW':
        return 'status-new';
      case 'TRIAGED':
        return 'status-triaged';
      case 'INVESTIGATING':
        return 'status-investigating';
      case 'RESOLVED':
        return 'status-resolved';
      default:
        return 'bg-slate-800 text-slate-300 border border-slate-700';
    }
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wider ${getBadgeStyle()}`}>
      {status}
    </span>
  );
};
