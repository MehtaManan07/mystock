import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthGuard, GuestGuard } from '../components/common/AuthGuard';
import MainLayout from '../components/layout/MainLayout';

// Direct imports instead of lazy loading for faster navigation
import LoginPage from '../features/auth/LoginPage';
import RegisterPage from '../features/auth/RegisterPage';
import DashboardPage from '../features/dashboard/DashboardPage';
import ProductsPage from '../features/products/ProductsPage';
import ProductDetailPage from '../features/products/ProductDetailPage';
import ContainersPage from '../features/containers/ContainersPage';
import ContainerDetailPage from '../features/containers/ContainerDetailPage';
import ContactsPage from '../features/contacts/ContactsPage';
import ContactDetailPage from '../features/contacts/ContactDetailPage';
import InventoryPage from '../features/inventory/InventoryPage';
import InventoryLogsPage from '../features/inventory/InventoryLogsPage';
import TransactionsPage from '../features/transactions/TransactionsPage';
import TransactionDetailPage from '../features/transactions/TransactionDetailPage';
import CreateSalePage from '../features/transactions/CreateSalePage';
import CreatePurchasePage from '../features/transactions/CreatePurchasePage';
import PaymentsPage from '../features/payments/PaymentsPage';

export const AppRoutes: React.FC = () => {
  return (
    <Routes>
      {/* Public routes */}
      <Route
        path="/login"
        element={
          <GuestGuard>
            <LoginPage />
          </GuestGuard>
        }
      />
      <Route
        path="/register"
        element={
          <GuestGuard>
            <RegisterPage />
          </GuestGuard>
        }
      />

      {/* Protected routes */}
      <Route
        element={
          <AuthGuard>
            <MainLayout />
          </AuthGuard>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        
        {/* Products */}
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/products/:id" element={<ProductDetailPage />} />
        
        {/* Containers */}
        <Route path="/containers" element={<ContainersPage />} />
        <Route path="/containers/:id" element={<ContainerDetailPage />} />
        
        {/* Contacts */}
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/contacts/:id" element={<ContactDetailPage />} />
        
        {/* Inventory */}
        <Route path="/inventory" element={<InventoryPage />} />
        <Route path="/inventory/logs" element={<InventoryLogsPage />} />
        
        {/* Transactions */}
        <Route path="/transactions" element={<TransactionsPage />} />
        <Route path="/transactions/new-sale" element={<CreateSalePage />} />
        <Route path="/transactions/new-purchase" element={<CreatePurchasePage />} />
        <Route path="/transactions/:id" element={<TransactionDetailPage />} />
        
        {/* Payments */}
        <Route path="/payments" element={<PaymentsPage />} />
      </Route>

      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 - redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default AppRoutes;
