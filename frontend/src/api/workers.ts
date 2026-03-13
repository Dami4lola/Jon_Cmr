import api from './client';
import type { Worker } from '../types';

export interface WorkerUpdate {
  name?: string;
  hourly_rate?: number;
  charges_hst?: boolean;
  is_employee?: boolean;
}

export const workersApi = {
  list: async (): Promise<Worker[]> => {
    const response = await api.get('/workers/');
    return response.data;
  },

  get: async (id: number): Promise<Worker> => {
    const response = await api.get(`/workers/${id}`);
    return response.data;
  },

  me: async (): Promise<Worker> => {
    const response = await api.get('/workers/me');
    return response.data;
  },

  update: async (id: number, data: WorkerUpdate): Promise<Worker> => {
    const response = await api.put(`/workers/${id}`, data);
    return response.data;
  },
};
