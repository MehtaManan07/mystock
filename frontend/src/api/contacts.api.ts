import apiClient from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  Contact,
  CreateContactDto,
  UpdateContactDto,
  ContactFilters,
} from '../types';

/**
 * Contacts API functions
 */
export const contactsApi = {
  /**
   * Get all contacts with optional filters
   */
  getAll: async (filters?: ContactFilters): Promise<Contact[]> => {
    const params: Record<string, string | string[]> = {};
    
    if (filters?.types && filters.types.length > 0) {
      params.types = filters.types;
    }
    if (filters?.balance) {
      params.balance = filters.balance;
    }
    if (filters?.search) {
      params.search = filters.search;
    }
    
    const response = await apiClient.get<Contact[]>(API_ENDPOINTS.CONTACTS.BASE, { params });
    return response.data;
  },

  /**
   * Get single contact by ID
   */
  getById: async (id: number): Promise<Contact> => {
    const response = await apiClient.get<Contact>(API_ENDPOINTS.CONTACTS.BY_ID(id));
    return response.data;
  },

  /**
   * Create a new contact
   */
  create: async (data: CreateContactDto): Promise<Contact> => {
    const response = await apiClient.post<Contact>(API_ENDPOINTS.CONTACTS.BASE, data);
    return response.data;
  },

  /**
   * Update a contact
   */
  update: async (id: number, data: UpdateContactDto): Promise<Contact> => {
    const response = await apiClient.patch<Contact>(API_ENDPOINTS.CONTACTS.BY_ID(id), data);
    return response.data;
  },

  /**
   * Delete a contact (soft delete)
   */
  delete: async (id: number): Promise<void> => {
    await apiClient.delete(API_ENDPOINTS.CONTACTS.BY_ID(id));
  },
};
