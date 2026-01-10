import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { authApi } from '../api/auth.api';
import { useAuthStore } from '../stores/authStore';
import { QUERY_KEYS } from '../constants';
import type { LoginRequest, RegisterRequest } from '../types';

/**
 * Hook to get current user data
 * Only fetches if user is authenticated
 */
export const useCurrentUser = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery({
    queryKey: QUERY_KEYS.CURRENT_USER,
    queryFn: authApi.getCurrentUser,
    enabled: isAuthenticated,
    staleTime: 5 * 60 * 1000, // 5 minutes
    retry: false,
  });
};

/**
 * Hook to login user
 */
export const useLogin = () => {
  const setAuth = useAuthStore((state) => state.setAuth);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: LoginRequest) => authApi.login(data),
    onSuccess: (response) => {
      // Store token and user in Zustand
      setAuth(response.token.access_token, response.user);
      
      // Set user in React Query cache
      queryClient.setQueryData(QUERY_KEYS.CURRENT_USER, response.user);
    },
  });
};

/**
 * Hook to register new user
 */
export const useRegister = () => {
  const setAuth = useAuthStore((state) => state.setAuth);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: RegisterRequest) => authApi.register(data),
    onSuccess: (response) => {
      // Store token and user in Zustand
      setAuth(response.token.access_token, response.user);
      
      // Set user in React Query cache
      queryClient.setQueryData(QUERY_KEYS.CURRENT_USER, response.user);
    },
  });
};

/**
 * Hook to logout user
 */
export const useLogout = () => {
  const logout = useAuthStore((state) => state.logout);
  const queryClient = useQueryClient();

  return () => {
    // Clear auth state
    logout();
    
    // Clear all cached queries
    queryClient.clear();
  };
};
