import apiClient from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  Container,
  ContainerDetail,
  CreateContainerDto,
  UpdateContainerDto,
} from '../types';

/**
 * Containers API functions
 */
export const containersApi = {
  /**
   * Get all containers with optional search
   */
  getAll: async (search?: string): Promise<Container[]> => {
    const params = search ? { search } : {};
    const response = await apiClient.get<Container[]>(API_ENDPOINTS.CONTAINERS.BASE, { params });
    return response.data;
  },

  /**
   * Get single container by ID with details (products + logs)
   */
  getById: async (id: number): Promise<ContainerDetail> => {
    const response = await apiClient.get<ContainerDetail>(API_ENDPOINTS.CONTAINERS.BY_ID(id));
    return response.data;
  },

  /**
   * Create a new container
   */
  create: async (data: CreateContainerDto): Promise<Container> => {
    const response = await apiClient.post<Container>(API_ENDPOINTS.CONTAINERS.BASE, data);
    return response.data;
  },

  /**
   * Create multiple containers in bulk
   */
  createBulk: async (data: CreateContainerDto[]): Promise<Container[]> => {
    const response = await apiClient.post<Container[]>(API_ENDPOINTS.CONTAINERS.BULK, { data });
    return response.data;
  },

  /**
   * Update a container
   */
  update: async (id: number, data: UpdateContainerDto): Promise<Container> => {
    const response = await apiClient.patch<Container>(API_ENDPOINTS.CONTAINERS.BY_ID(id), data);
    return response.data;
  },

  /**
   * Delete a container (soft delete)
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.CONTAINERS.BY_ID(id));
  },
};
