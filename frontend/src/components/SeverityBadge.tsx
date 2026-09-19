import React from 'react';
import { AlertSeverity } from '../types';

interface SeverityBadgeProps {
  severity: AlertSeverity;
}

export const SeverityBadge: React.FC<SeverityBadgeProps> = ({ severity }) => {
  const getBadgeStyle = () => {
    switch (severity) {
      case 'Critical':
        return 'badge-critical';
      case 'High':
        return 'badge-high';
      case 'Medium':
        return 'badge-medium';
      case 'Low':
        return 'badge-low';
      case 'Informational':
      default:
        return 'badge-info';
    }
  };

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold tracking-wide ${getBadgeStyle()}`}>
      {severity}
    </span>
  );
};
