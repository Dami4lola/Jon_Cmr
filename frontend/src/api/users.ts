import api from './client';

export interface UserWithWorker {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  roles: string[];
  created_at: string;
  worker_id: number | null;
  worker_name: string | null;
  hourly_rate: number | null;
  charges_hst: boolean | null;
  is_employee: boolean | null;
}

export interface AdminCreateUserData {
  username: string;
  email: string;
  password: string;
  name: string;
  hourly_rate?: number;
  charges_hst?: boolean;
  is_employee?: boolean;
  roles: string[];
}

export interface UpdateUserRolesData {
  roles: string[];
}

export const usersApi = {
  list: async (): Promise<UserWithWorker[]> => {
    const response = await api.get('/users/');
    return response.data;
  },

  get: async (id: number): Promise<UserWithWorker> => {
    const response = await api.get(`/users/${id}`);
    return response.data;
  },

  create: async (data: AdminCreateUserData): Promise<UserWithWorker> => {
    const response = await api.post('/users/', data);
    return response.data;
  },

  updateRoles: async (id: number, data: UpdateUserRolesData): Promise<UserWithWorker> => {
    const response = await api.put(`/users/${id}/roles`, data);
    return response.data;
  },

  toggleActive: async (id: number): Promise<UserWithWorker> => {
    const response = await api.put(`/users/${id}/toggle-active`);
    return response.data;
  },

  resetPassword: async (id: number, newPassword: string): Promise<{ message: string }> => {
    const response = await api.put(`/users/${id}/reset-password`, { new_password: newPassword });
    return response.data;
  },
};
