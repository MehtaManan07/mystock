import React from 'react';
import {
  Box,
  Typography,
  Grid,
  Card,
  CardContent,
  useTheme,
} from '@mui/material';
import {
  Inventory2 as ProductIcon,
  Warehouse as ContainerIcon,
  People as ContactIcon,
  Receipt as TransactionIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../stores/authStore';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: React.ReactNode;
  color: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, icon, color }) => {
  const theme = useTheme();
  
  return (
    <Card
      sx={{
        height: '100%',
        position: 'relative',
        overflow: 'visible',
      }}
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
            background: `linear-gradient(135deg, ${color} 0%, ${theme.palette.mode === 'dark' ? color + 'cc' : color + '99'} 100%)`,
            boxShadow: `0 4px 20px ${color}40`,
          }}
        >
          <Box sx={{ color: 'white', fontSize: 28, display: 'flex' }}>
            {icon}
          </Box>
        </Box>
        <Box sx={{ textAlign: 'right', mt: 2 }}>
          <Typography variant="body2" color="text.secondary" gutterBottom>
            {title}
          </Typography>
          <Typography variant="h4" fontWeight={700}>
            {value}
          </Typography>
        </Box>
      </CardContent>
    </Card>
  );
};

export const DashboardPage: React.FC = () => {
  const theme = useTheme();
  const user = useAuthStore((state) => state.user);

  // Placeholder data - will be replaced with real data from API
  const stats = [
    {
      title: 'Total Products',
      value: '--',
      icon: <ProductIcon />,
      color: theme.palette.primary.main,
    },
    {
      title: 'Containers',
      value: '--',
      icon: <ContainerIcon />,
      color: theme.palette.secondary.main,
    },
    {
      title: 'Contacts',
      value: '--',
      icon: <ContactIcon />,
      color: theme.palette.info.main,
    },
    {
      title: 'Transactions',
      value: '--',
      icon: <TransactionIcon />,
      color: theme.palette.success.main,
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

      {/* Placeholder for more content */}
      <Box sx={{ mt: 4 }}>
        <Card>
          <CardContent sx={{ p: 4, textAlign: 'center' }}>
            <Typography variant="h6" color="text.secondary" gutterBottom>
              Dashboard Coming Soon
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Charts, recent transactions, and analytics will be displayed here.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    </Box>
  );
};

export default DashboardPage;
