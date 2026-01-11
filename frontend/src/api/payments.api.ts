import api from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  Payment,
  CreatePaymentDto,
  UpdatePaymentDto,
  PaymentFilters,
  PaymentSummary,
  SuggestedCategories,
} from '../types';

/**
 * Payments API
 * Handles manual payments (income/expense) management
 */
export const paymentsApi = {
  /**
   * Get all payments with optional filters
   */
  getAll: async (filters?: PaymentFilters): Promise<Payment[]> => {
    const params: Record<string, string | number | boolean | undefined> = {};
    
    if (filters?.type) params.type = filters.type;
    if (filters?.category) params.category = filters.category;
    if (filters?.payment_method) params.payment_method = filters.payment_method;
    if (filters?.contact_id) params.contact_id = filters.contact_id;
    if (filters?.transaction_id) params.transaction_id = filters.transaction_id;
    if (filters?.from_date) params.from_date = filters.from_date;
    if (filters?.to_date) params.to_date = filters.to_date;
    if (filters?.search) params.search = filters.search;
    if (filters?.min_amount) params.min_amount = filters.min_amount;
    if (filters?.max_amount) params.max_amount = filters.max_amount;
    if (filters?.manual_only) params.manual_only = filters.manual_only;

    const response = await api.get(API_ENDPOINTS.PAYMENTS.BASE, { params });
    return response.data;
  },

  /**
   * Get a single payment by ID
   */
  getById: async (id: number): Promise<Payment> => {
    const response = await api.get(API_ENDPOINTS.PAYMENTS.BY_ID(id));
    return response.data;
  },

  /**
   * Create a new payment
   */
  create: async (data: CreatePaymentDto): Promise<Payment> => {
    const response = await api.post(API_ENDPOINTS.PAYMENTS.BASE, data);
    return response.data;
  },

  /**
   * Update a payment
   */
  update: async (id: number, data: UpdatePaymentDto): Promise<Payment> => {
    const response = await api.patch(API_ENDPOINTS.PAYMENTS.BY_ID(id), data);
    return response.data;
  },

  /**
   * Delete a payment
   */
  delete: async (id: number): Promise<void> => {
    await api.delete(API_ENDPOINTS.PAYMENTS.BY_ID(id));
  },

  /**
   * Get payment summary
   */
  getSummary: async (fromDate?: string, toDate?: string): Promise<PaymentSummary> => {
    const params: Record<string, string | undefined> = {};
    if (fromDate) params.from_date = fromDate;
    if (toDate) params.to_date = toDate;
    
    const response = await api.get(API_ENDPOINTS.PAYMENTS.SUMMARY, { params });
    return response.data;
  },

  /**
   * Get suggested categories
   */
  getSuggestedCategories: async (): Promise<SuggestedCategories> => {
    const response = await api.get(API_ENDPOINTS.PAYMENTS.CATEGORIES);
    return response.data;
  },
};
