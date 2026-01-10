import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Chip,
  Tooltip,
  IconButton,
  Paper,
  alpha,
} from '@mui/material';
import {
  Inventory2 as InventoryIcon,
  Category as ProductIcon,
  Warehouse as ContainerIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { useInventoryAnalytics, useContainerSearch } from '../../hooks/useContainerProducts';

interface StatCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: 'primary' | 'secondary' | 'success' | 'warning' | 'error' | 'info';
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color }) => (
  <Card
    sx={{
      height: '100%',
      background: (theme) =>
        `linear-gradient(135deg, ${alpha(theme.palette[color].main, 0.1)} 0%, ${alpha(
          theme.palette[color].light,
          0.05
        )} 100%)`,
      border: (theme) => `1px solid ${alpha(theme.palette[color].main, 0.2)}`,
    }}
  >
    <CardContent>
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          <Typography variant="h4" fontWeight={700} color={`${color}.main`}>
            {typeof value === 'number' ? value.toLocaleString() : value}
          </Typography>
        </Box>
        <Box
          sx={{
            p: 1.5,
            borderRadius: 2,
            bgcolor: (theme) => alpha(theme.palette[color].main, 0.15),
            color: `${color}.main`,
          }}
        >
          {icon}
        </Box>
      </Box>
    </CardContent>
  </Card>
);

export const InventoryPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  // Analytics data
  const {
    data: analytics,
    isLoading: analyticsLoading,
    isError: analyticsError,
    refetch: refetchAnalytics,
  } = useInventoryAnalytics();

  // Search results
  const {
    data: searchResults,
    isLoading: searchLoading,
    isFetching: searchFetching,
  } = useContainerSearch(searchQuery);

  const showSearchResults = searchQuery.trim().length > 0;

  // Render search results table
  const renderSearchResults = () => {
    if (searchLoading) {
      return <LoadingState message="Searching..." />;
    }

    if (!searchResults || searchResults.length === 0) {
      return (
        <EmptyState
          title="No results found"
          message={`No products matching "${searchQuery}" found in any container`}
        />
      );
    }

    return (
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Product</TableCell>
              <TableCell>Size</TableCell>
              <TableCell>Packing</TableCell>
              <TableCell>Container</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {searchResults.map((item) => (
              <TableRow key={item.id} hover>
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {item.product?.name || '-'}
                  </Typography>
                </TableCell>
                <TableCell>{item.product?.size || '-'}</TableCell>
                <TableCell>{item.product?.packing || '-'}</TableCell>
                <TableCell>
                  <Chip
                    label={item.container?.name || '-'}
                    size="small"
                    variant="outlined"
                    color="primary"
                    onClick={() => item.container && navigate(`/containers/${item.container.id}`)}
                    sx={{ cursor: 'pointer' }}
                  />
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={item.quantity}
                    size="small"
                    color={item.quantity > 0 ? 'success' : 'default'}
                    variant={item.quantity > 0 ? 'filled' : 'outlined'}
                  />
                </TableCell>
                <TableCell align="center">
                  {item.product && (
                    <Tooltip title="View Product">
                      <IconButton
                        size="small"
                        onClick={() => navigate(`/products/${item.product!.id}`)}
                      >
                        <ViewIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  )}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    );
  };

  if (analyticsLoading && !analytics) {
    return <LoadingState message="Loading inventory analytics..." fullPage />;
  }

  if (analyticsError) {
    return <ErrorState onRetry={() => refetchAnalytics()} />;
  }

  return (
    <Box>
      <PageHeader
        title="Inventory"
        subtitle="Overview of your inventory across all containers"
      />

      {/* Analytics Cards */}
      <Grid container spacing={3} sx={{ mb: 4 }}>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            title="Total Products"
            value={analytics?.totalProducts || 0}
            icon={<ProductIcon fontSize="large" />}
            color="primary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            title="Total Containers"
            value={analytics?.totalContainers || 0}
            icon={<ContainerIcon fontSize="large" />}
            color="secondary"
          />
        </Grid>
        <Grid size={{ xs: 12, sm: 4 }}>
          <StatCard
            title="Total Stock Quantity"
            value={analytics?.totalQuantity || 0}
            icon={<InventoryIcon fontSize="large" />}
            color="success"
          />
        </Grid>
      </Grid>

      {/* Search Section */}
      <Paper sx={{ p: 3, mb: 3 }}>
        <Typography variant="h6" gutterBottom>
          Find Products in Containers
        </Typography>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Search by product name to see which containers hold that product and their quantities.
        </Typography>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
          <SearchInput
            value={searchQuery}
            onChange={setSearchQuery}
            placeholder="Search by product name..."
          />
          {searchFetching && !searchLoading && (
            <Typography variant="caption" color="text.secondary">
              Searching...
            </Typography>
          )}
        </Box>
      </Paper>

      {/* Search Results or Quick Links */}
      {showSearchResults ? (
        <Card>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Search Results
              {searchResults && (
                <Chip
                  label={`${searchResults.length} found`}
                  size="small"
                  sx={{ ml: 1 }}
                />
              )}
            </Typography>
            {renderSearchResults()}
          </CardContent>
        </Card>
      ) : (
        <Grid container spacing={3}>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card
              sx={{
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate('/products')}
            >
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    bgcolor: 'primary.light',
                    color: 'primary.contrastText',
                  }}
                >
                  <ProductIcon fontSize="large" />
                </Box>
                <Box>
                  <Typography variant="h6">Manage Products</Typography>
                  <Typography variant="body2" color="text.secondary">
                    View and manage your product catalog
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12, md: 6 }}>
            <Card
              sx={{
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate('/containers')}
            >
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    bgcolor: 'secondary.light',
                    color: 'secondary.contrastText',
                  }}
                >
                  <ContainerIcon fontSize="large" />
                </Box>
                <Box>
                  <Typography variant="h6">Manage Containers</Typography>
                  <Typography variant="body2" color="text.secondary">
                    View and manage your storage containers
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
          <Grid size={{ xs: 12 }}>
            <Card
              sx={{
                cursor: 'pointer',
                transition: 'transform 0.2s, box-shadow 0.2s',
                '&:hover': {
                  transform: 'translateY(-4px)',
                  boxShadow: 4,
                },
              }}
              onClick={() => navigate('/inventory/logs')}
            >
              <CardContent sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <Box
                  sx={{
                    p: 2,
                    borderRadius: 2,
                    bgcolor: 'info.light',
                    color: 'info.contrastText',
                  }}
                >
                  <InventoryIcon fontSize="large" />
                </Box>
                <Box>
                  <Typography variant="h6">Inventory Logs</Typography>
                  <Typography variant="body2" color="text.secondary">
                    View the history of all inventory changes
                  </Typography>
                </Box>
              </CardContent>
            </Card>
          </Grid>
        </Grid>
      )}
    </Box>
  );
};

export default InventoryPage;
