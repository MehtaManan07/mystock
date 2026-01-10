import React, { useState, useMemo } from 'react';
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
} from '@mui/material';
import {
  Visibility as ViewIcon,
} from '@mui/icons-material';
import { format } from 'date-fns';
import { PageHeader } from '../../components/common/PageHeader';
import { SearchInput } from '../../components/common/SearchInput';
import { LoadingState } from '../../components/common/LoadingState';
import { ErrorState } from '../../components/common/ErrorState';
import { EmptyState } from '../../components/common/EmptyState';
import { useInventoryLogs } from '../../hooks/useInventoryLogs';
import type { InventoryLog } from '../../types';

type ActionFilter = 'all' | 'add' | 'remove' | 'transfer' | 'sale' | 'purchase' | 'adjustment';

export const InventoryLogsPage: React.FC = () => {
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');
  const [actionFilter, setActionFilter] = useState<ActionFilter>('all');

  const {
    data: logs,
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useInventoryLogs();

  const showFullLoading = isLoading && !logs;

  // Filter logs based on search and action filter
  const filteredLogs = useMemo(() => {
    if (!logs) return [];

    return logs.filter((log) => {
      // Action filter
      if (actionFilter !== 'all' && log.action !== actionFilter) {
        return false;
      }

      // Search filter (by note)
      if (searchQuery.trim()) {
        const query = searchQuery.toLowerCase();
        const matchesNote = log.note?.toLowerCase().includes(query);
        const matchesAction = log.action.toLowerCase().includes(query);
        if (!matchesNote && !matchesAction) {
          return false;
        }
      }

      return true;
    });
  }, [logs, searchQuery, actionFilter]);

  const formatDate = (dateString: string) => {
    return format(new Date(dateString), 'dd MMM yyyy, HH:mm');
  };

  const getActionColor = (action: string) => {
    switch (action) {
      case 'add':
      case 'purchase':
        return 'success';
      case 'remove':
      case 'sale':
        return 'error';
      case 'transfer':
        return 'info';
      case 'adjustment':
        return 'warning';
      default:
        return 'default';
    }
  };

  const renderTableContent = () => {
    if (showFullLoading) {
      return <LoadingState message="Loading inventory logs..." />;
    }

    if (isError) {
      return <ErrorState onRetry={() => refetch()} />;
    }

    if (!filteredLogs || filteredLogs.length === 0) {
      return (
        <EmptyState
          title="No logs found"
          message={
            searchQuery || actionFilter !== 'all'
              ? 'Try different filters'
              : 'No inventory activity has been recorded yet'
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
              <TableCell>Action</TableCell>
              <TableCell>Product ID</TableCell>
              <TableCell>Container ID</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell>Note</TableCell>
              <TableCell align="center">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {filteredLogs.map((log: InventoryLog) => (
              <TableRow key={log.id} hover>
                <TableCell>
                  <Typography variant="caption">
                    {formatDate(log.timestamp || log.created_at)}
                  </Typography>
                </TableCell>
                <TableCell>
                  <Chip
                    label={log.action}
                    size="small"
                    color={getActionColor(log.action) as 'success' | 'error' | 'info' | 'warning' | 'default'}
                    variant="outlined"
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={`Product #${log.product_id}`}
                    size="small"
                    variant="outlined"
                    onClick={() => navigate(`/products/${log.product_id}`)}
                    sx={{ cursor: 'pointer' }}
                  />
                </TableCell>
                <TableCell>
                  <Chip
                    label={`Container #${log.container_id}`}
                    size="small"
                    variant="outlined"
                    onClick={() => navigate(`/containers/${log.container_id}`)}
                    sx={{ cursor: 'pointer' }}
                  />
                </TableCell>
                <TableCell align="right">
                  <Chip
                    label={log.action === 'remove' || log.action === 'sale' ? `-${log.quantity}` : `+${log.quantity}`}
                    size="small"
                    color={log.action === 'remove' || log.action === 'sale' ? 'error' : 'success'}
                    variant="filled"
                  />
                </TableCell>
                <TableCell>
                  <Typography
                    variant="body2"
                    color="text.secondary"
                    sx={{
                      maxWidth: 200,
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {log.note || '-'}
                  </Typography>
                </TableCell>
                <TableCell align="center">
                  <Tooltip title="View Product">
                    <IconButton
                      size="small"
                      onClick={() => navigate(`/products/${log.product_id}`)}
                    >
                      <ViewIcon fontSize="small" />
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
        title="Inventory Logs"
        subtitle={logs ? `${filteredLogs.length} log entries` : 'History of inventory changes'}
        breadcrumbs={[
          { label: 'Inventory', path: '/inventory' },
          { label: 'Logs' },
        ]}
      />

      {/* Filters - always visible */}
      <Box sx={{ mb: 3, display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
        <SearchInput
          value={searchQuery}
          onChange={setSearchQuery}
          placeholder="Search by note or action..."
        />

        <ToggleButtonGroup
          value={actionFilter}
          exclusive
          onChange={(_, value) => value && setActionFilter(value)}
          size="small"
        >
          <ToggleButton value="all">All</ToggleButton>
          <ToggleButton value="add">Add</ToggleButton>
          <ToggleButton value="remove">Remove</ToggleButton>
          <ToggleButton value="sale">Sale</ToggleButton>
          <ToggleButton value="purchase">Purchase</ToggleButton>
          <ToggleButton value="adjustment">Adjustment</ToggleButton>
        </ToggleButtonGroup>

        {isFetching && !showFullLoading && (
          <Typography variant="caption" color="text.secondary">
            Refreshing...
          </Typography>
        )}
      </Box>

      {/* Logs table */}
      <Card>{renderTableContent()}</Card>
    </Box>
  );
};

export default InventoryLogsPage;
