import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { ProductFormDialog } from './components/ProductFormDialog';
import { useProducts, useCreateProduct, useUpdateProduct, useDeleteProduct } from '../../hooks/useProducts';
import type { Product, CreateProductDto, UpdateProductDto } from '../../types';

export const ProductsPage: React.FC = () => {
  const navigate = useNavigate();
  
  // Search state
  const [search, setSearch] = useState('');
  
  // Dialog states
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [productToDelete, setProductToDelete] = useState<Product | null>(null);

  // Data fetching
  const { data: products, isLoading, isFetching, isError, refetch } = useProducts(search || undefined);
  
  // Only show full loading on initial load (no data yet)
  const showFullLoading = isLoading && !products;
  
  // Mutations
  const createMutation = useCreateProduct();
  const updateMutation = useUpdateProduct();
  const deleteMutation = useDeleteProduct();

  // Handlers
  const handleOpenCreateDialog = () => {
    setSelectedProduct(null);
    setFormDialogOpen(true);
  };

  const handleOpenEditDialog = (product: Product) => {
    setSelectedProduct(product);
    setFormDialogOpen(true);
  };

  const handleCloseFormDialog = () => {
    setFormDialogOpen(false);
    setSelectedProduct(null);
  };

  const handleFormSubmit = (data: CreateProductDto) => {
    if (selectedProduct) {
      updateMutation.mutate(
        { id: selectedProduct.id, data: data as UpdateProductDto },
        {
          onSuccess: () => handleCloseFormDialog(),
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => handleCloseFormDialog(),
      });
    }
  };

  const handleOpenDeleteDialog = (product: Product) => {
    setProductToDelete(product);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setProductToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (productToDelete) {
      deleteMutation.mutate(productToDelete.id, {
        onSuccess: () => handleCloseDeleteDialog(),
      });
    }
  };

  const handleViewProduct = (product: Product) => {
    navigate(`/products/${product.id}`);
  };

  const formatCurrency = (value: number | null) => {
    if (value === null || value === undefined) return '-';
    return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  };

  // Render content for the table area
  const renderTableContent = () => {
    if (showFullLoading) {
      return <LoadingState message="Loading products..." />;
    }
    
    if (isError) {
      return <ErrorState onRetry={() => refetch()} />;
    }
    
    if (!products || products.length === 0) {
      return (
        <EmptyState
          title="No products found"
          message={search ? 'Try a different search term' : 'Add your first product to get started'}
          actionLabel={!search ? 'Add Product' : undefined}
          onAction={!search ? handleOpenCreateDialog : undefined}
        />
      );
    }
    
    return (
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Size</TableCell>
              <TableCell>Packing</TableCell>
              <TableCell align="right">Sale Price</TableCell>
              <TableCell align="right">Purchase Price</TableCell>
              <TableCell align="right">Total Qty</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {products.map((product) => (
              <TableRow
                key={product.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => handleViewProduct(product)}
              >
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {product.name}
                  </Typography>
                </TableCell>
                <TableCell>{product.size || '-'}</TableCell>
                <TableCell>{product.packing || '-'}</TableCell>
                <TableCell align="right">
                  <Chip
                    label={formatCurrency(product.default_sale_price)}
                    size="small"
                    color="success"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={formatCurrency(product.default_purchase_price)}
                    size="small"
                    color="primary"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={product.totalQuantity}
                    size="small"
                    color={product.totalQuantity > 0 ? 'primary' : 'default'}
                    variant={product.totalQuantity > 0 ? 'filled' : 'outlined'}
                  />
                </TableCell>
                <TableCell align="center" onClick={(e) => e.stopPropagation()}>
                  <Tooltip title="View">
                    <IconButton
                      size="small"
                      onClick={() => handleViewProduct(product)}
                    >
                      <ViewIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Edit">
                    <IconButton
                      size="small"
                      onClick={() => handleOpenEditDialog(product)}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => handleOpenDeleteDialog(product)}
                    >
                      <DeleteIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  return (
    <Box>
      <PageHeader
        title="Products"
        subtitle={products ? `${products.length} products in your catalog` : 'Manage your product catalog'}
        actionLabel="Add Product"
        onAction={handleOpenCreateDialog}
      />

      {/* Search bar - always visible */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by name, size, or packing..."
        />
        {isFetching && !showFullLoading && (
          <Typography variant="caption" color="text.secondary">
            Searching...
          </Typography>
        )}
      </Box>

      {/* Products table */}
      <Card>
        {renderTableContent()}
      </Card>

      {/* Create/Edit Dialog */}
      <ProductFormDialog
        open={formDialogOpen}
        product={selectedProduct}
        isLoading={createMutation.isPending || updateMutation.isPending}
        onSubmit={handleFormSubmit}
        onClose={handleCloseFormDialog}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Product"
        message={`Are you sure you want to delete "${productToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        confirmColor="error"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={handleCloseDeleteDialog}
      />
    </Box>
  );
};

export default ProductsPage;
