import React, { useEffect } from 'react';
import {
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Button,
  TextField,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  FormHelperText,
  Grid,
} from '@mui/material';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { CONTAINER_TYPES, type ContainerType } from '../../../constants';
import type { Container, CreateContainerDto } from '../../../types';

// Validation schema
const containerSchema = z.object({
  name: z.string().min(1, 'Name is required').max(255),
  type: z.enum([CONTAINER_TYPES.SINGLE, CONTAINER_TYPES.MIXED]),
});

type ContainerFormData = z.infer<typeof containerSchema>;

interface ContainerFormDialogProps {
  open: boolean;
  container?: Container | null;
  isLoading?: boolean;
  onSubmit: (data: CreateContainerDto) => void;
  onClose: () => void;
}

const containerTypeOptions: { value: ContainerType; label: string }[] = [
  { value: CONTAINER_TYPES.SINGLE, label: 'Single (one product only)' },
  { value: CONTAINER_TYPES.MIXED, label: 'Mixed (multiple products)' },
];

export const ContainerFormDialog: React.FC<ContainerFormDialogProps> = ({
  open,
  container,
  isLoading = false,
  onSubmit,
  onClose,
}) => {
  const isEditing = !!container;

  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ContainerFormData>({
    resolver: zodResolver(containerSchema),
    defaultValues: {
      name: '',
      type: CONTAINER_TYPES.MIXED,
    },
  });

  // Reset form when dialog opens/closes or container changes
  useEffect(() => {
    if (open) {
      if (container) {
        reset({
          name: container.name,
          type: container.type as ContainerType,
        });
      } else {
        reset({
          name: '',
          type: CONTAINER_TYPES.MIXED,
        });
      }
    }
  }, [open, container, reset]);

  const handleFormSubmit = (data: ContainerFormData) => {
    onSubmit(data);
  };

  return (
    <Dialog open={open} onClose={onClose} maxWidth="sm" fullWidth>
      <form onSubmit={handleSubmit(handleFormSubmit)}>
        <DialogTitle>{isEditing ? 'Edit Container' : 'Add New Container'}</DialogTitle>
        <DialogContent>
          <Grid container spacing={2} sx={{ mt: 0.5 }}>
            <Grid size={12}>
              <TextField
                {...register('name')}
                label="Container Name"
                placeholder="e.g., Warehouse-A, Godown-1, Rack-3"
                error={!!errors.name}
                helperText={errors.name?.message}
                disabled={isLoading}
                autoFocus
              />
            </Grid>
            <Grid size={12}>
              <Controller
                name="type"
                control={control}
                render={({ field }) => (
                  <FormControl fullWidth error={!!errors.type}>
                    <InputLabel>Container Type</InputLabel>
                    <Select {...field} label="Container Type" disabled={isLoading}>
                      {containerTypeOptions.map((option) => (
                        <MenuItem key={option.value} value={option.value}>
                          {option.label}
                        </MenuItem>
                      ))}
                    </Select>
                    {errors.type && (
                      <FormHelperText>{errors.type.message}</FormHelperText>
                    )}
                  </FormControl>
                )}
              />
            </Grid>
          </Grid>
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2 }}>
          <Button onClick={onClose} disabled={isLoading}>
            Cancel
          </Button>
          <Button type="submit" variant="contained" disabled={isLoading}>
            {isLoading ? 'Saving...' : isEditing ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </form>
    </Dialog>
  );
};

export default ContainerFormDialog;
