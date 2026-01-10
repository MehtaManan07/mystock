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
  Chip,
  Typography,
  ToggleButton,
  ToggleButtonGroup,
  IconButton,
  Tooltip,
  Button,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  TextField,
} from '@mui/material';
import {
  Visibility as ViewIcon,
  Delete as DeleteIcon,
  Add as AddIcon,
  ShoppingCart as SaleIcon,
  LocalShipping as PurchaseIcon,
  KeyboardArrowDown as ArrowDownIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { useTransactions, useDeleteTransaction } from '../../hooks/useTransactions';
import { TRANSACTION_TYPES, PAYMENT_STATUS, type TransactionType, type PaymentStatus } from '../../constants';
import type { Transaction, TransactionFilters } from '../../types';

export const TransactionsPage: React.FC = () => {
  const navigate = useNavigate();
  
  // Filter states
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<TransactionType | 'all'>('all');
  const [statusFilter, setStatusFilter] = useState<PaymentStatus | 'all'>('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  
  // Menu state for create button
  const [createMenuAnchor, setCreateMenuAnchor] = useState<null | HTMLElement>(null);
  
  // Delete dialog state
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [transactionToDelete, setTransactionToDelete] = useState<Transaction | null>(null);

  // Build filters
  const filters: TransactionFilters = {
    search: search || undefined,
    type: typeFilter !== 'all' ? typeFilter : undefined,
    payment_status: statusFilter !== 'all' ? statusFilter : undefined,
    from_date: fromDate || undefined,
    to_date: toDate || undefined,
  };

  // Data fetching
  const { data: transactions, isLoading, isFetching, isError, refetch } = useTransactions(filters);
  const deleteMutation = useDeleteTransaction();

  const showFullLoading = isLoading && !transactions;
  const hasActiveFilters = search || typeFilter !== 'all' || statusFilter !== 'all' || fromDate || toDate;

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

  const handleOpenDeleteDialog = (transaction: Transaction) => {
    setTransactionToDelete(transaction);
    setDeleteDialogOpen(true);
  };

  const handleConfirmDelete = () => {
    if (transactionToDelete) {
      deleteMutation.mutate(transactionToDelete.id, {
        onSuccess: () => {
          setDeleteDialogOpen(false);
          setTransactionToDelete(null);
        },
      });
    }
  };

  const renderTableContent = () => {
    if (showFullLoading) {
      return <LoadingState message="Loading transactions..." />;
    }

    if (isError) {
      return <ErrorState onRetry={() => refetch()} />;
    }

    if (!transactions || transactions.length === 0) {
      return (
        <EmptyState
          title="No transactions found"
          message={hasActiveFilters ? 'Try different filters' : 'Create your first sale or purchase to get started'}
        />
      );
    }

    return (
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Transaction #</TableCell>
              <TableCell>Date</TableCell>
              <TableCell>Type</TableCell>
              <TableCell>Contact</TableCell>
              <TableCell align="right">Total</TableCell>
              <TableCell align="right">Paid</TableCell>
              <TableCell align="right">Balance</TableCell>
              <TableCell>Status</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {transactions.map((transaction) => (
              <TableRow
                key={transaction.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => navigate(`/transactions/${transaction.id}`)}
              >
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {transaction.transaction_number}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Typography variant="caption">
                    {formatDate(transaction.transaction_date)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    icon={transaction.type === TRANSACTION_TYPES.SALE ? <SaleIcon /> : <PurchaseIcon />}
                    label={transaction.type}
                    size="small"
                    color={transaction.type === TRANSACTION_TYPES.SALE ? 'primary' : 'secondary'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Typography variant="body2">
                    {transaction.contact.name}
                  </Typography>
                  <Typography variant="caption" color="text.secondary">
                    {transaction.contact.phone}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" fontWeight={500}>
                    {formatCurrency(transaction.total_amount)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography variant="body2" color="success.main">
                    {formatCurrency(transaction.paid_amount)}
                  </Typography>
                </TableCell>
                <TableCell align="right">
                  <Typography
                    variant="body2"
                    color={transaction.balance_due > 0 ? 'error.main' : 'text.secondary'}
                    fontWeight={transaction.balance_due > 0 ? 600 : 400}
                  >
                    {formatCurrency(transaction.balance_due)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={transaction.payment_status}
                    size="small"
                    color={getStatusColor(transaction.payment_status)}
                    variant="filled"
                  />
                </TableCell>
                <TableCell align="center" onClick={(e) => e.stopPropagation()}>
                  <Tooltip title="View">
                    <IconButton
                      size="small"
                      onClick={() => navigate(`/transactions/${transaction.id}`)}
                    >
                      <ViewIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => handleOpenDeleteDialog(transaction)}
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
        title="Transactions"
        subtitle={transactions ? `${transactions.length} transactions` : 'Sales and purchases'}
      />

      {/* Action Button */}
      <Box sx={{ mb: 3 }}>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          endIcon={<ArrowDownIcon />}
          onClick={(e) => setCreateMenuAnchor(e.currentTarget)}
        >
          New Transaction
        </Button>
        <Menu
          anchorEl={createMenuAnchor}
          open={Boolean(createMenuAnchor)}
          onClose={() => setCreateMenuAnchor(null)}
        >
          <MenuItem onClick={() => { setCreateMenuAnchor(null); navigate('/transactions/new-sale'); }}>
            <ListItemIcon>
              <SaleIcon fontSize="small" color="primary" />
            </ListItemIcon>
            <ListItemText>New Sale</ListItemText>
          </MenuItem>
          <MenuItem onClick={() => { setCreateMenuAnchor(null); navigate('/transactions/new-purchase'); }}>
            <ListItemIcon>
              <PurchaseIcon fontSize="small" color="secondary" />
            </ListItemIcon>
            <ListItemText>New Purchase</ListItemText>
          </MenuItem>
        </Menu>
      </Box>

      {/* Filters - always visible */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by transaction # or notes..."
        />

        <ToggleButtonGroup
          value={typeFilter}
          exclusive
          onChange={(_, value) => value && setTypeFilter(value)}
          size="small"
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value={TRANSACTION_TYPES.SALE}>Sales</ToggleButton>
          <ToggleButton value={TRANSACTION_TYPES.PURCHASE}>Purchases</ToggleButton>
        </ToggleButtonGroup>

        <ToggleButtonGroup
          value={statusFilter}
          exclusive
          onChange={(_, value) => value && setStatusFilter(value)}
          size="small"
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value={PAYMENT_STATUS.PAID}>Paid</ToggleButton>
          <ToggleButton value={PAYMENT_STATUS.PARTIAL}>Partial</ToggleButton>
          <ToggleButton value={PAYMENT_STATUS.UNPAID}>Unpaid</ToggleButton>
        </ToggleButtonGroup>

        <TextField
          type="date"
          size="small"
          label="From"
          value={fromDate}
          onChange={(e) => setFromDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 150 }}
        />
        <TextField
          type="date"
          size="small"
          label="To"
          value={toDate}
          onChange={(e) => setToDate(e.target.value)}
          InputLabelProps={{ shrink: true }}
          sx={{ width: 150 }}
        />

        {isFetching && !showFullLoading && (
          <Typography variant="caption" color="text.secondary">
            Loading...
          </Typography>
        )}
      </Box>

      {/* Transactions table */}
      <Card>{renderTableContent()}</Card>

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Transaction"
        message={`Are you sure you want to delete "${transactionToDelete?.transaction_number}"? This will reverse all inventory and balance changes. This action cannot be undone.`}
        confirmLabel="Delete"
        confirmColor="error"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteDialogOpen(false)}
      />
    </Box>
  );
};

export default TransactionsPage;
