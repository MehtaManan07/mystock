// API Configuration
export const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// API Endpoints
export const API_ENDPOINTS = {
  // Auth
  AUTH: {
    LOGIN: '/users/login',
    REGISTER: '/users/register',
    ME: '/users/me',
  },
  // Users
  USERS: {
    BASE: '/users',
    BY_ID: (id: number) => `/users/${id}`,
    BY_ROLE: '/users/role',
  },
  // Products
  PRODUCTS: {
    BASE: '/products',
    BY_ID: (id: number) => `/products/${id}`,
    BULK: '/products/bulk',
  },
  // Containers
  CONTAINERS: {
    BASE: '/containers',
    BY_ID: (id: number) => `/containers/${id}`,
    BULK: '/containers/bulk',
  },
  // Container Products (Inventory)
  CONTAINER_PRODUCTS: {
    SET_PRODUCTS: '/container-products/set-products',
    BY_CONTAINER: (id: number) => `/container-products/${id}/products`,
    BY_PRODUCT: (id: number) => `/container-products/product/${id}/containers`,
    TOTAL_QUANTITY: (id: number) => `/container-products/product/${id}/total-quantity`,
    SEARCH: '/container-products/search',
    ANALYTICS: '/container-products/analytics',
    MAP_PRODUCTS: '/container-products/map-products-to-ids',
  },
  // Contacts
  CONTACTS: {
    BASE: '/contacts',
    BY_ID: (id: number) => `/contacts/${id}`,
  },
  // Transactions
  TRANSACTIONS: {
    BASE: '/transactions',
    SALES: '/transactions/sales',
    PURCHASES: '/transactions/purchases',
    BY_ID: (id: number) => `/transactions/${id}`,
    PAYMENTS: (id: number) => `/transactions/${id}/payments`,
    INVOICE_METADATA: (id: number) => `/transactions/${id}/invoice/metadata`,
    INVOICE_GENERATE: (id: number) => `/transactions/${id}/invoice/generate`,
    INVOICE_DOWNLOAD: (id: number) => `/transactions/${id}/invoice/download`,
  },
  // Payments
  PAYMENTS: {
    BASE: '/payments',
    BY_ID: (id: number) => `/payments/${id}`,
    SUMMARY: '/payments/summary',
    CATEGORIES: '/payments/suggested-categories',
  },
  // Inventory Logs
  INVENTORY_LOGS: {
    BASE: '/inventory-logs',
    BY_PRODUCT: (id: number) => `/inventory-logs/product/${id}`,
    BY_CONTAINER: (id: number) => `/inventory-logs/container/${id}`,
    BULK: '/inventory-logs/bulk',
  },
} as const;

// React Query Keys
export const QUERY_KEYS = {
  // Auth
  CURRENT_USER: ['currentUser'] as const,
  
  // Users
  USERS: ['users'] as const,
  USER: (id: number) => ['users', id] as const,
  
  // Products
  PRODUCTS: ['products'] as const,
  PRODUCT: (id: number) => ['products', id] as const,
  
  // Containers
  CONTAINERS: ['containers'] as const,
  CONTAINER: (id: number) => ['containers', id] as const,
  
  // Container Products
  CONTAINER_PRODUCTS: (containerId: number) => ['containerProducts', containerId] as const,
  PRODUCT_CONTAINERS: (productId: number) => ['productContainers', productId] as const,
  PRODUCT_TOTAL_QTY: (productId: number) => ['productTotalQty', productId] as const,
  INVENTORY_ANALYTICS: ['inventoryAnalytics'] as const,
  
  // Contacts
  CONTACTS: ['contacts'] as const,
  CONTACT: (id: number) => ['contacts', id] as const,
  
  // Transactions
  TRANSACTIONS: ['transactions'] as const,
  TRANSACTION: (id: number) => ['transactions', id] as const,
  TRANSACTION_PAYMENTS: (id: number) => ['transactionPayments', id] as const,
  INVOICE_METADATA: (id: number) => ['invoiceMetadata', id] as const,
  
  // Payments
  PAYMENTS: ['payments'] as const,
  PAYMENT: (id: number) => ['payments', id] as const,
  PAYMENT_SUMMARY: ['paymentSummary'] as const,
  PAYMENT_CATEGORIES: ['paymentCategories'] as const,
  
  // Inventory Logs
  INVENTORY_LOGS: ['inventoryLogs'] as const,
  PRODUCT_LOGS: (productId: number) => ['inventoryLogs', 'product', productId] as const,
  CONTAINER_LOGS: (containerId: number) => ['inventoryLogs', 'container', containerId] as const,
} as const;

// User Roles
export const USER_ROLES = {
  ADMIN: 'ADMIN',
  MANAGER: 'MANAGER',
  STAFF: 'STAFF',
  JOBBER: 'JOBBER',
} as const;

export type UserRole = (typeof USER_ROLES)[keyof typeof USER_ROLES];

// Contact Types
export const CONTACT_TYPES = {
  CUSTOMER: 'customer',
  SUPPLIER: 'supplier',
  BOTH: 'both',
} as const;

export type ContactType = (typeof CONTACT_TYPES)[keyof typeof CONTACT_TYPES];

// Container Types
export const CONTAINER_TYPES = {
  SINGLE: 'single',
  MIXED: 'mixed',
} as const;

export type ContainerType = (typeof CONTAINER_TYPES)[keyof typeof CONTAINER_TYPES];

// Transaction Types
export const TRANSACTION_TYPES = {
  SALE: 'sale',
  PURCHASE: 'purchase',
} as const;

export type TransactionType = (typeof TRANSACTION_TYPES)[keyof typeof TRANSACTION_TYPES];

// Payment Status
export const PAYMENT_STATUS = {
  PAID: 'paid',
  PARTIAL: 'partial',
  UNPAID: 'unpaid',
} as const;

export type PaymentStatus = (typeof PAYMENT_STATUS)[keyof typeof PAYMENT_STATUS];

// Payment Methods
export const PAYMENT_METHODS = {
  CASH: 'cash',
  BANK_TRANSFER: 'bank_transfer',
  UPI: 'upi',
  CHEQUE: 'cheque',
  CARD: 'card',
  OTHER: 'other',
} as const;

export type PaymentMethod = (typeof PAYMENT_METHODS)[keyof typeof PAYMENT_METHODS];

// Payment Types (Income/Expense)
export const PAYMENT_TYPES = {
  INCOME: 'income',
  EXPENSE: 'expense',
} as const;

export type PaymentType = (typeof PAYMENT_TYPES)[keyof typeof PAYMENT_TYPES];

// Local Storage Keys
export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'mystock_access_token',
  USER: 'mystock_user',
  THEME_MODE: 'mystock_theme_mode',
} as const;

// Pagination defaults
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 10,
  PAGE_SIZE_OPTIONS: [10, 25, 50, 100],
} as const;
