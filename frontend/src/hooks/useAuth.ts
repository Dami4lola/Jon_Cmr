import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { useAuthStore } from '../store/authStore';
import type { LoginCredentials, RegisterData } from '../types';

export function useAuth() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { login, logout, isAuthenticated, user, token } = useAuthStore();

  // Fetch current user
  const { data: currentUser, isLoading: isLoadingUser } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: authApi.me,
    enabled: isAuthenticated && !!token,
    staleTime: 1000 * 60 * 5,
  });

  // Login mutation - needs to fetch user after getting token
  const loginMutation = useMutation({
    mutationFn: async (credentials: LoginCredentials) => {
      const tokenData = await authApi.login(credentials);
      // Store token temporarily to make the /me request
      localStorage.setItem('access_token', tokenData.access_token);
      // Fetch user data
      const userData = await authApi.me();
      return { token: tokenData.access_token, user: userData };
    },
    onSuccess: (data) => {
      login(data.token, data.user);
      queryClient.invalidateQueries({ queryKey: ['auth'] });
      navigate('/dashboard');
    },
    onError: () => {
      localStorage.removeItem('access_token');
    },
  });

  // Register mutation - user is included in response
  const registerMutation = useMutation({
    mutationFn: authApi.register,
    onSuccess: (data) => {
      login(data.access_token, data.user);
      queryClient.invalidateQueries({ queryKey: ['auth'] });
      navigate('/dashboard');
    },
  });

  // Logout handler
  const handleLogout = () => {
    logout();
    queryClient.clear();
    navigate('/login');
  };

  return {
    user: currentUser || user,
    isAuthenticated,
    isLoading: isLoadingUser,
    login: (credentials: LoginCredentials) => loginMutation.mutateAsync(credentials),
    register: (data: RegisterData) => registerMutation.mutateAsync(data),
    logout: handleLogout,
    loginError: loginMutation.error,
    registerError: registerMutation.error,
    isLoggingIn: loginMutation.isPending,
    isRegistering: registerMutation.isPending,
  };
}
