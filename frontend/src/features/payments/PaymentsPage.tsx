import React, { useState, useMemo } from 'react';
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
  Typography,
  Tooltip,
  ToggleButton,
  ToggleButtonGroup,
  TextField,
  Button,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  TrendingUp as IncomeIcon,
  TrendingDown as ExpenseIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { usePayments, usePaymentSummary, useDeletePayment } from '../../hooks/usePayments';
import { PaymentFormDialog } from './components/PaymentFormDialog';
import type { Payment, PaymentFilters } from '../../types';
import { PAYMENT_TYPES, type PaymentType } from '../../constants';

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
  }).format(value);
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-IN', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
};

export const PaymentsPage: React.FC = () => {
  // Filter state
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<PaymentType | 'all'>('all');
  const [dateRange, setDateRange] = useState<{ from: string; to: string }>({
    from: '',
    to: '',
  });

  // Dialog state
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [editingPayment, setEditingPayment] = useState<Payment | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [paymentToDelete, setPaymentToDelete] = useState<Payment | null>(null);

  // Build filters object
  const filters: PaymentFilters = useMemo(() => {
    const f: PaymentFilters = { manual_only: true }; // Only show manual payments
    if (search) f.search = search;
    if (typeFilter !== 'all') f.type = typeFilter;
    if (dateRange.from) f.from_date = dateRange.from;
    if (dateRange.to) f.to_date = dateRange.to;
    return f;
  }, [search, typeFilter, dateRange]);

  // Data fetching
  const { data: payments, isLoading, isFetching, isError, refetch } = usePayments(filters);
  const { data: summary } = usePaymentSummary(dateRange.from || undefined, dateRange.to || undefined);
  const deleteMutation = useDeletePayment();

  const showFullLoading = isLoading && !payments;

  // Handlers
  const handleOpenCreateDialog = () => {
    setEditingPayment(null);
    setFormDialogOpen(true);
  };

  const handleOpenEditDialog = (payment: Payment) => {
    setEditingPayment(payment);
    setFormDialogOpen(true);
  };

  const handleCloseFormDialog = () => {
    setFormDialogOpen(false);
    setEditingPayment(null);
  };

  const handleOpenDeleteDialog = (payment: Payment) => {
    setPaymentToDelete(payment);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setPaymentToDelete(null);
  };

  const handleConfirmDelete = async () => {
    if (paymentToDelete) {
      await deleteMutation.mutateAsync(paymentToDelete.id);
      handleCloseDeleteDialog();
    }
  };

  const handleTypeFilterChange = (
    _: React.MouseEvent<HTMLElement>,
    newType: PaymentType | 'all' | null
  ) => {
    if (newType !== null) {
      setTypeFilter(newType);
    }
  };

  const renderTableContent = () => {
    if (showFullLoading) {
      return <LoadingState message="Loading payments..." />;
    }

    if (isError) {
      return <ErrorState onRetry={() => refetch()} />;
    }

    if (!payments || payments.length === 0) {
      return (
        <EmptyState
          title="No payments found"
          message={
            search || typeFilter !== 'all' || dateRange.from || dateRange.to
              ? 'Try different filters'
              : 'Add your first payment to get started'
          }
          actionLabel={
            !search && typeFilter === 'all' && !dateRange.from && !dateRange.to
              ? 'Add Payment'
              : undefined
          }
          onAction={
            !search && typeFilter === 'all' && !dateRange.from && !dateRange.to
              ? handleOpenCreateDialog
              : undefined
          }
        />
      );
    }

    return (
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Category</TableCell>
              <TableCell>Description</TableCell>
              <TableCell>Method</TableCell>
              <TableCell align="right">Amount</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {payments.map((payment) => (
              <TableRow key={payment.id} hover>
                <TableCell>
                  <Typography variant="body2">
                    {formatDate(payment.payment_date)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    icon={payment.type === 'income' ? <IncomeIcon /> : <ExpenseIcon />}
                    label={payment.type}
                    size="small"
                    color={payment.type === 'income' ? 'success' : 'error'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={payment.category || 'Uncategorized'}
                    size="small"
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    sx={{
                      maxWidth: 200,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {payment.description || '-'}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="body2" sx={{ textTransform: 'capitalize' }}>
                    {payment.payment_method.replace(/_/g, ' ')}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    fontWeight={600}
                    color={payment.type === 'income' ? 'success.main' : 'error.main'}
                  >
                    {payment.type === 'income' ? '+' : '-'}
                    {formatCurrency(payment.amount)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Tooltip title="Edit">
                    <IconButton
                      size="small"
                      onClick={() => handleOpenEditDialog(payment)}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => handleOpenDeleteDialog(payment)}
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
        title="Payments"
        subtitle="Manage your income and expenses"
        action={
          <Button
            variant="contained"
            color="primary"
            startIcon={<AddIcon />}
            onClick={handleOpenCreateDialog}
          >
            Add Payment
          </Button>
        }
      />

      {/* Summary Cards */}
      {summary && (
        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
          <Card sx={{ flex: 1, minWidth: 150, p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Total Income
            </Typography>
            <Typography variant="h5" color="success.main" fontWeight={600}>
              {formatCurrency(summary.total_earnings)}
            </Typography>
          </Card>
          <Card sx={{ flex: 1, minWidth: 150, p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Total Expenses
            </Typography>
            <Typography variant="h5" color="error.main" fontWeight={600}>
              {formatCurrency(summary.total_spends)}
            </Typography>
          </Card>
          <Card sx={{ flex: 1, minWidth: 150, p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Net Balance
            </Typography>
            <Typography
              variant="h5"
              fontWeight={600}
              color={
                summary.total_earnings - summary.total_spends >= 0
                  ? 'success.main'
                  : 'error.main'
              }
            >
              {formatCurrency(summary.total_earnings - summary.total_spends)}
            </Typography>
          </Card>
          <Card sx={{ flex: 1, minWidth: 150, p: 2 }}>
            <Typography variant="caption" color="text.secondary">
              Total Transactions
            </Typography>
            <Typography variant="h5" fontWeight={600}>
              {summary.payment_count}
            </Typography>
          </Card>
        </Box>
      )}

      {/* Filters */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by description..."
        />
        {isFetching && !showFullLoading && (
          <Typography variant="caption" color="text.secondary">
            Searching...
          </Typography>
        )}
        <ToggleButtonGroup
          value={typeFilter}
          exclusive
          onChange={handleTypeFilterChange}
          size="small"
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value={PAYMENT_TYPES.INCOME}>Income</ToggleButton>
          <ToggleButton value={PAYMENT_TYPES.EXPENSE}>Expense</ToggleButton>
        </ToggleButtonGroup>
        <TextField
          label="From Date"
          type="date"
          size="small"
          value={dateRange.from}
          onChange={(e) => setDateRange((prev) => ({ ...prev, from: e.target.value }))}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
        <TextField
          label="To Date"
          type="date"
          size="small"
          value={dateRange.to}
          onChange={(e) => setDateRange((prev) => ({ ...prev, to: e.target.value }))}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 160 }}
        />
      </Box>

      {/* Payments Table */}
      <Card>{renderTableContent()}</Card>

      {/* Payment Form Dialog */}
      <PaymentFormDialog
        open={formDialogOpen}
        payment={editingPayment}
        onClose={handleCloseFormDialog}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Payment"
        message={`Are you sure you want to delete this ${paymentToDelete?.type} of ${
          paymentToDelete ? formatCurrency(paymentToDelete.amount) : ''
        }? This action cannot be undone.`}
        confirmLabel="Delete"
        onConfirm={handleConfirmDelete}
        onCancel={handleCloseDeleteDialog}
        isLoading={deleteMutation.isPending}
      />
    </Box>
  );
};

export default PaymentsPage;
