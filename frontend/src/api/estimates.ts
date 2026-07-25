import api from './client';
import type {
  JobTypeOption,
  JobTypeRate,
  JobTypeRateUpdate,
  QuickQuoteRequest,
  QuickQuoteResponse,
  QuickQuoteRates,
  DistancePreviewResponse,
} from '../types';

export const estimatesApi = {
  // Public - no auth required. Powers the customer-facing quick estimate form.
  listJobTypes: async (): Promise<JobTypeOption[]> => {
    const response = await api.get('/estimates/job-types');
    return response.data;
  },

  quickQuote: async (data: QuickQuoteRequest): Promise<QuickQuoteResponse> => {
    const response = await api.post('/estimates/quick-quote', data);
    return response.data;
  },

  // Manager-only: current rates behind both invoices and the quick quote
  getRates: async (): Promise<QuickQuoteRates> => {
    const response = await api.get('/estimates/quick-quote-rates');
    return response.data;
  },

  updateJobTypeRate: async (jobType: string, data: JobTypeRateUpdate): Promise<JobTypeRate> => {
    const response = await api.put(`/estimates/quick-quote-rates/${jobType}`, data);
    return response.data;
  },

  updateAdminFee: async (adminFee: number): Promise<QuickQuoteRates> => {
    const response = await api.put('/estimates/quick-quote-admin-fee', { admin_fee: adminFee });
    return response.data;
  },

  // Manager-only: preview round-trip travel km for an address before a job exists
  distancePreview: async (address: string): Promise<DistancePreviewResponse> => {
    const response = await api.post('/estimates/distance-preview', { address });
    return response.data;
  },
};
