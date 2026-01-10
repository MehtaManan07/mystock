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
  IconButton,
  Chip,
  Tooltip,
  Typography,
} from '@mui/material';
import {
  Edit as EditIcon,
  Delete as DeleteIcon,
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { ConfirmDialog } from '../../components/common/ConfirmDialog';
import { ContainerFormDialog } from './components/ContainerFormDialog';
import { useContainers, useCreateContainer, useUpdateContainer, useDeleteContainer } from '../../hooks/useContainers';
import type { Container, CreateContainerDto, UpdateContainerDto } from '../../types';

export const ContainersPage: React.FC = () => {
  const navigate = useNavigate();
  
  // Search state
  const [search, setSearch] = useState('');
  
  // Dialog states
  const [formDialogOpen, setFormDialogOpen] = useState(false);
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [containerToDelete, setContainerToDelete] = useState<Container | null>(null);

  // Data fetching
  const { data: containers, isLoading, isFetching, isError, refetch } = useContainers(search || undefined);
  
  // Only show full loading on initial load (no data yet)
  const showFullLoading = isLoading && !containers;
  
  // Mutations
  const createMutation = useCreateContainer();
  const updateMutation = useUpdateContainer();
  const deleteMutation = useDeleteContainer();

  // Handlers
  const handleOpenCreateDialog = () => {
    setSelectedContainer(null);
    setFormDialogOpen(true);
  };

  const handleOpenEditDialog = (container: Container) => {
    setSelectedContainer(container);
    setFormDialogOpen(true);
  };

  const handleCloseFormDialog = () => {
    setFormDialogOpen(false);
    setSelectedContainer(null);
  };

  const handleFormSubmit = (data: CreateContainerDto) => {
    if (selectedContainer) {
      updateMutation.mutate(
        { id: selectedContainer.id, data: data as UpdateContainerDto },
        {
          onSuccess: () => handleCloseFormDialog(),
        }
      );
    } else {
      createMutation.mutate(data, {
        onSuccess: () => handleCloseFormDialog(),
      });
    }
  };

  const handleOpenDeleteDialog = (container: Container) => {
    setContainerToDelete(container);
    setDeleteDialogOpen(true);
  };

  const handleCloseDeleteDialog = () => {
    setDeleteDialogOpen(false);
    setContainerToDelete(null);
  };

  const handleConfirmDelete = () => {
    if (containerToDelete) {
      deleteMutation.mutate(containerToDelete.id, {
        onSuccess: () => handleCloseDeleteDialog(),
      });
    }
  };

  const handleViewContainer = (container: Container) => {
    navigate(`/containers/${container.id}`);
  };

  // Render content for the table area
  const renderTableContent = () => {
    if (showFullLoading) {
      return <LoadingState message="Loading containers..." />;
    }
    
    if (isError) {
      return <ErrorState onRetry={() => refetch()} />;
    }
    
    if (!containers || containers.length === 0) {
      return (
        <EmptyState
          title="No containers found"
          message={search ? 'Try a different search term' : 'Add your first container to get started'}
          actionLabel={!search ? 'Add Container' : undefined}
          onAction={!search ? handleOpenCreateDialog : undefined}
        />
      );
    }
    
    return (
      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Name</TableCell>
              <TableCell>Type</TableCell>
              <TableCell align="right">Products</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {containers.map((container) => (
              <TableRow
                key={container.id}
                hover
                sx={{ cursor: 'pointer' }}
                onClick={() => handleViewContainer(container)}
              >
                <TableCell>
                  <Typography variant="body2" fontWeight={600}>
                    {container.name}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={container.type}
                    size="small"
                    color={container.type === 'mixed' ? 'secondary' : 'primary'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={container.productCount}
                    size="small"
                    color={container.productCount > 0 ? 'primary' : 'default'}
                    variant={container.productCount > 0 ? 'filled' : 'outlined'}
                  />
                </TableCell>
                <TableCell align="center" onClick={(e) => e.stopPropagation()}>
                  <Tooltip title="View">
                    <IconButton
                      size="small"
                      onClick={() => handleViewContainer(container)}
                    >
                      <ViewIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Edit">
                    <IconButton
                      size="small"
                      onClick={() => handleOpenEditDialog(container)}
                    >
                      <EditIcon fontSize="small" />
                    </IconButton>
                  </Tooltip>
                  <Tooltip title="Delete">
                    <IconButton
                      size="small"
                      color="error"
                      onClick={() => handleOpenDeleteDialog(container)}
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
        title="Containers"
        subtitle={containers ? `${containers.length} containers in your inventory` : 'Manage your storage containers'}
        actionLabel="Add Container"
        onAction={handleOpenCreateDialog}
      />

      {/* Search bar - always visible */}
      <Box sx={{ mb: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <SearchInput
          value={search}
          onChange={setSearch}
          placeholder="Search by name..."
        />
        {isFetching && !showFullLoading && (
          <Typography variant="caption" color="text.secondary">
            Searching...
          </Typography>
        )}
      </Box>

      {/* Containers table */}
      <Card>
        {renderTableContent()}
      </Card>

      {/* Create/Edit Dialog */}
      <ContainerFormDialog
        open={formDialogOpen}
        container={selectedContainer}
        isLoading={createMutation.isPending || updateMutation.isPending}
        onSubmit={handleFormSubmit}
        onClose={handleCloseFormDialog}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={deleteDialogOpen}
        title="Delete Container"
        message={`Are you sure you want to delete "${containerToDelete?.name}"? This action cannot be undone.`}
        confirmLabel="Delete"
        confirmColor="error"
        isLoading={deleteMutation.isPending}
        onConfirm={handleConfirmDelete}
        onCancel={handleCloseDeleteDialog}
      />
    </Box>
  );
};

export default ContainersPage;
