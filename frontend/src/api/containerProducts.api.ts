import api from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  ContainerProduct,
  SetProductsDto,
  TotalQuantityResponse,
  InventoryAnalytics,
} from '../types';

/**
 * Container Products API
 * Handles inventory management between containers and products
 */
export const containerProductsApi = {
  /**
   * Set products in a container with quantities
   * Creates new, updates existing, or soft-deletes (qty=0) container-product relationships
   */
  setProducts: async (data: SetProductsDto): Promise<{ message: string }> => {
    const response = await api.post(API_ENDPOINTS.CONTAINER_PRODUCTS.SET_PRODUCTS, data);
    return response.data;
  },

  /**
   * Get all products in a specific container
   */
  getProductsInContainer: async (containerId: number): Promise<ContainerProduct[]> => {
    const response = await api.get(API_ENDPOINTS.CONTAINER_PRODUCTS.BY_CONTAINER(containerId));
    return response.data;
  },

  /**
   * Get all containers that have a specific product
   */
  getContainersForProduct: async (productId: number): Promise<ContainerProduct[]> => {
    const response = await api.get(API_ENDPOINTS.CONTAINER_PRODUCTS.BY_PRODUCT(productId));
    return response.data;
  },

  /**
   * Search for containers by product name/SKU
   */
  searchBySku: async (sku: string): Promise<ContainerProduct[]> => {
    const response = await api.get(API_ENDPOINTS.CONTAINER_PRODUCTS.SEARCH, {
      params: { sku },
    });
    return response.data;
  },

  /**
   * Get total quantity of a product across all containers
   */
  getTotalQuantity: async (productId: number): Promise<TotalQuantityResponse> => {
    const response = await api.get(API_ENDPOINTS.CONTAINER_PRODUCTS.TOTAL_QUANTITY(productId));
    return response.data;
  },

  /**
   * Get basic inventory analytics
   */
  getAnalytics: async (): Promise<InventoryAnalytics> => {
    const response = await api.get(API_ENDPOINTS.CONTAINER_PRODUCTS.ANALYTICS);
    return response.data;
  },
};
