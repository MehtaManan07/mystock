import apiClient from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  Product,
  ProductDetail,
  CreateProductDto,
  UpdateProductDto,
} from '../types';

/**
 * Products API functions
 */
export const productsApi = {
  /**
   * Get all products with optional search
   */
  getAll: async (search?: string): Promise<Product[]> => {
    const params = search ? { search } : {};
    const response = await apiClient.get<Product[]>(API_ENDPOINTS.PRODUCTS.BASE, { params });
    return response.data;
  },

  /**
   * Get single product by ID with details (containers + logs)
   */
  getById: async (id: number): Promise<ProductDetail> => {
    const response = await apiClient.get<ProductDetail>(API_ENDPOINTS.PRODUCTS.BY_ID(id));
    return response.data;
  },

  /**
   * Create a new product
   */
  create: async (data: CreateProductDto): Promise<Product> => {
    const response = await apiClient.post<Product>(API_ENDPOINTS.PRODUCTS.BASE, data);
    return response.data;
  },

  /**
   * Create multiple products in bulk
   */
  createBulk: async (data: CreateProductDto[]): Promise<Product[]> => {
    const response = await apiClient.post<Product[]>(API_ENDPOINTS.PRODUCTS.BULK, { data });
    return response.data;
  },

  /**
   * Update a product
   */
  update: async (id: number, data: UpdateProductDto): Promise<Product> => {
    const response = await apiClient.patch<Product>(API_ENDPOINTS.PRODUCTS.BY_ID(id), data);
    return response.data;
  },

  /**
   * Delete a product (soft delete)
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.PRODUCTS.BY_ID(id));
  },
};
