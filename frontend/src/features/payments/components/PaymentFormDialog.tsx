import React, { useEffect, useState } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  Grid,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  CircularProgress,
  ToggleButton,
  ToggleButtonGroup,
  Autocomplete,
  Box,
  Typography,
} from '@mui/material';
import {
  TrendingUp as IncomeIcon,
  TrendingDown as ExpenseIcon,
} from '@mui/icons-material';
import { useForm, Controller } from 'react-hook-form';
import { useCreatePayment, useUpdatePayment, usePaymentCategories } from '../../../hooks/usePayments';
import { useContacts } from '../../../hooks/useContacts';
import { PAYMENT_METHODS, PAYMENT_TYPES, type PaymentType, type PaymentMethod } from '../../../constants';
import type { Payment, CreatePaymentDto } from '../../../types';

interface PaymentFormDialogProps {
  open: boolean;
  payment: Payment | null;
  onClose: () => void;
}

interface FormData {
  payment_date: string;
  type: PaymentType;
  category: string;
  amount: number;
  payment_method: PaymentMethod;
  contact_id: number | null;
  description: string;
  reference_number: string;
  notes: string;
}

export const PaymentFormDialog: React.FC<PaymentFormDialogProps> = ({
  open,
  payment,
  onClose,
}) => {
  const isEdit = !!payment;
  const createMutation = useCreatePayment();
  const updateMutation = useUpdatePayment();
  const { data: suggestedCategories } = usePaymentCategories();
  const { data: contacts } = useContacts();

  const [paymentType, setPaymentType] = useState<PaymentType>(PAYMENT_TYPES.EXPENSE);

  const {
    control,
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      payment_date: new Date().toISOString().split('T')[0],
      type: PAYMENT_TYPES.EXPENSE,
      category: '',
      amount: 0,
      payment_method: PAYMENT_METHODS.CASH,
      contact_id: null,
      description: '',
      reference_number: '',
      notes: '',
    },
  });

  useEffect(() => {
    if (open) {
      if (payment) {
        setPaymentType(payment.type);
        reset({
          payment_date: payment.payment_date,
          type: payment.type,
          category: payment.category || '',
          amount: payment.amount,
          payment_method: payment.payment_method,
          contact_id: payment.contact?.id || null,
          description: payment.description || '',
          reference_number: payment.reference_number || '',
          notes: payment.notes || '',
        });
      } else {
        setPaymentType(PAYMENT_TYPES.EXPENSE);
        reset({
          payment_date: new Date().toISOString().split('T')[0],
          type: PAYMENT_TYPES.EXPENSE,
          category: '',
          amount: 0,
          payment_method: PAYMENT_METHODS.CASH,
          contact_id: null,
          description: '',
          reference_number: '',
          notes: '',
        });
      }
    }
  }, [open, payment, reset]);

  const handleTypeChange = (
    _: React.MouseEvent<HTMLElement>,
    newType: PaymentType | null
  ) => {
    if (newType !== null) {
      setPaymentType(newType);
    }
  };

  const onSubmit = async (data: FormData) => {
    const payload: CreatePaymentDto = {
      payment_date: data.payment_date,
      type: paymentType,
      category: data.category || undefined,
      amount: data.amount,
      payment_method: data.payment_method,
      contact_id: data.contact_id || undefined,
      description: data.description || undefined,
      reference_number: data.reference_number || undefined,
      notes: data.notes || undefined,
    };

    try {
      if (isEdit) {
        await updateMutation.mutateAsync({ id: payment.id, data: payload });
      } else {
        await createMutation.mutateAsync(payload);
      }
      onClose();
    } catch (error) {
      console.error('Failed to save payment:', error);
    }
  };

  const isLoading = createMutation.isPending || updateMutation.isPending;

  // Get appropriate categories based on payment type
  const categories =
    paymentType === PAYMENT_TYPES.INCOME
      ? suggestedCategories?.income_categories || []
      : suggestedCategories?.expense_categories || [];

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <DialogTitle>{isEdit ? 'Edit Payment' : 'Add Payment'}</DialogTitle>
      <DialogContent dividers>
        <Box component="form" onSubmit={handleSubmit(onSubmit)} noValidate>
          <Grid container spacing={2}>
            {/* Payment Type Toggle */}
            <Grid size={{ xs: 12 }}>
              <Box sx={{ display: 'flex', justifyContent: 'center', mb: 1 }}>
                <ToggleButtonGroup
                  value={paymentType}
                  exclusive
                  onChange={handleTypeChange}
                  size="large"
                  color="primary"
                >
                  <ToggleButton value={PAYMENT_TYPES.INCOME} color="success">
                    <IncomeIcon sx={{ mr: 1 }} />
                    Income
                  </ToggleButton>
                  <ToggleButton value={PAYMENT_TYPES.EXPENSE} color="error">
                    <ExpenseIcon sx={{ mr: 1 }} />
                    Expense
                  </ToggleButton>
                </ToggleButtonGroup>
              </Box>
            </Grid>

            {/* Payment Date */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                label="Payment Date"
                type="date"
                fullWidth
                {...register('payment_date', { required: 'Date is required' })}
                error={!!errors.payment_date}
                helperText={errors.payment_date?.message}
                InputLabelProps={{ shrink: true }}
              />
            </Grid>

            {/* Amount */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                label="Amount"
                type="number"
                fullWidth
                {...register('amount', {
                  required: 'Amount is required',
                  min: { value: 0.01, message: 'Amount must be positive' },
                  valueAsNumber: true,
                })}
                error={!!errors.amount}
                helperText={errors.amount?.message}
                InputProps={{
                  startAdornment: <Typography sx={{ mr: 0.5 }}>₹</Typography>,
                }}
              />
            </Grid>

            {/* Category */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <Controller
                name="category"
                control={control}
                render={({ field }) => (
                  <Autocomplete
                    freeSolo
                    options={categories}
                    value={field.value}
                    onChange={(_, newValue) => field.onChange(newValue || '')}
                    onInputChange={(_, newValue) => field.onChange(newValue)}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Category"
                        placeholder="Select or type category"
                        helperText="You can type your own category"
                      />
                    )}
                  />
                )}
              />
            </Grid>

            {/* Payment Method */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <Controller
                name="payment_method"
                control={control}
                rules={{ required: 'Payment method is required' }}
                render={({ field }) => (
                  <FormControl fullWidth error={!!errors.payment_method}>
                    <InputLabel>Payment Method</InputLabel>
                    <Select {...field} label="Payment Method">
                      {Object.values(PAYMENT_METHODS).map((method) => (
                        <MenuItem key={method} value={method}>
                          {method.replace(/_/g, ' ')}
                        </MenuItem>
                      ))}
                    </Select>
                    {errors.payment_method && (
                      <FormHelperText>{errors.payment_method.message}</FormHelperText>
                    )}
                  </FormControl>
                )}
              />
            </Grid>

            {/* Contact */}
            <Grid size={{ xs: 12 }}>
              <Controller
                name="contact_id"
                control={control}
                render={({ field }) => (
                  <Autocomplete
                    options={contacts || []}
                    getOptionLabel={(option) =>
                      typeof option === 'object' ? option.name : ''
                    }
                    value={contacts?.find((c) => c.id === field.value) || null}
                    onChange={(_, newValue) =>
                      field.onChange(newValue?.id || null)
                    }
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Contact (Optional)"
                        placeholder="Select contact"
                      />
                    )}
                  />
                )}
              />
            </Grid>

            {/* Description */}
            <Grid size={{ xs: 12 }}>
              <TextField
                label="Description"
                fullWidth
                multiline
                rows={2}
                {...register('description')}
                helperText="Brief description of the payment"
              />
            </Grid>

            {/* Reference Number */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                label="Reference Number"
                fullWidth
                {...register('reference_number')}
                placeholder="e.g., Receipt #, Check #"
              />
            </Grid>

            {/* Notes */}
            <Grid size={{ xs: 12, sm: 6 }}>
              <TextField
                label="Notes"
                fullWidth
                {...register('notes')}
                placeholder="Additional notes"
              />
            </Grid>
          </Grid>
        </Box>
      </DialogContent>
      <DialogActions>
        <Button onClick={onClose} disabled={isLoading}>
          Cancel
        </Button>
        <Button
          variant="contained"
          color={paymentType === PAYMENT_TYPES.INCOME ? 'success' : 'error'}
          onClick={handleSubmit(onSubmit)}
          disabled={isLoading}
        >
          {isLoading ? (
            <CircularProgress size={24} color="inherit" />
          ) : isEdit ? (
            'Update'
          ) : (
            `Add ${paymentType === PAYMENT_TYPES.INCOME ? 'Income' : 'Expense'}`
          )}
        </Button>
      </DialogActions>
    </Dialog>
  );
};
