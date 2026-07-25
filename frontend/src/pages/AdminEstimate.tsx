import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { EstimateCalculator } from '../components/EstimateCalculator';
import { formatCurrency } from '../lib/utils';

export function AdminEstimate() {
  const navigate = useNavigate();
  const [appliedTotal, setAppliedTotal] = useState<number | null>(null);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Estimate Calculator</h1>
          <p className="text-sm text-gray-500 mt-1">
            Build a line-item quote without needing to create or edit a job first.
          </p>
        </div>
      </div>

      {appliedTotal !== null && (
        <div className="bg-white rounded-lg shadow p-4 border border-obatek/30 flex items-center justify-between">
          <span className="text-sm font-medium text-gray-700">Estimate</span>
          <span className="text-lg font-bold text-obatek">{formatCurrency(appliedTotal)}</span>
        </div>
      )}

      <div className="bg-white rounded-lg shadow p-6">
        <EstimateCalculator
          onApply={(total) => setAppliedTotal(total)}
          onClose={() => navigate('/admin')}
        />
      </div>
    </div>
  );
}
