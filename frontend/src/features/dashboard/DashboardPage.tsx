import React from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  CardHeader,
  useTheme,
  Table,
  TableBody,
  TableCell,
  TableRow,
  Chip,
  Button,
  Skeleton,
  Divider,
  List,
  ListItem,
  ListItemText,
  ListItemIcon,
  Avatar,
} from '@mui/material';
import {
  Inventory2 as ProductIcon,
  Warehouse as ContainerIcon,
  People as ContactIcon,
  Receipt as TransactionIcon,
  TrendingUp as IncomeIcon,
  TrendingDown as ExpenseIcon,
  AccountBalance as BalanceIcon,
  ArrowForward as ArrowIcon,
  ShoppingCart as SaleIcon,
  LocalShipping as PurchaseIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../stores/authStore';
import { useProducts } from '../../hooks/useProducts';
import { useContainers } from '../../hooks/useContainers';
import { useContacts } from '../../hooks/useContacts';
import { useTransactions } from '../../hooks/useTransactions';
import { usePaymentSummary } from '../../hooks/usePayments';
import { useInventoryAnalytics } from '../../hooks/useContainerProducts';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
  loading?: boolean;
  onClick?: () => void;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color, loading, onClick }) => {
  const theme = useTheme();

  return (
    <Card
      sx={{
        height: '100%',
        position: 'relative',
        overflow: 'visible',
        cursor: onClick ? 'pointer' : 'default',
        transition: 'transform 0.2s, box-shadow 0.2s',
        '&:hover': onClick
          ? {
              transform: 'translateY(-4px)',
              boxShadow: theme.shadows[8],
            }
          : {},
      }}
      onClick={onClick}
    >
      <CardContent sx={{ p: 3 }}>
        <Box
          sx={{
            position: 'absolute',
            top: -20,
            left: 24,
            width: 56,
            height: 56,
            borderRadius: 2,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: `linear-gradient(135deg, ${color} 0%, ${
              theme.palette.mode === 'dark' ? color + 'cc' : color + '99'
            } 100%)`,
            boxShadow: `0 4px 20px ${color}40`,
          }}
        >
          <Box sx={{ color: 'white', fontSize: 28, display: 'flex' }}>{icon}</Box>
        </Box>
        <Box sx={{ textAlign: 'right', mt: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          {loading ? (
            <Skeleton width={80} height={40} sx={{ ml: 'auto' }} />
          ) : (
            <Typography variant="h4" fontWeight={700}>
              {value}
            </Typography>
          )}
        </Box>
      </CardContent>
    </Card>
  );
};

const formatCurrency = (value: number) => {
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
};

const formatDate = (dateString: string) => {
  return new Date(dateString).toLocaleDateString('en-IN', {
    month: 'short',
    day: 'numeric',
  });
};

export const DashboardPage: React.FC = () => {
  const theme = useTheme();
  const navigate = useNavigate();
  const user = useAuthStore((state) => state.user);

  // Fetch all data
  const { data: products, isLoading: productsLoading } = useProducts();
  const { data: containers, isLoading: containersLoading } = useContainers();
  const { data: contacts, isLoading: contactsLoading } = useContacts();
  const { data: transactions, isLoading: transactionsLoading } = useTransactions({});
  const { data: paymentSummary, isLoading: paymentLoading } = usePaymentSummary();
  const { data: inventoryAnalytics, isLoading: inventoryLoading } = useInventoryAnalytics();

  // Compute stats
  const totalProducts = products?.length || 0;
  const totalContainers = containers?.length || 0;
  const totalContacts = contacts?.length || 0;
  const totalInventory = inventoryAnalytics?.totalQuantity || 0;

  // Financial stats from payment summary
  const totalIncome = paymentSummary?.total_earnings || 0;
  const totalExpenses = paymentSummary?.total_spends || 0;
  const netBalance = totalIncome - totalExpenses;

  // Recent transactions (last 5)
  const recentTransactions = transactions?.slice(0, 5) || [];

  // Outstanding contacts (with balance != 0)
  const outstandingContacts = contacts
    ?.filter((c) => c.balance !== 0)
    .sort((a, b) => Math.abs(b.balance) - Math.abs(a.balance))
    .slice(0, 5) || [];

  const stats = [
    {
      title: 'Total Products',
      value: totalProducts,
      icon: <ProductIcon />,
      color: theme.palette.primary.main,
      loading: productsLoading,
      onClick: () => navigate('/products'),
    },
    {
      title: 'Containers',
      value: totalContainers,
      icon: <ContainerIcon />,
      color: theme.palette.secondary.main,
      loading: containersLoading,
      onClick: () => navigate('/containers'),
    },
    {
      title: 'Contacts',
      value: totalContacts,
      icon: <ContactIcon />,
      color: theme.palette.info.main,
      loading: contactsLoading,
      onClick: () => navigate('/contacts'),
    },
    {
      title: 'Total Inventory',
      value: totalInventory.toLocaleString(),
      icon: <TransactionIcon />,
      color: theme.palette.success.main,
      loading: inventoryLoading,
      onClick: () => navigate('/inventory'),
    },
  ];

  return (
    <Box>
      {/* Header */}
      <Box sx={{ mb: 4 }}>
        <Typography variant="h4" fontWeight={700} gutterBottom>
          Welcome back, {user?.name || 'User'}!
        </Typography>
        <Typography variant="body1" color="text.secondary">
          Here's what's happening with your inventory today.
        </Typography>
      </Box>

      {/* Stats Grid */}
      <Grid container spacing={3} sx={{ mt: 2 }}>
        {stats.map((stat, index) => (
          <Grid size={{ xs: 12, sm: 6, lg: 3 }} key={index}>
            <StatCard {...stat} />
          </Grid>
        ))}
      </Grid>

      {/* Financial Overview */}
      <Grid container spacing={3} sx={{ mt: 4 }}>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            sx={{
              background: `linear-gradient(135deg, ${theme.palette.success.main} 0%, ${theme.palette.success.dark} 100%)`,
              color: 'white',
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <IncomeIcon />
                <Typography variant="subtitle1">Total Income</Typography>
              </Box>
              {paymentLoading ? (
                <Skeleton width={120} height={40} sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
              ) : (
                <Typography variant="h4" fontWeight={700}>
                  {formatCurrency(totalIncome)}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            sx={{
              background: `linear-gradient(135deg, ${theme.palette.error.main} 0%, ${theme.palette.error.dark} 100%)`,
              color: 'white',
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <ExpenseIcon />
                <Typography variant="subtitle1">Total Expenses</Typography>
              </Box>
              {paymentLoading ? (
                <Skeleton width={120} height={40} sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
              ) : (
                <Typography variant="h4" fontWeight={700}>
                  {formatCurrency(totalExpenses)}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
        <Grid size={{ xs: 12, md: 4 }}>
          <Card
            sx={{
              background:
                netBalance >= 0
                  ? `linear-gradient(135deg, ${theme.palette.info.main} 0%, ${theme.palette.info.dark} 100%)`
                  : `linear-gradient(135deg, ${theme.palette.warning.main} 0%, ${theme.palette.warning.dark} 100%)`,
              color: 'white',
            }}
          >
            <CardContent sx={{ p: 3 }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                <BalanceIcon />
                <Typography variant="subtitle1">Net Balance</Typography>
              </Box>
              {paymentLoading ? (
                <Skeleton width={120} height={40} sx={{ bgcolor: 'rgba(255,255,255,0.2)' }} />
              ) : (
                <Typography variant="h4" fontWeight={700}>
                  {formatCurrency(netBalance)}
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Recent Activity & Outstanding */}
      <Grid container spacing={3} sx={{ mt: 2 }}>
        {/* Recent Transactions */}
        <Grid size={{ xs: 12, md: 7 }}>
          <Card>
            <CardHeader
              title="Recent Transactions"
              action={
                <Button
                  endIcon={<ArrowIcon />}
                  onClick={() => navigate('/transactions')}
                  size="small"
                >
                  View All
                </Button>
              }
            />
            <Divider />
            {transactionsLoading ? (
              <Box sx={{ p: 2 }}>
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} height={60} sx={{ mb: 1 }} />
                ))}
              </Box>
            ) : recentTransactions.length === 0 ? (
              <CardContent>
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  No transactions yet
                </Typography>
              </CardContent>
            ) : (
              <Table>
                <TableBody>
                  {recentTransactions.map((txn) => (
                    <TableRow
                      key={txn.id}
                      hover
                      sx={{ cursor: 'pointer' }}
                      onClick={() => navigate(`/transactions/${txn.id}`)}
                    >
                      <TableCell sx={{ width: 50 }}>
                        <Avatar
                          sx={{
                            bgcolor:
                              txn.type === 'sale'
                                ? theme.palette.success.light
                                : theme.palette.primary.light,
                            width: 36,
                            height: 36,
                          }}
                        >
                          {txn.type === 'sale' ? (
                            <SaleIcon fontSize="small" />
                          ) : (
                            <PurchaseIcon fontSize="small" />
                          )}
                        </Avatar>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight={500}>
                          {txn.transaction_number}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {txn.contact?.name || 'Unknown'}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={txn.type}
                          size="small"
                          color={txn.type === 'sale' ? 'success' : 'primary'}
                          variant="outlined"
                        />
                      </TableCell>
                      <TableCell>
                        <Chip
                          label={txn.payment_status.replace(/_/g, ' ')}
                          size="small"
                          color={
                            txn.payment_status === 'paid'
                              ? 'success'
                              : txn.payment_status === 'partial'
                              ? 'warning'
                              : 'error'
                          }
                        />
                      </TableCell>
                      <TableCell align="right">
                        <Typography variant="body2" fontWeight={600}>
                          {formatCurrency(txn.total_amount)}
                        </Typography>
                        <Typography variant="caption" color="text.secondary">
                          {formatDate(txn.transaction_date)}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </Card>
        </Grid>

        {/* Outstanding Balances */}
        <Grid size={{ xs: 12, md: 5 }}>
          <Card>
            <CardHeader
              title="Outstanding Balances"
              action={
                <Button
                  endIcon={<ArrowIcon />}
                  onClick={() => navigate('/contacts')}
                  size="small"
                >
                  View All
                </Button>
              }
            />
            <Divider />
            {contactsLoading ? (
              <Box sx={{ p: 2 }}>
                {[1, 2, 3].map((i) => (
                  <Skeleton key={i} height={50} sx={{ mb: 1 }} />
                ))}
              </Box>
            ) : outstandingContacts.length === 0 ? (
              <CardContent>
                <Typography variant="body2" color="text.secondary" textAlign="center">
                  No outstanding balances
                </Typography>
              </CardContent>
            ) : (
              <List disablePadding>
                {outstandingContacts.map((contact, index) => (
                  <React.Fragment key={contact.id}>
                    <ListItem
                      sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
                      onClick={() => navigate(`/contacts/${contact.id}`)}
                    >
                      <ListItemIcon>
                        <Avatar
                          sx={{
                            bgcolor:
                              contact.balance > 0
                                ? theme.palette.success.light
                                : theme.palette.error.light,
                            width: 36,
                            height: 36,
                          }}
                        >
                          <ContactIcon fontSize="small" />
                        </Avatar>
                      </ListItemIcon>
                      <ListItemText
                        primary={contact.name}
                        secondary={contact.type}
                        primaryTypographyProps={{ fontWeight: 500 }}
                      />
                      <Typography
                        variant="body2"
                        fontWeight={600}
                        color={contact.balance > 0 ? 'success.main' : 'error.main'}
                      >
                        {contact.balance > 0 ? '+' : ''}
                        {formatCurrency(contact.balance)}
                      </Typography>
                    </ListItem>
                    {index < outstandingContacts.length - 1 && <Divider />}
                  </React.Fragment>
                ))}
              </List>
            )}
          </Card>
        </Grid>
      </Grid>

      {/* Quick Actions */}
      <Card sx={{ mt: 3 }}>
        <CardHeader title="Quick Actions" />
        <Divider />
        <CardContent>
          <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
            <Button
              variant="contained"
              color="success"
              startIcon={<SaleIcon />}
              onClick={() => navigate('/transactions/new-sale')}
            >
              New Sale
            </Button>
            <Button
              variant="contained"
              color="primary"
              startIcon={<PurchaseIcon />}
              onClick={() => navigate('/transactions/new-purchase')}
            >
              New Purchase
            </Button>
            <Button
              variant="outlined"
              startIcon={<ProductIcon />}
              onClick={() => navigate('/products')}
            >
              Add Product
            </Button>
            <Button
              variant="outlined"
              startIcon={<ContactIcon />}
              onClick={() => navigate('/contacts')}
            >
              Add Contact
            </Button>
            <Button
              variant="outlined"
              startIcon={<ExpenseIcon />}
              onClick={() => navigate('/payments')}
            >
              Record Payment
            </Button>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default DashboardPage;
