import api from './client';
import type { JobFinancialsDetail, JobFinancialsListResponse } from '../types';

export const financialsApi = {
  listJobs: async (params?: {
    completed?: boolean;
    client_id?: number;
    start_date?: string;
    end_date?: string;
    has_timesheets_only?: boolean;
    skip?: number;
    limit?: number;
  }): Promise<JobFinancialsListResponse> => {
    const response = await api.get('/financials/jobs', { params });
    return response.data;
  },

  getJob: async (jobId: number): Promise<JobFinancialsDetail> => {
    const response = await api.get(`/financials/jobs/${jobId}`);
    return response.data;
  },
};
