import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  MenuItem,
  Box,
  Alert,
} from '@mui/material';
import { PAYMENT_METHODS, type PaymentMethod } from '../../../constants';
import type { CreatePaymentDto } from '../../../types';

interface RecordPaymentDialogProps {
  open: boolean;
  transactionNumber: string;
  balanceDue: number;
  isLoading: boolean;
  onSubmit: (data: CreatePaymentDto) => void;
  onClose: () => void;
}

export const RecordPaymentDialog: React.FC<RecordPaymentDialogProps> = ({
  open,
  transactionNumber,
  balanceDue,
  isLoading,
  onSubmit,
  onClose,
}) => {
  const [paymentDate, setPaymentDate] = useState(new Date().toISOString().split('T')[0]);
  const [amount, setAmount] = useState(balanceDue);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(PAYMENT_METHODS.CASH);
  const [referenceNumber, setReferenceNumber] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (open) {
      setPaymentDate(new Date().toISOString().split('T')[0]);
      setAmount(balanceDue);
      setPaymentMethod(PAYMENT_METHODS.CASH);
      setReferenceNumber('');
      setNotes('');
      setError(null);
    }
  }, [open, balanceDue]);

  const formatCurrency = (value: number) => {
    return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    
    if (!paymentDate) {
      setError('Payment date is required');
      return;
    }
    if (!amount || amount <= 0) {
      setError('Amount must be greater than 0');
      return;
    }
    if (amount > balanceDue) {
      setError('Amount cannot exceed balance due');
      return;
    }

    onSubmit({
      payment_date: paymentDate,
      amount,
      payment_method: paymentMethod,
      reference_number: referenceNumber || undefined,
      notes: notes || undefined,
    });
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit}>
        <DialogTitle>Record Payment for {transactionNumber}</DialogTitle>
        <DialogContent>
          <Box sx={{ mb: 2, mt: 1 }}>
            <Alert severity="info">
              Balance Due: <strong>{formatCurrency(balanceDue)}</strong>
            </Alert>
          </Box>

          {error && (
            <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
              {error}
            </Alert>
          )}

          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
            <TextField
              label="Payment Date"
              type="date"
              fullWidth
              required
              value={paymentDate}
              onChange={(e) => setPaymentDate(e.target.value)}
              InputLabelProps={{ shrink: true }}
            />

            <TextField
              label="Amount"
              type="number"
              fullWidth
              required
              value={amount}
              onChange={(e) => setAmount(parseFloat(e.target.value) || 0)}
              inputProps={{ min: 0.01, step: 0.01, max: balanceDue }}
              error={amount > balanceDue}
              helperText={amount > balanceDue ? `Exceeds balance due (${formatCurrency(balanceDue)})` : ''}
            />

            <TextField
              label="Payment Method"
              select
              fullWidth
              required
              value={paymentMethod}
              onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
            >
              {Object.values(PAYMENT_METHODS).map((method) => (
                <MenuItem key={method} value={method}>
                  {method.replace('_', ' ').toUpperCase()}
                </MenuItem>
              ))}
            </TextField>

            <TextField
              label="Reference Number"
              fullWidth
              value={referenceNumber}
              onChange={(e) => setReferenceNumber(e.target.value)}
              placeholder="Check #, UPI ID, etc."
            />

            <TextField
              label="Notes"
              fullWidth
              multiline
              rows={2}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Optional notes..."
            />
          </Box>
        </DialogContent>
        <DialogActions>
          <Button onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button
            type="submit"
            variant="contained"
            disabled={isLoading || amount > balanceDue || amount <= 0}
          >
            {isLoading ? 'Recording...' : 'Record Payment'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default RecordPaymentDialog;
