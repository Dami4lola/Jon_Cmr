import api from './client';
import type { TimeOffRequest, TimeOffRequestCreate, TimeOffRequestReview } from '../types';

export const timeOffApi = {
  list: async (params?: {
    status_filter?: string;
    worker_id?: number;
  }): Promise<TimeOffRequest[]> => {
    const response = await api.get('/time-off/', { params });
    return response.data;
  },

  create: async (data: TimeOffRequestCreate): Promise<TimeOffRequest> => {
    const response = await api.post('/time-off/', data);
    return response.data;
  },

  review: async (id: number, data: TimeOffRequestReview): Promise<TimeOffRequest> => {
    const response = await api.post(`/time-off/${id}/review`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/time-off/${id}`);
  },
};
