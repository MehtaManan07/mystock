import { useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { contactsApi } from '../api/contacts.api';
import { QUERY_KEYS, type ContactType } from '../constants';
import type { CreateContactDto, UpdateContactDto, ContactFilters, Contact } from '../types';

/**
 * Hook to fetch all contacts with optional filters
 */
export const useContacts = (filters?: ContactFilters) => {
  const queryKey = useMemo(() => {
    if (!filters || Object.values(filters).every(v => v === undefined)) {
      return QUERY_KEYS.CONTACTS;
    }
    const activeFilters: Record<string, unknown> = {};
    if (filters.search?.trim()) activeFilters.search = filters.search.trim();
    if (filters.types?.length) activeFilters.types = filters.types;
    if (filters.balance) activeFilters.balance = filters.balance;
    
    return [...QUERY_KEYS.CONTACTS, activeFilters];
  }, [filters?.search, filters?.types?.join(','), filters?.balance]);

  return useQuery({
    queryKey,
    queryFn: () => contactsApi.getAll(filters),
  });
};

/**
 * Hook to fetch a single contact by ID
 */
export const useContact = (id: number) => {
  return useQuery({
    queryKey: QUERY_KEYS.CONTACT(id),
    queryFn: () => contactsApi.getById(id),
    enabled: !!id,
  });
};

/**
 * Hook to create a new contact with optimistic update
 */
export const useCreateContact = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateContactDto) => contactsApi.create(data),
    
    onMutate: async (newContact) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTACTS });
      
      const previousContacts = queryClient.getQueryData<Contact[]>(QUERY_KEYS.CONTACTS);
      
      if (previousContacts) {
        const optimisticContact: Contact = {
          id: Date.now(),
          name: newContact.name,
          phone: newContact.phone,
          address: newContact.address ?? null,
          gstin: newContact.gstin ?? null,
          type: newContact.type as ContactType,
          balance: newContact.balance ?? 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
          deleted_at: null,
        };
        queryClient.setQueryData<Contact[]>(
          QUERY_KEYS.CONTACTS,
          [...previousContacts, optimisticContact]
        );
      }
      
      return { previousContacts };
    },
    
    onError: (_err, _newContact, context) => {
      if (context?.previousContacts) {
        queryClient.setQueryData(QUERY_KEYS.CONTACTS, context.previousContacts);
      }
    },
    
    onSuccess: (serverContact) => {
      const contacts = queryClient.getQueryData<Contact[]>(QUERY_KEYS.CONTACTS);
      if (contacts) {
        const updated = contacts.filter(c => c.id < Date.now() - 10000);
        queryClient.setQueryData<Contact[]>(QUERY_KEYS.CONTACTS, [...updated, serverContact]);
      }
    },
  });
};

/**
 * Hook to update a contact with optimistic update
 */
export const useUpdateContact = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, data }: { id: number; data: UpdateContactDto }) =>
      contactsApi.update(id, data),
    
    onMutate: async ({ id, data }) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTACTS });
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTACT(id) });
      
      const previousContacts = queryClient.getQueryData<Contact[]>(QUERY_KEYS.CONTACTS);
      const previousContact = queryClient.getQueryData(QUERY_KEYS.CONTACT(id));
      
      if (previousContacts) {
        queryClient.setQueryData<Contact[]>(
          QUERY_KEYS.CONTACTS,
          previousContacts.map(c => 
            c.id === id ? { ...c, ...data, updated_at: new Date().toISOString() } : c
          )
        );
      }
      
      return { previousContacts, previousContact };
    },
    
    onError: (_err, { id }, context) => {
      if (context?.previousContacts) {
        queryClient.setQueryData(QUERY_KEYS.CONTACTS, context.previousContacts);
      }
      if (context?.previousContact) {
        queryClient.setQueryData(QUERY_KEYS.CONTACT(id), context.previousContact);
      }
    },
    
    onSuccess: (serverContact, { id }) => {
      const contacts = queryClient.getQueryData<Contact[]>(QUERY_KEYS.CONTACTS);
      if (contacts) {
        queryClient.setQueryData<Contact[]>(
          QUERY_KEYS.CONTACTS,
          contacts.map(c => c.id === id ? { ...c, ...serverContact } : c)
        );
      }
      queryClient.invalidateQueries({ queryKey: QUERY_KEYS.CONTACT(id) });
    },
  });
};

/**
 * Hook to delete a contact with optimistic update
 */
export const useDeleteContact = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: number) => contactsApi.delete(id),
    
    onMutate: async (id) => {
      await queryClient.cancelQueries({ queryKey: QUERY_KEYS.CONTACTS });
      
      const previousContacts = queryClient.getQueryData<Contact[]>(QUERY_KEYS.CONTACTS);
      
      if (previousContacts) {
        queryClient.setQueryData<Contact[]>(
          QUERY_KEYS.CONTACTS,
          previousContacts.filter(c => c.id !== id)
        );
      }
      
      return { previousContacts };
    },
    
    onError: (_err, _id, context) => {
      if (context?.previousContacts) {
        queryClient.setQueryData(QUERY_KEYS.CONTACTS, context.previousContacts);
      }
    },
  });
};
