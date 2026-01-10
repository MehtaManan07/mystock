import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
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

// Placeholder component for pages not yet implemented
const PlaceholderPage: React.FC<{ title: string }> = ({ title }) => (
  <Box sx={{ p: 3 }}>
    <h1>{title}</h1>
    <p>This page is coming soon.</p>
  </Box>
);

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
        
        {/* Transactions - Placeholder for now */}
        <Route path="/transactions" element={<PlaceholderPage title="Transactions" />} />
        <Route path="/transactions/:id" element={<PlaceholderPage title="Transaction Details" />} />
        
        {/* Payments - Placeholder for now */}
        <Route path="/payments" element={<PlaceholderPage title="Payments" />} />
        <Route path="/payments/:id" element={<PlaceholderPage title="Payment Details" />} />
      </Route>

      {/* Redirect root to dashboard */}
      <Route path="/" element={<Navigate to="/dashboard" replace />} />

      {/* 404 - redirect to dashboard */}
      <Route path="*" element={<Navigate to="/dashboard" replace />} />
    </Routes>
  );
};

export default AppRoutes;
