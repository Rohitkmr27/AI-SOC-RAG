import React from 'react';

interface RiskGaugeProps {
  score: number; // 0 to 100
  showLabel?: boolean;
}

export const RiskGauge: React.FC<RiskGaugeProps> = ({ score, showLabel = true }) => {
  const clampedScore = Math.min(100, Math.max(0, score));

  const getColorClass = () => {
    if (clampedScore >= 75) return 'text-rose-500 bg-rose-500/10 border-rose-500/30';
    if (clampedScore >= 50) return 'text-amber-500 bg-amber-500/10 border-amber-500/30';
    if (clampedScore >= 25) return 'text-yellow-500 bg-yellow-500/10 border-yellow-500/30';
    return 'text-blue-400 bg-blue-500/10 border-blue-500/30';
  };

  return (
    <div className="inline-flex items-center space-x-2">
      <div className={`px-2.5 py-1 rounded-md text-sm font-bold border ${getColorClass()}`}>
        {clampedScore} / 100
      </div>
      {showLabel && (
        <span className="text-xs text-slate-400 uppercase font-mono tracking-wider">
          {clampedScore >= 75 ? 'Critical Risk' : clampedScore >= 50 ? 'High Risk' : clampedScore >= 25 ? 'Medium Risk' : 'Low Risk'}
        </span>
      )}
    </div>
  );
};
