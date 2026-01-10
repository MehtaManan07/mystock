import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { inventoryLogsApi } from '../api/inventoryLogs.api';
import { QUERY_KEYS } from '../constants';
import type { CreateInventoryLogDto, InventoryLog } from '../types';

/**
 * Hook to get all inventory logs
 */
export const useInventoryLogs = () => {
  return useQuery({
    queryKey: QUERY_KEYS.INVENTORY_LOGS,
    queryFn: () => inventoryLogsApi.getAll(),
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnMount: false,
  });
};

/**
 * Hook to get inventory logs for a specific product
 */
export const useProductLogs = (productId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.PRODUCT_LOGS(productId),
    queryFn: () => inventoryLogsApi.getByProduct(productId),
    enabled: productId > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to get inventory logs for a specific container
 */
export const useContainerLogs = (containerId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.CONTAINER_LOGS(containerId),
    queryFn: () => inventoryLogsApi.getByContainer(containerId),
    enabled: containerId > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to create a single inventory log with optimistic update
 */
export const useCreateInventoryLog = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateInventoryLogDto) => inventoryLogsApi.create(data),
    onMutate: async (newLog) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.INVENTORY_LOGS });
      
      // Snapshot current logs
      const previousLogs = queryClient.getQueryData<InventoryLog[]>(QUERY_KEYS.INVENTORY_LOGS);

      // Optimistically add the new log
      queryClient.setQueryData<InventoryLog[]>(QUERY_KEYS.INVENTORY_LOGS, (old) => {
        const tempId = Date.now();
        const optimisticLog: InventoryLog = {
          id: tempId,
          product_id: newLog.product_id,
          container_id: newLog.container_id,
          quantity: newLog.quantity,
          action: newLog.action,
          note: newLog.note || null,
          timestamp: new Date().toISOString(),
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          deleted_at: null,
        };
        return old ? [optimisticLog, ...old] : [optimisticLog];
      });

      return { previousLogs };
    },
    onSuccess: (_, variables) => {
      // Invalidate related queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INVENTORY_LOGS });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.PRODUCT_LOGS(variables.product_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTAINER_LOGS(variables.container_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTAINER(variables.container_id) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.PRODUCT(variables.product_id) 
      });
    },
    onError: (_, __, context) => {
      // Rollback on error
      if (context?.previousLogs) {
        queryClient.setQueryData(QUERY_KEYS.INVENTORY_LOGS, context.previousLogs);
      }
    },
  });
};

/**
 * Hook to create multiple inventory logs in bulk
 */
export const useCreateInventoryLogsBulk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateInventoryLogDto[]) => inventoryLogsApi.createBulk(data),
    onSuccess: (_, variables) => {
      // Invalidate all related queries
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.INVENTORY_LOGS });
      
      // Get unique product and container IDs
      const productIds = [...new Set(variables.map((v) => v.product_id))];
      const containerIds = [...new Set(variables.map((v) => v.container_id))];
      
      productIds.forEach((id) => {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PRODUCT_LOGS(id) });
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PRODUCT(id) });
      });
      
      containerIds.forEach((id) => {
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTAINER_LOGS(id) });
        queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTAINER(id) });
      });
    },
  });
};
