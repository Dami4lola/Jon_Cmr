import api from './client';
import type { Worker } from '../types';

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
};
