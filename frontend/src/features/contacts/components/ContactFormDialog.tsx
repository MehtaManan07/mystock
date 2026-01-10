import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Grid,
  InputAdornment,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { CONTACT_TYPES, type ContactType } from '../../../constants';
import type { Contact, CreateContactDto } from '../../../types';

// Form data type
interface ContactFormData {
  name: string;
  phone: string;
  address: string;
  gstin: string;
  type: ContactType;
  balance: string;
}

// Validation schema
const contactSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  phone: z.string().min(1, 'Phone is required').max(50),
  address: z.string().max(500),
  gstin: z.string().max(15),
  type: z.enum([CONTACT_TYPES.CUSTOMER, CONTACT_TYPES.SUPPLIER, CONTACT_TYPES.BOTH]),
  balance: z.string(),
});

interface ContactFormDialogProps {
  open: boolean;
  contact?: Contact | null;
  isLoading?: boolean;
  onSubmit: (data: CreateContactDto) => void;
  onClose: () => void;
}

const contactTypeOptions: { value: ContactType; label: string; description: string }[] = [
  { value: CONTACT_TYPES.CUSTOMER, label: 'Customer', description: 'Buys from you' },
  { value: CONTACT_TYPES.SUPPLIER, label: 'Supplier', description: 'Sells to you' },
  { value: CONTACT_TYPES.BOTH, label: 'Both', description: 'Customer & Supplier' },
];

export const ContactFormDialog: React.FC<ContactFormDialogProps> = ({
  open,
  contact,
  isLoading = false,
  onSubmit,
  onClose,
}) => {
  const isEditing = !!contact;

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContactFormData>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      name: '',
      phone: '',
      address: '',
      gstin: '',
      type: CONTACT_TYPES.CUSTOMER,
      balance: '0',
    },
  });

  // Reset form when dialog opens/closes or contact changes
  useEffect(() => {
    if (open) {
      if (contact) {
        reset({
          name: contact.name,
          phone: contact.phone,
          address: contact.address || '',
          gstin: contact.gstin || '',
          type: contact.type as ContactType,
          balance: contact.balance.toString(),
        });
      } else {
        reset({
          name: '',
          phone: '',
          address: '',
          gstin: '',
          type: CONTACT_TYPES.CUSTOMER,
          balance: '0',
        });
      }
    }
  }, [open, contact, reset]);

  const handleFormSubmit = (data: ContactFormData) => {
    const balanceValue = data.balance ? parseFloat(data.balance) : 0;
    
    onSubmit({
      name: data.name,
      phone: data.phone,
      address: data.address || undefined,
      gstin: data.gstin || undefined,
      type: data.type,
      balance: balanceValue,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <DialogTitle>{isEditing ? 'Edit Contact' : 'Add New Contact'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={12}>
              <TextField
                {...register('name')}
                label="Name"
                placeholder="Contact or business name"
                error={!!errors.name}
                helperText={errors.name?.message}
                disabled={isLoading}
                autoFocus
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('phone')}
                label="Phone"
                placeholder="e.g., 9876543210"
                error={!!errors.phone}
                helperText={errors.phone?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <Controller
                name="type"
                control={control}
                render={({ field }) => (
                  <FormControl fullWidth error={!!errors.type}>
                    <InputLabel>Contact Type</InputLabel>
                    <Select {...field} label="Contact Type" disabled={isLoading}>
                      {contactTypeOptions.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </Select>
                    {errors.type && (
                      <FormHelperText>{errors.type.message}</FormHelperText>
                    )}
                  </FormControl>
                )}
              />
            </Grid>
            <Grid size={12}>
              <TextField
                {...register('address')}
                label="Address (Optional)"
                placeholder="Full address"
                multiline
                rows={2}
                error={!!errors.address}
                helperText={errors.address?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('gstin')}
                label="GSTIN (Optional)"
                placeholder="e.g., 22AAAAA0000A1Z5"
                error={!!errors.gstin}
                helperText={errors.gstin?.message}
                disabled={isLoading}
              />
            </Grid>
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                {...register('balance')}
                label="Opening Balance"
                type="number"
                inputProps={{ step: '0.01' }}
                InputProps={{
                  startAdornment: <InputAdornment position="start">₹</InputAdornment>,
                }}
                helperText="Positive = they owe you, Negative = you owe them"
                error={!!errors.balance}
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

export default ContactFormDialog;
