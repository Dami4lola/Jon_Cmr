import api from './client';
import type { Client } from '../types';

export interface ClientCreate {
  name: string;
  phone_number?: string;
  email?: string;
  address: string;
}

export const clientsApi = {
  list: async (): Promise<Client[]> => {
    const response = await api.get('/clients/');
    return response.data;
  },

  get: async (id: number): Promise<Client> => {
    const response = await api.get(`/clients/${id}`);
    return response.data;
  },

  create: async (data: ClientCreate): Promise<Client> => {
    const response = await api.post('/clients/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<ClientCreate>): Promise<Client> => {
    const response = await api.put(`/clients/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/clients/${id}`);
  },
};
