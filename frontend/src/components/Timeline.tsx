import React from 'react';
import { Clock } from 'lucide-react';
import { AlertSeverity, AlertStatus } from '../types';
import { SeverityBadge } from './SeverityBadge';
import { StatusBadge } from './StatusBadge';

export interface TimelineEvent {
  id: string;
  timestamp: string;
  attack_type: string;
  severity: AlertSeverity;
  status: AlertStatus;
  source_ip: string;
  destination_ip: string;
  destination_port: number;
}

interface TimelineProps {
  events: TimelineEvent[];
}

export const Timeline: React.FC<TimelineProps> = ({ events }) => {
  if (!events || events.length === 0) {
    return (
      <div className="py-8 text-center text-slate-500 text-xs font-mono">
        No event timestamps available for timeline visualization.
      </div>
    );
  }

  // Sort events chronologically ascending
  const sortedEvents = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );

  return (
    <div className="relative pl-6 border-l-2 border-slate-800 space-y-6 font-mono text-xs my-2">
      {sortedEvents.map((evt, idx) => (
        <div key={evt.id || idx} className="relative group">
          {/* Timeline Dot */}
          <div className="absolute -left-[31px] top-1.5 w-3.5 h-3.5 rounded-full bg-cyan-500 border-2 border-[#090d16] group-hover:scale-125 transition"></div>

          <div className="p-3.5 bg-slate-900/80 rounded-xl border border-slate-800/90 space-y-2 hover:border-slate-700 transition">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800/60 pb-2">
              <div className="flex items-center space-x-2">
                <Clock className="w-3.5 h-3.5 text-cyan-400" />
                <span className="text-slate-300 font-bold">
                  {new Date(evt.timestamp).toLocaleString()}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <SeverityBadge severity={evt.severity} />
                <StatusBadge status={evt.status} />
              </div>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <span className="text-slate-100 font-bold text-sm">{evt.attack_type}</span>
                <p className="text-slate-400 text-[11px] mt-0.5">
                  Flow: <code className="text-cyan-300">{evt.source_ip}</code> &rarr;{' '}
                  <code className="text-cyan-300">{evt.destination_ip}:{evt.destination_port}</code>
                </p>
              </div>
              <span className="text-slate-500 text-[10px]">Step #{idx + 1}</span>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
};
