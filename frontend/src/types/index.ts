import type {
  UserRole,
  ContactType,
  ContainerType,
  TransactionType,
  PaymentStatus,
  PaymentMethod,
  PaymentType,
} from '../constants';

// ============================================
// Base Types
// ============================================

export interface BaseEntity {
  id: number;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

// ============================================
// User & Auth Types
// ============================================

export interface User extends BaseEntity {
  username: string;
  name: string;
  role: UserRole;
  contact_info: string | null;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  name: string;
  role: UserRole;
  contact_info?: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface AuthResponse {
  user: User;
  token: TokenResponse;
}

// ============================================
// Product Types
// ============================================

export interface Product extends BaseEntity {
  name: string;
  size: string;
  packing: string;
  default_sale_price: number | null;
  default_purchase_price: number | null;
  totalQuantity: number;
}

export interface ProductDetail extends Omit<Product, 'totalQuantity'> {
  containers: ContainerProductInfo[];
  logs: InventoryLogInfo[];
}

export interface ContainerProductInfo {
  container: ContainerInfo;
  quantity: number;
}

export interface ContainerInfo {
  id: number;
  name: string;
  type: ContainerType;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface CreateProductDto {
  name: string;
  size: string;
  packing: string;
  default_sale_price?: number;
  default_purchase_price?: number;
}

export interface UpdateProductDto {
  name?: string;
  size?: string;
  packing?: string;
  default_sale_price?: number;
  default_purchase_price?: number;
}

// ============================================
// Container Types
// ============================================

export interface Container extends BaseEntity {
  name: string;
  type: ContainerType;
  productCount: number;
}

export interface ContainerDetail extends Omit<Container, 'productCount'> {
  products: ProductContainerInfo[];
  logs: InventoryLogInfo[];
}

export interface ProductContainerInfo {
  product: ProductInfo;
  quantity: number;
}

export interface ProductInfo {
  id: number;
  name: string;
  size: string;
  packing: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;
}

export interface CreateContainerDto {
  name: string;
  type: ContainerType;
}

export interface UpdateContainerDto {
  name?: string;
  type?: ContainerType;
}

// ============================================
// Container Product (Inventory) Types
// ============================================

export interface ContainerProduct extends BaseEntity {
  container_id: number;
  product_id: number;
  quantity: number;
  product?: ProductInfo;
  container?: ContainerInfo;
}

export interface SetProductsDto {
  containerId: number;
  items: Array<{
    productId: number;
    quantity: number;
  }>;
}

export interface TotalQuantityResponse {
  productId: number;
  totalQuantity: number;
}

export interface InventoryAnalytics {
  totalProducts: number;
  totalContainers: number;
  totalQuantity: number;
}

// ============================================
// Contact Types
// ============================================

export interface Contact extends BaseEntity {
  name: string;
  phone: string;
  address: string | null;
  gstin: string | null;
  type: ContactType;
  balance: number;
}

export interface CreateContactDto {
  name: string;
  phone: string;
  address?: string;
  gstin?: string;
  type: ContactType;
  balance?: number;
}

export interface UpdateContactDto {
  name?: string;
  phone?: string;
  address?: string;
  gstin?: string;
  type?: ContactType;
  balance?: number;
}

export interface ContactFilters {
  types?: ContactType[];
  balance?: 'positive' | 'negative';
  search?: string;
}

// ============================================
// Transaction Types
// ============================================

export interface Transaction extends BaseEntity {
  transaction_number: string;
  transaction_date: string;
  type: TransactionType;
  contact: ContactInTransaction;
  items: TransactionItem[];
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  paid_amount: number;
  payment_status: PaymentStatus;
  balance_due: number;
  notes: string | null;
  invoice_url: string | null;
  invoice_checksum: string | null;
  payments: Payment[];
}

export interface TransactionItem {
  id: number;
  product: ProductInTransaction;
  container: ContainerInTransaction | null;
  quantity: number;
  unit_price: number;
  line_total: number;
  created_at: string;
  updated_at: string;
}

export interface ProductInTransaction {
  id: number;
  name: string;
  size: string;
  packing: string;
}

export interface ContainerInTransaction {
  id: number;
  name: string;
  type: string;
}

export interface ContactInTransaction {
  id: number;
  name: string;
  phone: string;
  type: string;
  balance: number;
}

export interface CreateTransactionItemDto {
  product_id: number;
  container_id?: number;
  quantity: number;
  unit_price: number;
}

export interface CreateTransactionDto {
  transaction_date: string;
  contact_id: number;
  items: CreateTransactionItemDto[];
  tax_amount?: number;
  discount_amount?: number;
  paid_amount?: number;
  payment_method?: PaymentMethod;
  payment_reference?: string;
  notes?: string;
}

export interface TransactionFilters {
  type?: TransactionType;
  payment_status?: PaymentStatus;
  contact_id?: number;
  from_date?: string;
  to_date?: string;
  search?: string;
}

export interface InvoiceMetadata {
  transaction_id: number;
  transaction_number: string;
  invoice_url: string | null;
  invoice_checksum: string | null;
}

// ============================================
// Payment Types
// ============================================

export interface Payment extends BaseEntity {
  payment_date: string;
  amount: number;
  payment_method: PaymentMethod;
  type: PaymentType;
  category: string | null;
  description: string | null;
  reference_number: string | null;
  notes: string | null;
  contact?: ContactInPayment | null;
  transaction?: TransactionInPayment | null;
}

export interface ContactInPayment {
  id: number;
  name: string;
  phone: string;
  type: string;
}

export interface TransactionInPayment {
  id: number;
  transaction_number: string;
  transaction_date: string;
  type: string;
  total_amount: number;
}

export interface CreatePaymentDto {
  payment_date: string;
  amount: number;
  payment_method: PaymentMethod;
  type?: PaymentType;
  category?: string;
  description?: string;
  transaction_id?: number;
  contact_id?: number;
  reference_number?: string;
  notes?: string;
}

export interface UpdatePaymentDto {
  payment_date?: string;
  amount?: number;
  payment_method?: PaymentMethod;
  type?: PaymentType;
  category?: string;
  description?: string;
  transaction_id?: number;
  contact_id?: number;
  reference_number?: string;
  notes?: string;
}

export interface PaymentFilters {
  type?: PaymentType;
  category?: string;
  payment_method?: PaymentMethod;
  contact_id?: number;
  transaction_id?: number;
  from_date?: string;
  to_date?: string;
  search?: string;
  min_amount?: number;
  max_amount?: number;
  manual_only?: boolean;
}

export interface PaymentSummary {
  total_amount: number;
  total_spends: number;
  total_earnings: number;
  payment_count: number;
  category_breakdown: Record<string, number>;
}

export interface SuggestedCategories {
  income_categories: string[];
  expense_categories: string[];
}

// ============================================
// Inventory Log Types
// ============================================

export interface InventoryLog extends BaseEntity {
  product_id: number;
  container_id: number;
  quantity: number;
  action: string;
  note: string | null;
  timestamp: string;
}

export interface InventoryLogInfo {
  id: number;
  quantity: number;
  action: string;
  container?: { id: number; name: string } | null;
  product?: { id: number; name: string } | null;
  created_at: string;
}

export interface CreateInventoryLogDto {
  product_id: number;
  container_id: number;
  quantity: number;
  action: string;
  note?: string;
}

// ============================================
// API Response Types
// ============================================

export interface ApiResponse<T> {
  success: boolean;
  data: T;
  message?: string;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}
