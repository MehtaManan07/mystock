import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { containerProductsApi } from '../api/containerProducts.api';
import { QUERY_KEYS } from '../constants';
import type { SetProductsDto, ContainerProduct } from '../types';

/**
 * Hook to get all products in a specific container
 */
export const useContainerProducts = (containerId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.CONTAINER_PRODUCTS(containerId),
    queryFn: () => containerProductsApi.getProductsInContainer(containerId),
    enabled: containerId > 0,
    staleTime: 1000 * 60 * 5, // 5 minutes
    refetchOnMount: false,
  });
};

/**
 * Hook to get all containers that have a specific product
 */
export const useProductContainers = (productId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.PRODUCT_CONTAINERS(productId),
    queryFn: () => containerProductsApi.getContainersForProduct(productId),
    enabled: productId > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to get total quantity of a product across all containers
 */
export const useProductTotalQuantity = (productId: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.PRODUCT_TOTAL_QTY(productId),
    queryFn: () => containerProductsApi.getTotalQuantity(productId),
    enabled: productId > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to search containers by product SKU/name
 */
export const useContainerSearch = (sku: string) => {
  const normalizedSku = sku.trim();
  
  return useQuery({
    queryKey: normalizedSku ? ['containerSearch', normalizedSku] : ['containerSearch'],
    queryFn: () => containerProductsApi.searchBySku(normalizedSku),
    enabled: normalizedSku.length > 0,
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to get inventory analytics
 */
export const useInventoryAnalytics = () => {
  return useQuery({
    queryKey: QUERY_KEYS.INVENTORY_ANALYTICS,
    queryFn: () => containerProductsApi.getAnalytics(),
    staleTime: 1000 * 60 * 5,
    refetchOnMount: false,
  });
};

/**
 * Hook to set products in a container with optimistic updates
 */
export const useSetContainerProducts = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: SetProductsDto) => containerProductsApi.setProducts(data),
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ 
        queryKey: QUERY_KEYS.CONTAINER_PRODUCTS(newData.containerId) 
      });

      // Snapshot current data
      const previousProducts = queryClient.getQueryData<ContainerProduct[]>(
        QUERY_KEYS.CONTAINER_PRODUCTS(newData.containerId)
      );

      // Optimistically update the container products
      queryClient.setQueryData<ContainerProduct[]>(
        QUERY_KEYS.CONTAINER_PRODUCTS(newData.containerId),
        (old) => {
          if (!old) return old;
          
          const updatedProducts = [...old];
          
          newData.items.forEach((item) => {
            const existingIndex = updatedProducts.findIndex(
              (p) => p.product_id === item.productId
            );
            
            if (item.quantity === 0) {
              // Remove if quantity is 0
              if (existingIndex >= 0) {
                updatedProducts.splice(existingIndex, 1);
              }
            } else if (existingIndex >= 0) {
              // Update existing
              updatedProducts[existingIndex] = {
                ...updatedProducts[existingIndex],
                quantity: item.quantity,
              };
            }
            // Note: We can't add new products optimistically without product details
          });
          
          return updatedProducts;
        }
      );

      return { previousProducts };
    },
    onSuccess: (_, variables) => {
      // Invalidate related queries to refetch fresh data
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTAINER_PRODUCTS(variables.containerId) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.CONTAINER(variables.containerId) 
      });
      queryClient.invalidateQueries({ 
        queryKey: QUERY_KEYS.INVENTORY_ANALYTICS 
      });
      
      // Invalidate product-related queries for affected products
      variables.items.forEach((item) => {
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.PRODUCT_CONTAINERS(item.productId) 
        });
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.PRODUCT_TOTAL_QTY(item.productId) 
        });
        queryClient.invalidateQueries({ 
          queryKey: QUERY_KEYS.PRODUCT(item.productId) 
        });
      });
    },
    onError: (_, variables, context) => {
      // Rollback on error
      if (context?.previousProducts) {
        queryClient.setQueryData(
          QUERY_KEYS.CONTAINER_PRODUCTS(variables.containerId),
          context.previousProducts
        );
      }
    },
  });
};
