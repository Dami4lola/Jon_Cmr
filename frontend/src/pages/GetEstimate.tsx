import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery } from '@tanstack/react-query';
import { estimatesApi } from '../api/estimates';
import { formatCurrency } from '../lib/utils';
import type { QuickQuoteResponse } from '../types';

// Fallback shown while /estimates/job-types loads, or if that request fails.
const FALLBACK_JOB_TYPES = [{ value: 'general', label: 'General / Other' }];

export function GetEstimate() {
  const { data: jobTypes = FALLBACK_JOB_TYPES } = useQuery({
    queryKey: ['job-types'],
    queryFn: estimatesApi.listJobTypes,
    staleTime: 60 * 60 * 1000,
  });

  const [jobType, setJobType] = useState('general');
  const [address, setAddress] = useState('');
  const [areaSqft, setAreaSqft] = useState('');
  const [quote, setQuote] = useState<QuickQuoteResponse | null>(null);

  const quoteMutation = useMutation({
    mutationFn: () =>
      estimatesApi.quickQuote({
        job_type: jobType,
        address,
        area_sqft: parseFloat(areaSqft),
      }),
    onSuccess: (data) => setQuote(data),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setQuote(null);
    if (!address.trim() || !areaSqft || parseFloat(areaSqft) <= 0) return;
    quoteMutation.mutate();
  };

  const handleStartOver = () => {
    setQuote(null);
    quoteMutation.reset();
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-obatek to-obatek-dark flex flex-col items-center justify-center p-4">
      <div className="text-center text-white mb-8">
        <h1 className="text-4xl font-bold mb-2">Get a Free Estimate</h1>
        <p className="text-white/80">Tell us about the job and get an instant rough quote</p>
      </div>

      <div className="bg-white rounded-lg shadow-xl p-8 max-w-lg w-full">
        {!quote ? (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type of Work</label>
              <select
                value={jobType}
                onChange={(e) => setJobType(e.target.value)}
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
              >
                {jobTypes.map((jt) => (
                  <option key={jt.value} value={jt.value}>
                    {jt.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Job Address</label>
              <input
                type="text"
                value={address}
                onChange={(e) => setAddress(e.target.value)}
                placeholder="Street address, city, province"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Size of Area Being Worked On (sq ft)
              </label>
              <input
                type="number"
                min="1"
                step="1"
                value={areaSqft}
                onChange={(e) => setAreaSqft(e.target.value)}
                placeholder="e.g. 300"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-obatek focus:border-transparent outline-none"
                required
              />
            </div>

            {quoteMutation.isError && (
              <div className="bg-red-50 border border-red-200 rounded-lg p-3">
                <p className="text-red-800 text-sm">
                  {(quoteMutation.error as any)?.response?.data?.detail ||
                    'Could not calculate an estimate. Please check the address and try again.'}
                </p>
              </div>
            )}

            <button
              type="submit"
              disabled={quoteMutation.isPending || !address.trim() || !areaSqft}
              className="w-full bg-obatek text-white text-center py-3 px-4 rounded-lg font-medium hover:bg-obatek-dark transition-colors disabled:opacity-50"
            >
              {quoteMutation.isPending ? 'Calculating...' : 'Get Estimate'}
            </button>
          </form>
        ) : (
          <div className="space-y-4">
            <div>
              <h2 className="text-xl font-semibold text-gray-800">Your Estimate</h2>
              <p className="text-sm text-gray-500">{quote.job_type_label}</p>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">Estimated labour ({quote.estimated_hours} hrs)</span>
                <span className="font-medium">{formatCurrency(quote.labour_amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Travel</span>
                <span className="font-medium">
                  {quote.distance_km != null
                    ? formatCurrency(quote.travel_amount)
                    : 'Confirmed at booking'}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Materials</span>
                <span className="font-medium">{formatCurrency(quote.materials_amount)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Admin fee</span>
                <span className="font-medium">{formatCurrency(quote.admin_fee)}</span>
              </div>
              <div className="flex justify-between border-t pt-2">
                <span className="text-gray-600">Subtotal</span>
                <span className="font-medium">{formatCurrency(quote.subtotal)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">HST</span>
                <span className="font-medium">{formatCurrency(quote.hst_amount)}</span>
              </div>
              <div className="flex justify-between border-t pt-2 text-lg font-bold text-obatek">
                <span>Estimated Total</span>
                <span>{formatCurrency(quote.total)}</span>
              </div>
            </div>

            <p className="text-xs text-gray-500 bg-gray-50 rounded-lg p-3">{quote.disclaimer}</p>

            <button
              onClick={handleStartOver}
              className="w-full border-2 border-obatek text-obatek text-center py-2 px-4 rounded-lg font-medium hover:bg-obatek/5 transition-colors"
            >
              Start Over
            </button>
          </div>
        )}
      </div>

      <Link to="/" className="text-white/70 hover:text-white text-sm mt-8">
        Back to home
      </Link>
    </div>
  );
}
