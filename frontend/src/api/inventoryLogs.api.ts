import api from './axios';
import { API_ENDPOINTS } from '../constants';
import type { InventoryLog, CreateInventoryLogDto } from '../types';

/**
 * Inventory Logs API
 * Handles inventory audit trail and logging
 */
export const inventoryLogsApi = {
  /**
   * Get all inventory logs
   */
  getAll: async (): Promise<InventoryLog[]> => {
    const response = await api.get(API_ENDPOINTS.INVENTORY_LOGS.BASE);
    return response.data;
  },

  /**
   * Get inventory logs for a specific product
   */
  getByProduct: async (productId: number): Promise<InventoryLog[]> => {
    const response = await api.get(API_ENDPOINTS.INVENTORY_LOGS.BY_PRODUCT(productId));
    return response.data;
  },

  /**
   * Get inventory logs for a specific container
   */
  getByContainer: async (containerId: number): Promise<InventoryLog[]> => {
    const response = await api.get(API_ENDPOINTS.INVENTORY_LOGS.BY_CONTAINER(containerId));
    return response.data;
  },

  /**
   * Create a single inventory log
   */
  create: async (data: CreateInventoryLogDto): Promise<InventoryLog> => {
    const response = await api.post(API_ENDPOINTS.INVENTORY_LOGS.BASE, data);
    return response.data;
  },

  /**
   * Create multiple inventory logs in bulk
   */
  createBulk: async (data: CreateInventoryLogDto[]): Promise<InventoryLog[]> => {
    const response = await api.post(API_ENDPOINTS.INVENTORY_LOGS.BULK, { data });
    return response.data;
  },
};
