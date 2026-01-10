import React, { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Chip,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Tooltip,
  Divider,
  Button,
} from '@mui/material';
import {
  ArrowBack as BackIcon,
  Delete as DeleteIcon,
  Payment as PaymentIcon,
  Download as DownloadIcon,
  ShoppingCart as SaleIcon,
  LocalShipping as PurchaseIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { RecordPaymentDialog } from './components/RecordPaymentDialog';
import {
  useTransaction,
  useDeleteTransaction,
  useRecordPayment,
  useInvoiceDownloadUrl,
} from '../../hooks/useTransactions';
import { TRANSACTION_TYPES, PAYMENT_STATUS } from '../../constants';
import type { CreatePaymentDto } from '../../types';

export const TransactionDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const transactionId = parseInt(id || '0', 10);

  // Dialog states
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [paymentDialogOpen, setPaymentDialogOpen] = useState(false);

  // Data fetching
  const { data: transaction, isLoading, isError, refetch } = useTransaction(transactionId);

  // Mutations
  const deleteMutation = useDeleteTransaction();
  const recordPaymentMutation = useRecordPayment();
  const downloadInvoiceMutation = useInvoiceDownloadUrl();

  const formatCurrency = (value: number) => {
    return `₹${Math.abs(value).toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  };

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'dd MMM yyyy');
  };

  const getStatusColor = (status: string): 'success' | 'warning' | 'error' => {
    switch (status) {
      case PAYMENT_STATUS.PAID:
        return 'success';
      case PAYMENT_STATUS.PARTIAL:
        return 'warning';
      case PAYMENT_STATUS.UNPAID:
        return 'error';
      default:
        return 'warning';
    }
  };

  const handleConfirmDelete = () => {
    deleteMutation.mutate(transactionId, {
      onSuccess: () => navigate('/transactions'),
    });
  };

  const handleRecordPayment = (data: CreatePaymentDto) => {
    recordPaymentMutation.mutate(
      { transactionId, data },
      {
        onSuccess: () => {
          setPaymentDialogOpen(false);
          refetch();
        },
      }
    );
  };

  const handleDownloadInvoice = async () => {
    try {
      const result = await downloadInvoiceMutation.mutateAsync({ transactionId });
      window.open(result.download_url, '_blank');
    } catch (error) {
      console.error('Failed to get invoice URL', error);
    }
  };

  if (isLoading) {
    return <LoadingState message="Loading transaction details..." fullPage />;
  }

  if (isError || !transaction) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  const isSale = transaction.type === TRANSACTION_TYPES.SALE;
  const isPaid = transaction.payment_status === PAYMENT_STATUS.PAID;

  return (
    <Box>
      <PageHeader
        title={transaction.transaction_number}
        subtitle={`${transaction.type.toUpperCase()} • ${formatDate(transaction.transaction_date)}`}
        breadcrumbs={[
          { label: 'Transactions', path: '/transactions' },
          { label: transaction.transaction_number },
        ]}
      />

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3, flexWrap: 'wrap' }}>
        <Tooltip title="Back to Transactions">
          <IconButton onClick={() => navigate('/transactions')}>
            <BackIcon />
          </IconButton>
        </Tooltip>
        
        {!isPaid && (
          <Button
            variant="contained"
            color="success"
            startIcon={<PaymentIcon />}
            onClick={() => setPaymentDialogOpen(true)}
          >
            Record Payment
          </Button>
        )}
        
        {transaction.invoice_url && (
          <Button
            variant="outlined"
            startIcon={<DownloadIcon />}
            onClick={handleDownloadInvoice}
            disabled={downloadInvoiceMutation.isPending}
          >
            {downloadInvoiceMutation.isPending ? 'Loading...' : 'Download Invoice'}
          </Button>
        )}
        
        <Tooltip title="Delete Transaction">
          <IconButton color="error" onClick={() => setDeleteDialogOpen(true)}>
            <DeleteIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        {/* Transaction Summary Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                {isSale ? (
                  <SaleIcon color="primary" />
                ) : (
                  <PurchaseIcon color="secondary" />
                )}
                <Typography variant="h6">
                  {isSale ? 'Sale' : 'Purchase'} Details
                </Typography>
              </Box>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    {isSale ? 'Customer' : 'Supplier'}
                  </Typography>
                  <Typography
                    variant="body1"
                    fontWeight={600}
                    sx={{ cursor: 'pointer', '&:hover': { textDecoration: 'underline' } }}
                    onClick={() => navigate(`/contacts/${transaction.contact.id}`)}
                  >
                    {transaction.contact.name}
                  </Typography>
                  <Typography variant="body2" color="text.secondary">
                    {transaction.contact.phone}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Date
                  </Typography>
                  <Typography variant="body1">
                    {formatDate(transaction.transaction_date)}
                  </Typography>
                </Box>

                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Status
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip
                      label={transaction.payment_status}
                      color={getStatusColor(transaction.payment_status)}
                      size="small"
                    />
                  </Box>
                </Box>

                <Divider />

                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="text.secondary">Subtotal</Typography>
                  <Typography variant="body2">{formatCurrency(transaction.subtotal)}</Typography>
                </Box>
                {transaction.tax_amount > 0 && (
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Tax</Typography>
                    <Typography variant="body2">{formatCurrency(transaction.tax_amount)}</Typography>
                  </Box>
                )}
                {transaction.discount_amount > 0 && (
                  <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Typography variant="body2" color="text.secondary">Discount</Typography>
                    <Typography variant="body2" color="error.main">
                      -{formatCurrency(transaction.discount_amount)}
                    </Typography>
                  </Box>
                )}
                <Divider />
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body1" fontWeight={600}>Total</Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {formatCurrency(transaction.total_amount)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2" color="success.main">Paid</Typography>
                  <Typography variant="body2" color="success.main">
                    {formatCurrency(transaction.paid_amount)}
                  </Typography>
                </Box>
                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography
                    variant="body1"
                    fontWeight={600}
                    color={transaction.balance_due > 0 ? 'error.main' : 'text.primary'}
                  >
                    Balance Due
                  </Typography>
                  <Typography
                    variant="body1"
                    fontWeight={600}
                    color={transaction.balance_due > 0 ? 'error.main' : 'text.primary'}
                  >
                    {formatCurrency(transaction.balance_due)}
                  </Typography>
                </Box>

                {transaction.notes && (
                  <>
                    <Divider />
                    <Box>
                      <Typography variant="caption" color="text.secondary">
                        Notes
                      </Typography>
                      <Typography variant="body2">{transaction.notes}</Typography>
                    </Box>
                  </>
                )}
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Items and Payments */}
        <Grid size={{ xs: 12, md: 8 }}>
          {/* Items Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Items ({transaction.items.length})
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <TableContainer>
                <Table size="small">
                  <TableHead>
                    <TableRow>
                      <TableCell>Product</TableCell>
                      <TableCell>Container</TableCell>
                      <TableCell align="right">Qty</TableCell>
                      <TableCell align="right">Unit Price</TableCell>
                      <TableCell align="right">Total</TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {transaction.items.map((item) => (
                      <TableRow
                        key={item.id}
                        hover
                        sx={{ cursor: 'pointer' }}
                        onClick={() => navigate(`/products/${item.product.id}`)}
                      >
                        <TableCell>
                          <Typography variant="body2" fontWeight={500}>
                            {item.product.name}
                          </Typography>
                          <Typography variant="caption" color="text.secondary">
                            {item.product.size} • {item.product.packing}
                          </Typography>
                        </TableCell>
                        <TableCell>
                          {item.container ? (
                            <Chip
                              label={item.container.name}
                              size="small"
                              variant="outlined"
                              onClick={(e) => {
                                e.stopPropagation();
                                navigate(`/containers/${item.container!.id}`);
                              }}
                            />
                          ) : (
                            '-'
                          )}
                        </TableCell>
                        <TableCell align="right">{item.quantity}</TableCell>
                        <TableCell align="right">{formatCurrency(item.unit_price)}</TableCell>
                        <TableCell align="right" sx={{ fontWeight: 500 }}>
                          {formatCurrency(item.line_total)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            </CardContent>
          </Card>

          {/* Payments Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Payments ({transaction.payments.length})
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {transaction.payments.length > 0 ? (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Date</TableCell>
                        <TableCell>Method</TableCell>
                        <TableCell>Reference</TableCell>
                        <TableCell align="right">Amount</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {transaction.payments.map((payment) => (
                        <TableRow key={payment.id}>
                          <TableCell>
                            <Typography variant="caption">
                              {formatDate(payment.payment_date)}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip
                              label={payment.payment_method.replace('_', ' ')}
                              size="small"
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>
                            <Typography variant="body2" color="text.secondary">
                              {payment.reference_number || '-'}
                            </Typography>
                          </TableCell>
                          <TableCell align="right">
                            <Typography variant="body2" color="success.main" fontWeight={500}>
                              {formatCurrency(payment.amount)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No payments recorded yet.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Transaction"
        message={`Are you sure you want to delete "${transaction.transaction_number}"? This will reverse all inventory and balance changes. This action cannot be undone.`}
        confirmLabel="Delete"
        confirmColor="error"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteDialogOpen(false)}
      />

      {/* Record Payment Dialog */}
      <RecordPaymentDialog
        open={paymentDialogOpen}
        transactionNumber={transaction.transaction_number}
        balanceDue={transaction.balance_due}
        isLoading={recordPaymentMutation.isPending}
        onSubmit={handleRecordPayment}
        onClose={() => setPaymentDialogOpen(false)}
      />
    </Box>
  );
};

export default TransactionDetailPage;
