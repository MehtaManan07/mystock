import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { containersApi } from '../api/containers.api';
import { QUERY_KEYS, type ContainerType } from '../constants';
import type { CreateContainerDto, UpdateContainerDto, Container } from '../types';

/**
 * Hook to fetch all containers
 */
export const useContainers = (search?: string) => {
  const normalizedSearch = search?.trim() || undefined;
  
  return useQuery({
    queryKey: normalizedSearch 
      ? [...QUERY_KEYS.CONTAINERS, normalizedSearch] 
      : QUERY_KEYS.CONTAINERS,
    queryFn: () => containersApi.getAll(normalizedSearch),
  });
};

/**
 * Hook to fetch a single container by ID
 */
export const useContainer = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.CONTAINER(id),
    queryFn: () => containersApi.getById(id),
    enabled: !!id,
  });
};

/**
 * Hook to create a new container with optimistic update
 */
export const useCreateContainer = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateContainerDto) => containersApi.create(data),
    
    onMutate: async (newContainer) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTAINERS });
      
      const previousContainers = queryClient.getQueryData<Container[]>(QUERY_KEYS.CONTAINERS);
      
      if (previousContainers) {
        const optimisticContainer: Container = {
          id: Date.now(),
          name: newContainer.name,
          type: newContainer.type as ContainerType
          ,
          productCount: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          deleted_at: null,
        };
        queryClient.setQueryData<Container[]>(
          QUERY_KEYS.CONTAINERS,
          [...previousContainers, optimisticContainer]
        );
      }
      
      return { previousContainers };
    },
    
    onError: (_err, _newContainer, context) => {
      if (context?.previousContainers) {
        queryClient.setQueryData(QUERY_KEYS.CONTAINERS, context.previousContainers);
      }
    },
    
    onSuccess: (serverContainer) => {
      const containers = queryClient.getQueryData<Container[]>(QUERY_KEYS.CONTAINERS);
      if (containers) {
        const updated = containers.filter(c => c.id < Date.now() - 10000);
        queryClient.setQueryData<Container[]>(QUERY_KEYS.CONTAINERS, [...updated, serverContainer]);
      }
    },
  });
};

/**
 * Hook to update a container with optimistic update
 */
export const useUpdateContainer = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateContainerDto }) =>
      containersApi.update(id, data),
    
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTAINERS });
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTAINER(id) });
      
      const previousContainers = queryClient.getQueryData<Container[]>(QUERY_KEYS.CONTAINERS);
      const previousContainer = queryClient.getQueryData(QUERY_KEYS.CONTAINER(id));
      
      if (previousContainers) {
        queryClient.setQueryData<Container[]>(
          QUERY_KEYS.CONTAINERS,
          previousContainers.map(c => 
            c.id === id ? { ...c, ...data, updated_at: new Date().toISOString() } : c
          )
        );
      }
      
      return { previousContainers, previousContainer };
    },
    
    onError: (_err, { id }, context) => {
      if (context?.previousContainers) {
        queryClient.setQueryData(QUERY_KEYS.CONTAINERS, context.previousContainers);
      }
      if (context?.previousContainer) {
        queryClient.setQueryData(QUERY_KEYS.CONTAINER(id), context.previousContainer);
      }
    },
    
    onSuccess: (serverContainer, { id }) => {
      const containers = queryClient.getQueryData<Container[]>(QUERY_KEYS.CONTAINERS);
      if (containers) {
        queryClient.setQueryData<Container[]>(
          QUERY_KEYS.CONTAINERS,
          containers.map(c => c.id === id ? { ...c, ...serverContainer } : c)
        );
      }
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTAINER(id) });
    },
  });
};

/**
 * Hook to delete a container with optimistic update
 */
export const useDeleteContainer = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => containersApi.delete(id),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTAINERS });
      
      const previousContainers = queryClient.getQueryData<Container[]>(QUERY_KEYS.CONTAINERS);
      
      if (previousContainers) {
        queryClient.setQueryData<Container[]>(
          QUERY_KEYS.CONTAINERS,
          previousContainers.filter(c => c.id !== id)
        );
      }
      
      return { previousContainers };
    },
    
    onError: (_err, _id, context) => {
      if (context?.previousContainers) {
        queryClient.setQueryData(QUERY_KEYS.CONTAINERS, context.previousContainers);
      }
    },
  });
};

/**
 * Hook to create multiple containers in bulk
 */
export const useCreateContainersBulk = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateContainerDto[]) => containersApi.createBulk(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTAINERS });
    },
  });
};
