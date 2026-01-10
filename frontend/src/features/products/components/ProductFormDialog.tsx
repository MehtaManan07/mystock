import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  InputAdornment,
} from '@mui/material';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import type { Product, CreateProductDto } from '../../../types';

// Form data type
interface ProductFormData {
  name: string;
  size: string;
  packing: string;
  default_sale_price: string;
  default_purchase_price: string;
}

// Validation schema
const productSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  size: z.string().min(1, 'Size is required').max(255),
  packing: z.string().min(1, 'Packing is required').max(255),
  default_sale_price: z.string(),
  default_purchase_price: z.string(),
});

interface ProductFormDialogProps {
  open: boolean;
  product?: Product | null;
  isLoading?: boolean;
  onSubmit: (data: CreateProductDto) => void;
  onClose: () => void;
}

export const ProductFormDialog: React.FC<ProductFormDialogProps> = ({
  open,
  product,
  isLoading = false,
  onSubmit,
  onClose,
}) => {
  const isEditing = !!product;

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ProductFormData>({
    resolver: zodResolver(productSchema),
    defaultValues: {
      name: '',
      size: '',
      packing: '',
      default_sale_price: '',
      default_purchase_price: '',
    },
  });

  // Reset form when dialog opens/closes or product changes
  useEffect(() => {
    if (open) {
      if (product) {
        reset({
          name: product.name,
          size: product.size,
          packing: product.packing,
          default_sale_price: product.default_sale_price?.toString() || '',
          default_purchase_price: product.default_purchase_price?.toString() || '',
        });
      } else {
        reset({
          name: '',
          size: '',
          packing: '',
          default_sale_price: '',
          default_purchase_price: '',
        });
      }
    }
  }, [open, product, reset]);

  const handleFormSubmit = (data: ProductFormData) => {
    const salePrice = data.default_sale_price ? parseFloat(data.default_sale_price) : undefined;
    const purchasePrice = data.default_purchase_price ? parseFloat(data.default_purchase_price) : undefined;
    
    onSubmit({
      name: data.name,
      size: data.size,
      packing: data.packing,
      default_sale_price: salePrice,
      default_purchase_price: purchasePrice,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <DialogTitle>{isEditing ? 'Edit Product' : 'Add New Product'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={12}>
              <TextField
                {...register('name')}
                label="Product Name"
                error={!!errors.name}
                helperText={errors.name?.message}
                disabled={isLoading}
                autoFocus
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('size')}
                label="Size"
                placeholder="e.g., 25kg, 1L, 500g"
                error={!!errors.size}
                helperText={errors.size?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('packing')}
                label="Packing"
                placeholder="e.g., Bag, Box, Bottle"
                error={!!errors.packing}
                helperText={errors.packing?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('default_sale_price')}
                label="Default Sale Price"
                type="number"
                inputProps={{ step: '0.01', min: 0 }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                }}
                error={!!errors.default_sale_price}
                helperText={errors.default_sale_price?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('default_purchase_price')}
                label="Default Purchase Price"
                type="number"
                inputProps={{ step: '0.01', min: 0 }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                }}
                error={!!errors.default_purchase_price}
                helperText={errors.default_purchase_price?.message}
                disabled={isLoading}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={isLoading}>
            {isLoading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default ProductFormDialog;
