import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { paymentsApi } from '../api/payments.api';
import { QUERY_KEYS } from '../constants';
import type { Payment, CreatePaymentDto, UpdatePaymentDto, PaymentFilters } from '../types';

/**
 * Hook to get all payments with optional filters
 */
export const usePayments = (filters?: PaymentFilters) => {
  const queryKey = filters 
    ? [...QUERY_KEYS.PAYMENTS, filters] 
    : QUERY_KEYS.PAYMENTS;

  return useQuery({
    queryKey,
    queryFn: () => paymentsApi.getAll(filters),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnMount: false,
  });
};

/**
 * Hook to get a single payment by ID
 */
export const usePayment = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.PAYMENT(id),
    queryFn: () => paymentsApi.getById(id),
    enabled: id > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to get payment summary
 */
export const usePaymentSummary = (fromDate?: string, toDate?: string) => {
  return useQuery({
    queryKey: [...QUERY_KEYS.PAYMENT_SUMMARY, fromDate, toDate],
    queryFn: () => paymentsApi.getSummary(fromDate, toDate),
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to get suggested payment categories
 */
export const usePaymentCategories = () => {
  return useQuery({
    queryKey: QUERY_KEYS.PAYMENT_CATEGORIES,
    queryFn: () => paymentsApi.getSuggestedCategories(),
    staleTime: 1000 * 60 * 30, // 30 minutes - categories don't change often
    refetchOnMount: false,
  });
};

/**
 * Hook to create a payment with optimistic updates
 */
export const useCreatePayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreatePaymentDto) => paymentsApi.create(data),
    onMutate: async (newPayment) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      
      const previousPayments = queryClient.getQueryData<Payment[]>(QUERY_KEYS.PAYMENTS);

      queryClient.setQueryData<Payment[]>(QUERY_KEYS.PAYMENTS, (old) => {
        const tempId = Date.now();
        const optimisticPayment: Payment = {
          id: tempId,
          payment_date: newPayment.payment_date,
          amount: newPayment.amount,
          payment_method: newPayment.payment_method,
          type: newPayment.type || 'expense',
          category: newPayment.category || null,
          description: newPayment.description || null,
          reference_number: newPayment.reference_number || null,
          notes: newPayment.notes || null,
          contact: null,
          transaction: null,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          deleted_at: null,
        };
        return old ? [optimisticPayment, ...old] : [optimisticPayment];
      });

      return { previousPayments };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENT_SUMMARY });
    },
    onError: (_, __, context) => {
      if (context?.previousPayments) {
        queryClient.setQueryData(QUERY_KEYS.PAYMENTS, context.previousPayments);
      }
    },
  });
};

/**
 * Hook to update a payment
 */
export const useUpdatePayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdatePaymentDto }) =>
      paymentsApi.update(id, data),
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      
      const previousPayments = queryClient.getQueryData<Payment[]>(QUERY_KEYS.PAYMENTS);

      queryClient.setQueryData<Payment[]>(QUERY_KEYS.PAYMENTS, (old) =>
        old?.map((p) =>
          p.id === id
            ? {
                ...p,
                ...data,
                updated_at: new Date().toISOString(),
              }
            : p
        )
      );

      return { previousPayments };
    },
    onSuccess: (updatedPayment) => {
      queryClient.setQueryData(QUERY_KEYS.PAYMENT(updatedPayment.id), updatedPayment);
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENT_SUMMARY });
    },
    onError: (_, __, context) => {
      if (context?.previousPayments) {
        queryClient.setQueryData(QUERY_KEYS.PAYMENTS, context.previousPayments);
      }
    },
  });
};

/**
 * Hook to delete a payment with optimistic updates
 */
export const useDeletePayment = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => paymentsApi.delete(id),
    onMutate: async (deletedId) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      
      const previousPayments = queryClient.getQueryData<Payment[]>(QUERY_KEYS.PAYMENTS);

      queryClient.setQueryData<Payment[]>(QUERY_KEYS.PAYMENTS, (old) =>
        old?.filter((p) => p.id !== deletedId)
      );

      return { previousPayments };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENTS });
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PAYMENT_SUMMARY });
    },
    onError: (_, __, context) => {
      if (context?.previousPayments) {
        queryClient.setQueryData(QUERY_KEYS.PAYMENTS, context.previousPayments);
      }
    },
  });
};
