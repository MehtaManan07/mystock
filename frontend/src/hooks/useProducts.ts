import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { productsApi } from '../api/products.api';
import { QUERY_KEYS } from '../constants';
import type { CreateProductDto, UpdateProductDto, Product } from '../types';

/**
 * Hook to fetch all products
 */
export const useProducts = (search?: string) => {
  const normalizedSearch = search?.trim() || undefined;
  
  return useQuery({
    queryKey: normalizedSearch 
      ? [...QUERY_KEYS.PRODUCTS, normalizedSearch] 
      : QUERY_KEYS.PRODUCTS,
    queryFn: () => productsApi.getAll(normalizedSearch),
  });
};

/**
 * Hook to fetch a single product by ID
 */
export const useProduct = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.PRODUCT(id),
    queryFn: () => productsApi.getById(id),
    enabled: !!id,
  });
};

/**
 * Hook to create a new product with optimistic update
 */
export const useCreateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProductDto) => productsApi.create(data),
    
    onMutate: async (newProduct) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PRODUCTS });
      
      // Snapshot previous value
      const previousProducts = queryClient.getQueryData<Product[]>(QUERY_KEYS.PRODUCTS);
      
      // Optimistically add the new product with a temporary ID
      if (previousProducts) {
        const optimisticProduct: Product = {
          id: Date.now(), // Temporary ID
          ...newProduct,
          default_sale_price: newProduct.default_sale_price ?? null,
          default_purchase_price: newProduct.default_purchase_price ?? null,
          totalQuantity: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          deleted_at: null,
        };
        queryClient.setQueryData<Product[]>(
          QUERY_KEYS.PRODUCTS,
          [...previousProducts, optimisticProduct]
        );
      }
      
      return { previousProducts };
    },
    
    onError: (_err, _newProduct, context) => {
      // Rollback on error
      if (context?.previousProducts) {
        queryClient.setQueryData(QUERY_KEYS.PRODUCTS, context.previousProducts);
      }
    },
    
    onSuccess: (serverProduct) => {
      // Replace optimistic product with server response
      const products = queryClient.getQueryData<Product[]>(QUERY_KEYS.PRODUCTS);
      if (products) {
        // Remove the temp product and add the real one
        const updated = products.filter(p => p.id < Date.now() - 10000);
        queryClient.setQueryData<Product[]>(QUERY_KEYS.PRODUCTS, [...updated, serverProduct]);
      }
    },
  });
};

/**
 * Hook to update a product with optimistic update
 */
export const useUpdateProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateProductDto }) =>
      productsApi.update(id, data),
    
    onMutate: async ({ id, data }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PRODUCTS });
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PRODUCT(id) });
      
      // Snapshot previous values
      const previousProducts = queryClient.getQueryData<Product[]>(QUERY_KEYS.PRODUCTS);
      const previousProduct = queryClient.getQueryData(QUERY_KEYS.PRODUCT(id));
      
      // Optimistically update the products list
      if (previousProducts) {
        queryClient.setQueryData<Product[]>(
          QUERY_KEYS.PRODUCTS,
          previousProducts.map(p => 
            p.id === id ? { ...p, ...data, updated_at: new Date().toISOString() } : p
          )
        );
      }
      
      return { previousProducts, previousProduct };
    },
    
    onError: (_err, { id }, context) => {
      // Rollback on error
      if (context?.previousProducts) {
        queryClient.setQueryData(QUERY_KEYS.PRODUCTS, context.previousProducts);
      }
      if (context?.previousProduct) {
        queryClient.setQueryData(QUERY_KEYS.PRODUCT(id), context.previousProduct);
      }
    },
    
    onSuccess: (serverProduct, { id }) => {
      // Update with server response
      const products = queryClient.getQueryData<Product[]>(QUERY_KEYS.PRODUCTS);
      if (products) {
        queryClient.setQueryData<Product[]>(
          QUERY_KEYS.PRODUCTS,
          products.map(p => p.id === id ? { ...p, ...serverProduct } : p)
        );
      }
      // Invalidate detail view to get fresh data on next visit
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PRODUCT(id) });
    },
  });
};

/**
 * Hook to delete a product with optimistic update
 */
export const useDeleteProduct = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => productsApi.delete(id),
    
    onMutate: async (id) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.PRODUCTS });
      
      // Snapshot previous value
      const previousProducts = queryClient.getQueryData<Product[]>(QUERY_KEYS.PRODUCTS);
      
      // Optimistically remove the product
      if (previousProducts) {
        queryClient.setQueryData<Product[]>(
          QUERY_KEYS.PRODUCTS,
          previousProducts.filter(p => p.id !== id)
        );
      }
      
      return { previousProducts };
    },
    
    onError: (_err, _id, context) => {
      // Rollback on error
      if (context?.previousProducts) {
        queryClient.setQueryData(QUERY_KEYS.PRODUCTS, context.previousProducts);
      }
    },
  });
};

/**
 * Hook to create multiple products in bulk
 */
export const useCreateProductsBulk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProductDto[]) => productsApi.createBulk(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.PRODUCTS });
    },
  });
};
