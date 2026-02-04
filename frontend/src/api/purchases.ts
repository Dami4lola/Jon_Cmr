import api from './client';
import type { PurchaseItem, PurchaseItemCreate } from '../types';

export const purchasesApi = {
  list: async (params?: {
    skip?: number;
    limit?: number;
    is_purchased?: boolean;
  }): Promise<PurchaseItem[]> => {
    const response = await api.get('/purchases/', { params });
    return response.data;
  },

  get: async (id: number): Promise<PurchaseItem> => {
    const response = await api.get(`/purchases/${id}`);
    return response.data;
  },

  create: async (data: PurchaseItemCreate): Promise<PurchaseItem> => {
    const response = await api.post('/purchases/', data);
    return response.data;
  },

  update: async (id: number, data: Partial<PurchaseItemCreate>): Promise<PurchaseItem> => {
    const response = await api.put(`/purchases/${id}`, data);
    return response.data;
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/purchases/${id}`);
  },

  markPurchased: async (id: number): Promise<PurchaseItem> => {
    const response = await api.put(`/purchases/${id}/purchased`);
    return response.data;
  },

  markNotPurchased: async (id: number): Promise<PurchaseItem> => {
    const response = await api.put(`/purchases/${id}/not-purchased`);
    return response.data;
  },
};
