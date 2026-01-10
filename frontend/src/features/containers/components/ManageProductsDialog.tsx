import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  Box,
  Typography,
  TextField,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Chip,
  Autocomplete,
  CircularProgress,
  Alert,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
} from '@mui/icons-material';
import { useProducts } from '../../../hooks/useProducts';
import { useSetContainerProducts } from '../../../hooks/useContainerProducts';
import type { Product, ProductContainerInfo, SetProductsDto } from '../../../types';

interface ProductQuantityItem {
  product: Product;
  quantity: number;
}

interface ManageProductsDialogProps {
  open: boolean;
  containerId: number;
  containerName: string;
  currentProducts: ProductContainerInfo[];
  onClose: () => void;
  onSuccess: () => void;
}

export const ManageProductsDialog: React.FC<ManageProductsDialogProps> = ({
  open,
  containerId,
  containerName,
  currentProducts,
  onClose,
  onSuccess,
}) => {
  const [items, setItems] = useState<ProductQuantityItem[]>([]);
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [newQuantity, setNewQuantity] = useState<number>(1);
  const [error, setError] = useState<string | null>(null);

  // Fetch all products for selection
  const { data: allProducts, isLoading: productsLoading } = useProducts();

  // Mutation to set products
  const setProductsMutation = useSetContainerProducts();

  // Initialize items from current products when dialog opens
  useEffect(() => {
    if (open && currentProducts) {
      const initialItems: ProductQuantityItem[] = currentProducts.map((cp) => ({
        product: {
          id: cp.product.id,
          name: cp.product.name,
          size: cp.product.size,
          packing: cp.product.packing,
          default_sale_price: null,
          default_purchase_price: null,
          totalQuantity: 0,
          created_at: cp.product.created_at,
          updated_at: cp.product.updated_at,
          deleted_at: cp.product.deleted_at,
        },
        quantity: cp.quantity,
      }));
      setItems(initialItems);
      setError(null);
    }
  }, [open, currentProducts]);

  // Get available products (not already in the list)
  const availableProducts =
    allProducts?.filter(
      (p) => !items.some((item) => item.product.id === p.id)
    ) || [];

  const handleAddProduct = () => {
    if (!selectedProduct) return;
    if (newQuantity <= 0) {
      setError('Quantity must be greater than 0');
      return;
    }

    setItems([...items, { product: selectedProduct, quantity: newQuantity }]);
    setSelectedProduct(null);
    setNewQuantity(1);
    setError(null);
  };

  const handleRemoveProduct = (productId: number) => {
    setItems(items.filter((item) => item.product.id !== productId));
  };

  const handleQuantityChange = (productId: number, quantity: number) => {
    if (quantity < 0) return;
    setItems(
      items.map((item) =>
        item.product.id === productId ? { ...item, quantity } : item
      )
    );
  };

  const handleSave = async () => {
    // Build the DTO
    const dto: SetProductsDto = {
      containerId,
      items: items.map((item) => ({
        productId: item.product.id,
        quantity: item.quantity,
      })),
    };

    // Also include products that were removed (set quantity to 0)
    const removedProducts = currentProducts.filter(
      (cp) => !items.some((item) => item.product.id === cp.product.id)
    );

    removedProducts.forEach((cp) => {
      dto.items.push({
        productId: cp.product.id,
        quantity: 0, // This will soft-delete the relationship
      });
    });

    try {
      await setProductsMutation.mutateAsync(dto);
      onSuccess();
      onClose();
    } catch (err) {
      setError('Failed to update products. Please try again.');
    }
  };

  const hasChanges = () => {
    // Check if there are any differences
    if (items.length !== currentProducts.length) return true;

    return items.some((item) => {
      const current = currentProducts.find(
        (cp) => cp.product.id === item.product.id
      );
      return !current || current.quantity !== item.quantity;
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="md" fullWidth>
      <DialogTitle>
        Manage Products in {containerName}
      </DialogTitle>
      <DialogContent>
        {error && (
          <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
            {error}
          </Alert>
        )}

        {/* Add Product Section */}
        <Box
          sx={{
            display: 'flex',
            gap: 2,
            alignItems: 'flex-start',
            mb: 3,
            mt: 1,
          }}
        >
          <Autocomplete
            value={selectedProduct}
            onChange={(_, value) => setSelectedProduct(value)}
            options={availableProducts}
            getOptionLabel={(option) =>
              `${option.name} (${option.size} - ${option.packing})`
            }
            loading={productsLoading}
            sx={{ flex: 1 }}
            renderInput={(params) => (
              <TextField
                {...params}
                label="Select Product"
                size="small"
                InputProps={{
                  ...params.InputProps,
                  endAdornment: (
                    <>
                      {productsLoading ? (
                        <CircularProgress color="inherit" size={20} />
                      ) : null}
                      {params.InputProps.endAdornment}
                    </>
                  ),
                }}
              />
            )}
          />
          <TextField
            label="Quantity"
            type="number"
            size="small"
            value={newQuantity}
            onChange={(e) => setNewQuantity(parseInt(e.target.value) || 0)}
            sx={{ width: 120 }}
            inputProps={{ min: 1 }}
          />
          <Button
            variant="contained"
            startIcon={<AddIcon />}
            onClick={handleAddProduct}
            disabled={!selectedProduct || newQuantity <= 0}
          >
            Add
          </Button>
        </Box>

        {/* Products Table */}
        {items.length > 0 ? (
          <TableContainer>
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>Product</TableCell>
                  <TableCell>Size</TableCell>
                  <TableCell>Packing</TableCell>
                  <TableCell align="right">Quantity</TableCell>
                  <TableCell align="center">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {items.map((item) => (
                  <TableRow key={item.product.id}>
                    <TableCell>
                      <Typography variant="body2" fontWeight={500}>
                        {item.product.name}
                      </Typography>
                    </TableCell>
                    <TableCell>{item.product.size}</TableCell>
                    <TableCell>{item.product.packing}</TableCell>
                    <TableCell align="right">
                      <TextField
                        type="number"
                        size="small"
                        value={item.quantity}
                        onChange={(e) =>
                          handleQuantityChange(
                            item.product.id,
                            parseInt(e.target.value) || 0
                          )
                        }
                        sx={{ width: 100 }}
                        inputProps={{ min: 0 }}
                      />
                    </TableCell>
                    <TableCell align="center">
                      <Tooltip title="Remove">
                        <IconButton
                          size="small"
                          color="error"
                          onClick={() => handleRemoveProduct(item.product.id)}
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
        ) : (
          <Box
            sx={{
              py: 4,
              textAlign: 'center',
              bgcolor: 'action.hover',
              borderRadius: 1,
            }}
          >
            <Typography variant="body2" color="text.secondary">
              No products in this container. Add products using the form above.
            </Typography>
          </Box>
        )}

        {/* Summary */}
        <Box sx={{ mt: 2, display: 'flex', gap: 2 }}>
          <Chip
            label={`${items.length} products`}
            size="small"
            color="primary"
            variant="outlined"
          />
          <Chip
            label={`${items.reduce((sum, i) => sum + i.quantity, 0)} total quantity`}
            size="small"
            color="success"
            variant="outlined"
          />
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose}>Cancel</Button>
        <Button
          variant="contained"
          onClick={handleSave}
          disabled={setProductsMutation.isPending || !hasChanges()}
        >
          {setProductsMutation.isPending ? 'Saving...' : 'Save Changes'}
        </Button>
      </DialogActions>
    </Dialog>
  );
};

export default ManageProductsDialog;
