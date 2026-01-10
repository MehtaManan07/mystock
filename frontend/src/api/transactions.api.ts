import api from './axios';
import { API_ENDPOINTS } from '../constants';
import type {
  Transaction,
  CreateTransactionDto,
  CreatePaymentDto,
  TransactionFilters,
  InvoiceMetadata,
  Payment,
} from '../types';

/**
 * Transactions API
 * Handles sales, purchases, payments, and invoices
 */
export const transactionsApi = {
  /**
   * Get all transactions with optional filters
   */
  getAll: async (filters?: TransactionFilters): Promise<Transaction[]> => {
    const params: Record<string, string | number | undefined> = {};
    
    if (filters?.type) params.type = filters.type;
    if (filters?.payment_status) params.payment_status = filters.payment_status;
    if (filters?.contact_id) params.contact_id = filters.contact_id;
    if (filters?.from_date) params.from_date = filters.from_date;
    if (filters?.to_date) params.to_date = filters.to_date;
    if (filters?.search) params.search = filters.search;

    const response = await api.get(API_ENDPOINTS.TRANSACTIONS.BASE, { params });
    return response.data;
  },

  /**
   * Get a single transaction by ID
   */
  getById: async (id: number): Promise<Transaction> => {
    const response = await api.get(API_ENDPOINTS.TRANSACTIONS.BY_ID(id));
    return response.data;
  },

  /**
   * Create a new sale transaction
   */
  createSale: async (data: CreateTransactionDto): Promise<Transaction> => {
    const response = await api.post(API_ENDPOINTS.TRANSACTIONS.SALES, data);
    return response.data;
  },

  /**
   * Create a new purchase transaction
   */
  createPurchase: async (data: CreateTransactionDto): Promise<Transaction> => {
    const response = await api.post(API_ENDPOINTS.TRANSACTIONS.PURCHASES, data);
    return response.data;
  },

  /**
   * Delete a transaction (soft delete)
   */
  delete: async (id: number): Promise<void> => {
    await api.delete(API_ENDPOINTS.TRANSACTIONS.BY_ID(id));
  },

  /**
   * Record a payment against a transaction
   */
  recordPayment: async (transactionId: number, data: CreatePaymentDto): Promise<Transaction> => {
    const response = await api.post(API_ENDPOINTS.TRANSACTIONS.PAYMENTS(transactionId), data);
    return response.data;
  },

  /**
   * Get all payments for a transaction
   */
  getPayments: async (transactionId: number): Promise<Payment[]> => {
    const response = await api.get(API_ENDPOINTS.TRANSACTIONS.PAYMENTS(transactionId));
    return response.data;
  },

  /**
   * Get invoice metadata
   */
  getInvoiceMetadata: async (transactionId: number): Promise<InvoiceMetadata> => {
    const response = await api.get(API_ENDPOINTS.TRANSACTIONS.INVOICE_METADATA(transactionId));
    return response.data;
  },

  /**
   * Generate/regenerate invoice PDF
   */
  generateInvoice: async (
    transactionId: number, 
    forceRegenerate = false
  ): Promise<{ message: string; invoice_url: string; checksum: string }> => {
    const response = await api.post(
      API_ENDPOINTS.TRANSACTIONS.INVOICE_GENERATE(transactionId),
      null,
      { params: { force_regenerate: forceRegenerate } }
    );
    return response.data;
  },

  /**
   * Get presigned download URL for invoice
   */
  getInvoiceDownloadUrl: async (
    transactionId: number,
    expiration = 3600
  ): Promise<{ download_url: string; expires_in_seconds: number }> => {
    const response = await api.get(
      API_ENDPOINTS.TRANSACTIONS.INVOICE_DOWNLOAD(transactionId),
      { params: { expiration } }
    );
    return response.data;
  },
};
