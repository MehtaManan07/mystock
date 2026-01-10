import React, { useState } from 'react';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';
import {
  Box,
  Drawer,
  AppBar,
  Toolbar,
  List,
  Typography,
  Divider,
  IconButton,
  ListItem,
  ListItemButton,
  ListItemIcon,
  ListItemText,
  Avatar,
  Menu,
  MenuItem,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  Menu as MenuIcon,
  Dashboard as DashboardIcon,
  Inventory2 as ProductIcon,
  Warehouse as ContainerIcon,
  People as ContactIcon,
  Receipt as TransactionIcon,
  Payments as PaymentIcon,
  DarkMode as DarkModeIcon,
  LightMode as LightModeIcon,
  Logout as LogoutIcon,
  Person as PersonIcon,
  Inventory as InventoryIcon,
} from '@mui/icons-material';
import { useAuthStore } from '../../stores/authStore';
import { useThemeStore } from '../../stores/themeStore';
import { useLogout } from '../../hooks/useAuth';

const DRAWER_WIDTH = 260;

interface NavItem {
  text: string;
  icon: React.ReactNode;
  path: string;
}

const navItems: NavItem[] = [
  { text: 'Dashboard', icon: <DashboardIcon />, path: '/dashboard' },
  { text: 'Products', icon: <ProductIcon />, path: '/products' },
  { text: 'Containers', icon: <ContainerIcon />, path: '/containers' },
  { text: 'Inventory', icon: <InventoryIcon />, path: '/inventory' },
  { text: 'Contacts', icon: <ContactIcon />, path: '/contacts' },
  { text: 'Transactions', icon: <TransactionIcon />, path: '/transactions' },
  { text: 'Payments', icon: <PaymentIcon />, path: '/payments' },
];

