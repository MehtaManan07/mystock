import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { transactionsApi } from '../api/transactions.api';
import { QUERY_KEYS } from '../constants';
import type { 
  Transaction, 
  CreateTransactionDto, 
  CreatePaymentDto, 
  TransactionFilters 
} from '../types';

/**
 * Hook to get all transactions with optional filters
 */
export const useTransactions = (filters?: TransactionFilters) => {
  // Create a stable query key based on filters
  const queryKey = filters 
    ? [...QUERY_KEYS.TRANSACTIONS, filters] 
    : QUERY_KEYS.TRANSACTIONS;

  return useQuery({
    queryKey,
    queryFn: () => transactionsApi.getAll(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnMount: false,
  });
};

/**
 * Hook to get a single transaction by ID
 */
export const useTransaction = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.TRANSACTION(id),
    queryFn: () => transactionsApi.getById(id),
    enabled: id > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to create a sale transaction
 */
export const useCreateSale = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateTransactionDto) => transactionsApi.createSale(data),
    onSuccess: (newTransaction) => {
      // Invalidate transactions list
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.TRANSACTIONS });
      
      // Invalidate contact (balance changed)
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTACT(newTransaction.contact.id) 
      });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTACTS });
      
      // Invalidate inventory (stock changed)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INVENTORY_ANALYTICS });
      newTransaction.items.forEach((item) => {
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.PRODUCT(item.product.id) 
        });
        if (item.container) {
          queryClient.invalidateQueries({ 
            queryKey: QUERY_KEYS.CONTAINER(item.container.id) 
          });
        }
      });
    },
  });
};

/**
 * Hook to create a purchase transaction
 */
export const useCreatePurchase = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateTransactionDto) => transactionsApi.createPurchase(data),
    onSuccess: (newTransaction) => {
      // Invalidate transactions list
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.TRANSACTIONS });
      
      // Invalidate contact (balance changed)
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTACT(newTransaction.contact.id) 
      });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTACTS });
      
      // Invalidate inventory (stock changed)
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INVENTORY_ANALYTICS });
      newTransaction.items.forEach((item) => {
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.PRODUCT(item.product.id) 
        });
        if (item.container) {
          queryClient.invalidateQueries({ 
            queryKey: QUERY_KEYS.CONTAINER(item.container.id) 
          });
        }
      });
    },
  });
};

/**
 * Hook to delete a transaction
 */
export const useDeleteTransaction = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => transactionsApi.delete(id),
    onMutate: async (deletedId) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.TRANSACTIONS });
      
      const previousTransactions = queryClient.getQueryData<Transaction[]>(
        QUERY_KEYS.TRANSACTIONS
      );

      // Optimistically remove from list
      queryClient.setQueryData<Transaction[]>(QUERY_KEYS.TRANSACTIONS, (old) =>
        old?.filter((t) => t.id !== deletedId)
      );

      return { previousTransactions };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.TRANSACTIONS });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTACTS });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INVENTORY_ANALYTICS });
    },
    onError: (_, __, context) => {
      if (context?.previousTransactions) {
        queryClient.setQueryData(QUERY_KEYS.TRANSACTIONS, context.previousTransactions);
      }
    },
  });
};

/**
 * Hook to record a payment against a transaction
 */
export const useRecordPayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ transactionId, data }: { transactionId: number; data: CreatePaymentDto }) =>
      transactionsApi.recordPayment(transactionId, data),
    onSuccess: (updatedTransaction) => {
      // Update the specific transaction in cache
      queryClient.setQueryData(
        QUERY_KEYS.TRANSACTION(updatedTransaction.id),
        updatedTransaction
      );
      
      // Invalidate transactions list
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.TRANSACTIONS });
      
      // Invalidate contact (balance changed)
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTACT(updatedTransaction.contact.id) 
      });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTACTS });
    },
  });
};

/**
 * Hook to get payments for a transaction
 */
export const useTransactionPayments = (transactionId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.TRANSACTION_PAYMENTS(transactionId),
    queryFn: () => transactionsApi.getPayments(transactionId),
    enabled: transactionId > 0,
    staleTime: 1000 * 60 * 5,
  });
};

/**
 * Hook to get invoice metadata
 */
export const useInvoiceMetadata = (transactionId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.INVOICE_METADATA(transactionId),
    queryFn: () => transactionsApi.getInvoiceMetadata(transactionId),
    enabled: transactionId > 0,
    staleTime: 1000 * 60 * 10, // 10 minutes
  });
};

/**
 * Hook to generate invoice
 */
export const useGenerateInvoice = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ transactionId, forceRegenerate }: { transactionId: number; forceRegenerate?: boolean }) =>
      transactionsApi.generateInvoice(transactionId, forceRegenerate),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.INVOICE_METADATA(variables.transactionId) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.TRANSACTION(variables.transactionId) 
      });
    },
  });
};

/**
 * Hook to get invoice download URL
 */
export const useInvoiceDownloadUrl = () => {
  return useMutation({
    mutationFn: ({ transactionId, expiration }: { transactionId: number; expiration?: number }) =>
      transactionsApi.getInvoiceDownloadUrl(transactionId, expiration),
  });
};
