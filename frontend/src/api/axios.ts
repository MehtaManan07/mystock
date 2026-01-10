import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios';
import { API_BASE_URL } from '../constants';
import { useAuthStore } from '../stores/authStore';

// Create axios instance with base configuration
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000, // 30 seconds
});

// Request interceptor - Add auth token to all requests
apiClient.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = useAuthStore.getState().token;
    
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle errors globally
apiClient.interceptors.response.use(
  (response) => {
    // Extract data from wrapped response if present
    // Backend wraps responses in { success: true, data: ... }
    if (response.data && response.data.success !== undefined) {
      return { ...response, data: response.data.data };
    }
    return response;
  },
  (error: AxiosError<{ detail: string }>) => {
    // Handle 401 Unauthorized - logout user
    if (error.response?.status === 401) {
      const { logout } = useAuthStore.getState();
      logout();
      
      // Redirect to login if not already there
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }

    // Extract error message from response
    const message = error.response?.data?.detail || error.message || 'An error occurred';
    
    // Create a more useful error object
    const enhancedError = {
      ...error,
      message,
      statusCode: error.response?.status,
    };

    return Promise.reject(enhancedError);
  }
);

export default apiClient;
