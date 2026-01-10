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
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  ArrowBack as BackIcon,
  Inventory as InventoryIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { ContainerFormDialog } from './components/ContainerFormDialog';
import { ManageProductsDialog } from './components/ManageProductsDialog';
import { useContainer, useUpdateContainer, useDeleteContainer } from '../../hooks/useContainers';
import type { CreateContainerDto, UpdateContainerDto } from '../../types';
import { format } from 'date-fns';

export const ContainerDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const containerId = parseInt(id || '0', 10);

  // Dialog states
  const [editDialogOpen, setEditDialogOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [manageProductsDialogOpen, setManageProductsDialogOpen] = useState(false);

  // Data fetching
  const { data: container, isLoading, isError, refetch } = useContainer(containerId);

  // Mutations
  const updateMutation = useUpdateContainer();
  const deleteMutation = useDeleteContainer();

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'dd MMM yyyy, HH:mm');
  };

  const handleEditSubmit = (data: CreateContainerDto) => {
    updateMutation.mutate(
      { id: containerId, data: data as UpdateContainerDto },
      {
        onSuccess: () => setEditDialogOpen(false),
      }
    );
  };

  const handleConfirmDelete = () => {
    deleteMutation.mutate(containerId, {
      onSuccess: () => {
        navigate('/containers');
      },
    });
  };

  // Calculate total quantity from products
  const totalQuantity = container?.products?.reduce(
    (sum, cp) => sum + cp.quantity,
    0
  ) || 0;

  if (isLoading) {
    return <LoadingState message="Loading container details..." fullPage />;
  }

  if (isError || !container) {
    return <ErrorState onRetry={() => refetch()} />;
  }

  return (
    <Box>
      <PageHeader
        title={container.name}
        subtitle={`${container.type} container`}
        breadcrumbs={[
          { label: 'Containers', path: '/containers' },
          { label: container.name },
        ]}
      />

      {/* Action buttons */}
      <Box sx={{ display: 'flex', gap: 1, mb: 3 }}>
        <Tooltip title="Back to Containers">
          <IconButton onClick={() => navigate('/containers')}>
            <BackIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Manage Products">
          <IconButton color="primary" onClick={() => setManageProductsDialogOpen(true)}>
            <InventoryIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Edit Container">
          <IconButton onClick={() => setEditDialogOpen(true)}>
            <EditIcon />
          </IconButton>
        </Tooltip>
        <Tooltip title="Delete Container">
          <IconButton color="error" onClick={() => setDeleteDialogOpen(true)}>
            <DeleteIcon />
          </IconButton>
        </Tooltip>
      </Box>

      <Grid container spacing={3}>
        {/* Container Info Card */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Container Information
              </Typography>
              <Divider sx={{ mb: 2 }} />
              
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Name
                  </Typography>
                  <Typography variant="body1" fontWeight={600}>
                    {container.name}
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Type
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip
                      label={container.type}
                      color={container.type === 'mixed' ? 'secondary' : 'primary'}
                      size="small"
                    />
                  </Box>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Products Stored
                  </Typography>
                  <Typography variant="body1">
                    {container.products?.length || 0} products
                  </Typography>
                </Box>
                <Box>
                  <Typography variant="caption" color="text.secondary">
                    Total Quantity
                  </Typography>
                  <Box sx={{ mt: 0.5 }}>
                    <Chip
                      label={totalQuantity}
                      color={totalQuantity > 0 ? 'primary' : 'default'}
                    />
                  </Box>
                </Box>
              </Box>
            </CardContent>
          </Card>
        </Grid>

        {/* Products Card */}
        <Grid size={{ xs: 12, md: 8 }}>
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Products in Container ({container.products?.length || 0})
              </Typography>
              <Divider sx={{ mb: 2 }} />
              
              {container.products && container.products.length > 0 ? (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Product</TableCell>
                        <TableCell>Size</TableCell>
                        <TableCell>Packing</TableCell>
                        <TableCell align="right">Quantity</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {container.products.map((cp) => (
                        <TableRow
                          key={cp.product.id}
                          hover
                          sx={{ cursor: 'pointer' }}
                          onClick={() => navigate(`/products/${cp.product.id}`)}
                        >
                          <TableCell>
                            <Typography variant="body2" fontWeight={500}>
                              {cp.product.name}
                            </Typography>
                          </TableCell>
                          <TableCell>{cp.product.size}</TableCell>
                          <TableCell>{cp.product.packing}</TableCell>
                          <TableCell align="right">{cp.quantity}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No products stored in this container yet.
                </Typography>
              )}
            </CardContent>
          </Card>

          {/* Recent Logs Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Activity ({container.logs?.length || 0} logs)
              </Typography>
              <Divider sx={{ mb: 2 }} />
              
              {container.logs && container.logs.length > 0 ? (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Action</TableCell>
                        <TableCell>Product</TableCell>
                        <TableCell align="right">Quantity</TableCell>
                        <TableCell>Date</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {container.logs.slice(0, 10).map((log) => (
                        <TableRow key={log.id} hover>
                          <TableCell>
                            <Chip
                              label={log.action}
                              size="small"
                              color={
                                log.action === 'add' || log.action === 'purchase'
                                  ? 'success'
                                  : log.action === 'remove' || log.action === 'sale'
                                  ? 'error'
                                  : 'default'
                              }
                              variant="outlined"
                            />
                          </TableCell>
                          <TableCell>{log.product?.name || '-'}</TableCell>
                          <TableCell align="right">{log.quantity}</TableCell>
                          <TableCell>
                            <Typography variant="caption">
                              {formatDate(log.created_at)}
                            </Typography>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary">
                  No activity logs for this container.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>

      {/* Edit Dialog */}
      <ContainerFormDialog
        open={editDialogOpen}
        container={{
          ...container,
          productCount: container.products?.length || 0,
        }}
        isLoading={updateMutation.isPending}
        onSubmit={handleEditSubmit}
        onClose={() => setEditDialogOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Container"
        message={`Are you sure you want to delete "${container.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        confirmColor="error"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={() => setDeleteDialogOpen(false)}
      />

      {/* Manage Products Dialog */}
      <ManageProductsDialog
        open={manageProductsDialogOpen}
        containerId={containerId}
        containerName={container.name}
        currentProducts={container.products || []}
        onClose={() => setManageProductsDialogOpen(false)}
        onSuccess={() => refetch()}
      />
    </Box>
  );
};

export default ContainerDetailPage;