export const MainLayout: React.FC = () => {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  const navigate = useNavigate();
  const location = useLocation();
  
  const [mobileOpen, setMobileOpen] = useState(false);
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  
  const user = useAuthStore((state) => state.user);
  const { mode, toggleTheme } = useThemeStore();
  const logout = useLogout();

  const handleDrawerToggle = () => {
    setMobileOpen(!mobileOpen);
  };

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
    navigate('/login');
  };

  const handleNavClick = (path: string) => {
    navigate(path);
    if (isMobile) {
      setMobileOpen(false);
    }
  };

  const drawer = (
    <Box sx={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
      {/* Logo */}
      <Box sx={{ p: 3, display: 'flex', alignItems: 'center', gap: 2 }}>
        <Box
          sx={{
            width: 40,
            height: 40,
            borderRadius: 2,
            background: `linear-gradient(135deg, ${theme.palette.primary.main} 0%, ${theme.palette.secondary.main} 100%)`,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
          }}
        >
          <ProductIcon sx={{ color: 'white', fontSize: 24 }} />
        </Box>
        <Typography variant="h6" fontWeight={700} color="primary">
          MyStock
        </Typography>
      </Box>
      
      <Divider />
      
      {/* Navigation */}
      <List sx={{ flex: 1, px: 2, py: 2 }}>
        {navItems.map((item) => {
          const isActive = location.pathname.startsWith(item.path);
          return (
            <ListItem key={item.text} disablePadding sx={{ mb: 0.5 }}>
              <ListItemButton
                onClick={() => handleNavClick(item.path)}
                sx={{
                  borderRadius: 2,
                  backgroundColor: isActive
                    ? theme.palette.primary.main + '15'
                    : 'transparent',
                  color: isActive
                    ? theme.palette.primary.main
                    : theme.palette.text.secondary,
                  '&:hover': {
                    backgroundColor: isActive
                      ? theme.palette.primary.main + '20'
                      : theme.palette.action.hover,
                  },
                }}
              >
                <ListItemIcon
                  sx={{
                    color: 'inherit',
                    minWidth: 40,
                  }}
                >
                  {item.icon}
                </ListItemIcon>
                <ListItemText
                  primary={item.text}
                  primaryTypographyProps={{
                    fontWeight: isActive ? 600 : 500,
                  }}
                />
              </ListItemButton>
            </ListItem>
          );
        })}
      </List>
      
      <Divider />
      
      {/* User info at bottom */}
      <Box sx={{ p: 2 }}>
        <Box
          sx={{
            p: 2,
            borderRadius: 2,
            backgroundColor: theme.palette.action.hover,
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
          }}
        >
          <Avatar
            sx={{
              width: 36,
              height: 36,
              bgcolor: theme.palette.primary.main,
              fontSize: 14,
            }}
          >
            {user?.name?.charAt(0).toUpperCase() || 'U'}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Typography variant="body2" fontWeight={600} noWrap>
              {user?.name || 'User'}
            </Typography>
            <Typography variant="caption" color="text.secondary" noWrap>
              {user?.role || 'Role'}
            </Typography>
          </Box>
        </Box>
      </Box>
    </Box>
  );

  return (
    <Box sx={{ display: 'flex', minHeight: '100vh' }}>
      {/* AppBar */}
      <AppBar
        position="fixed"
        elevation={0}
        sx={{
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          ml: { md: `${DRAWER_WIDTH}px` },
          backgroundColor: theme.palette.background.paper,
          borderBottom: `1px solid ${theme.palette.divider}`,
        }}
      >
        <Toolbar>
          <IconButton
            color="inherit"
            edge="start"
            onClick={handleDrawerToggle}
            sx={{ mr: 2, display: { md: 'none' }, color: 'text.primary' }}
          >
            <MenuIcon />
          </IconButton>
          
          <Box sx={{ flexGrow: 1 }} />
          
          {/* Theme toggle */}
          <IconButton onClick={toggleTheme} sx={{ mr: 1 }}>
            {mode === 'dark' ? (
              <LightModeIcon sx={{ color: 'text.primary' }} />
            ) : (
              <DarkModeIcon sx={{ color: 'text.primary' }} />
            )}
          </IconButton>
          
          {/* User menu */}
          <IconButton onClick={handleMenuOpen}>
            <Avatar
              sx={{
                width: 36,
                height: 36,
                bgcolor: theme.palette.primary.main,
              }}
            >
              {user?.name?.charAt(0).toUpperCase() || 'U'}
            </Avatar>
          </IconButton>
          
          <Menu
            anchorEl={anchorEl}
            open={Boolean(anchorEl)}
            onClose={handleMenuClose}
            transformOrigin={{ horizontal: 'right', vertical: 'top' }}
            anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
          >
            <MenuItem onClick={handleMenuClose}>
              <ListItemIcon>
                <PersonIcon fontSize="small" />
              </ListItemIcon>
              Profile
            </MenuItem>
            <Divider />
            <MenuItem onClick={handleLogout}>
              <ListItemIcon>
                <LogoutIcon fontSize="small" />
              </ListItemIcon>
              Logout
            </MenuItem>
          </Menu>
        </Toolbar>
      </AppBar>
      
      {/* Sidebar */}
      <Box
        component="nav"
        sx={{ width: { md: DRAWER_WIDTH }, flexShrink: { md: 0 } }}
      >
        {/* Mobile drawer */}
        <Drawer
          variant="temporary"
          open={mobileOpen}
          onClose={handleDrawerToggle}
          ModalProps={{ keepMounted: true }}
          sx={{
            display: { xs: 'block', md: 'none' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
            },
          }}
        >
          {drawer}
        </Drawer>
        
        {/* Desktop drawer */}
        <Drawer
          variant="permanent"
          sx={{
            display: { xs: 'none', md: 'block' },
            '& .MuiDrawer-paper': {
              boxSizing: 'border-box',
              width: DRAWER_WIDTH,
              borderRight: `1px solid ${theme.palette.divider}`,
            },
          }}
          open
        >
          {drawer}
        </Drawer>
      </Box>
      
      {/* Main content */}
      <Box
        component="main"
        sx={{
          flexGrow: 1,
          p: 3,
          width: { md: `calc(100% - ${DRAWER_WIDTH}px)` },
          mt: '64px',
          backgroundColor: theme.palette.background.default,
          minHeight: 'calc(100vh - 64px)',
        }}
      >
        <Outlet />
      </Box>
    </Box>
  );
};

export default MainLayout;
