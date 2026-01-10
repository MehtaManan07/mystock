import React, { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Card,
  CardContent,
  Grid,
  Typography,
  TextField,
  Button,
  Autocomplete,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  IconButton,
  Chip,
  Divider,
  MenuItem,
  Alert,
  CircularProgress,
} from '@mui/material';
import {
  Add as AddIcon,
  Delete as DeleteIcon,
  ArrowBack as BackIcon,
} from '@mui/icons-material';
import { PageHeader } from '../../components/common/PageHeader';
import { useContacts } from '../../hooks/useContacts';
import { useProducts } from '../../hooks/useProducts';
import { useContainers } from '../../hooks/useContainers';
import { useCreatePurchase } from '../../hooks/useTransactions';
import { CONTACT_TYPES, PAYMENT_METHODS, type PaymentMethod } from '../../constants';
import type { Contact, Product, Container, CreateTransactionDto, CreateTransactionItemDto } from '../../types';

interface LineItem {
  id: string;
  product: Product | null;
  container: Container | null;
  quantity: number;
  unit_price: number;
}

export const CreatePurchasePage: React.FC = () => {
  const navigate = useNavigate();

  // Form state
  const [transactionDate, setTransactionDate] = useState(new Date().toISOString().split('T')[0]);
  const [selectedContact, setSelectedContact] = useState<Contact | null>(null);
  const [items, setItems] = useState<LineItem[]>([]);
  const [taxAmount, setTaxAmount] = useState(0);
  const [discountAmount, setDiscountAmount] = useState(0);
  const [paidAmount, setPaidAmount] = useState(0);
  const [paymentMethod, setPaymentMethod] = useState<PaymentMethod>(PAYMENT_METHODS.CASH);
  const [paymentReference, setPaymentReference] = useState('');
  const [notes, setNotes] = useState('');
  const [error, setError] = useState<string | null>(null);

  // For adding new items
  const [selectedProduct, setSelectedProduct] = useState<Product | null>(null);
  const [selectedContainer, setSelectedContainer] = useState<Container | null>(null);
  const [newQuantity, setNewQuantity] = useState(1);
  const [newUnitPrice, setNewUnitPrice] = useState(0);

  // Data fetching
  const { data: contacts, isLoading: contactsLoading } = useContacts({ 
    types: [CONTACT_TYPES.SUPPLIER, CONTACT_TYPES.BOTH] 
  });
  const { data: products, isLoading: productsLoading } = useProducts();
  const { data: containers, isLoading: containersLoading } = useContainers();
  
  const createPurchaseMutation = useCreatePurchase();

  // Calculate totals
  const subtotal = useMemo(() => {
    return items.reduce((sum, item) => sum + item.quantity * item.unit_price, 0);
  }, [items]);

  const totalAmount = subtotal + taxAmount - discountAmount;

  // Set default price when product changes
  const handleProductChange = (product: Product | null) => {
    setSelectedProduct(product);
    if (product?.default_purchase_price) {
      setNewUnitPrice(product.default_purchase_price);
    } else {
      setNewUnitPrice(0);
    }
  };

  // Add item to list
  const handleAddItem = () => {
    if (!selectedProduct || !selectedContainer) {
      setError('Please select a product and destination container');
      return;
    }
    if (newQuantity <= 0) {
      setError('Quantity must be greater than 0');
      return;
    }
    if (newUnitPrice < 0) {
      setError('Price cannot be negative');
      return;
    }

    // Check if same product-container combo already exists
    const existingIndex = items.findIndex(
      i => i.product?.id === selectedProduct.id && i.container?.id === selectedContainer.id
    );

    if (existingIndex >= 0) {
      // Update existing item
      const updatedItems = [...items];
      const existingItem = updatedItems[existingIndex];
      updatedItems[existingIndex] = {
        ...existingItem,
        quantity: existingItem.quantity + newQuantity,
      };
      setItems(updatedItems);
    } else {
      // Add new item
      setItems([
        ...items,
        {
          id: `${Date.now()}`,
          product: selectedProduct,
          container: selectedContainer,
          quantity: newQuantity,
          unit_price: newUnitPrice,
        },
      ]);
    }

    // Reset form
    setSelectedProduct(null);
    setSelectedContainer(null);
    setNewQuantity(1);
    setNewUnitPrice(0);
    setError(null);
  };

  // Remove item
  const handleRemoveItem = (id: string) => {
    setItems(items.filter(i => i.id !== id));
  };

  // Submit form
  const handleSubmit = async () => {
    if (!selectedContact) {
      setError('Please select a supplier');
      return;
    }
    if (items.length === 0) {
      setError('Please add at least one item');
      return;
    }

    const transactionItems: CreateTransactionItemDto[] = items.map(item => ({
      product_id: item.product!.id,
      container_id: item.container!.id,
      quantity: item.quantity,
      unit_price: item.unit_price,
    }));

    const data: CreateTransactionDto = {
      transaction_date: transactionDate,
      contact_id: selectedContact.id,
      items: transactionItems,
      tax_amount: taxAmount,
      discount_amount: discountAmount,
      paid_amount: paidAmount,
      payment_method: paidAmount > 0 ? paymentMethod : undefined,
      payment_reference: paidAmount > 0 ? paymentReference || undefined : undefined,
      notes: notes || undefined,
    };

    try {
      const result = await createPurchaseMutation.mutateAsync(data);
      navigate(`/transactions/${result.id}`);
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to create purchase';
      setError(errorMessage);
    }
  };

  const formatCurrency = (value: number) => {
    return `₹${value.toLocaleString('en-IN', { minimumFractionDigits: 2 })}`;
  };

  return (
    <Box>
      <PageHeader
        title="New Purchase"
        subtitle="Create a new purchase transaction"
        breadcrumbs={[
          { label: 'Transactions', path: '/transactions' },
          { label: 'New Purchase' },
        ]}
      />

      <Box sx={{ mb: 2 }}>
        <Button
          startIcon={<BackIcon />}
          onClick={() => navigate('/transactions')}
        >
          Back to Transactions
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Left Column - Items */}
        <Grid size={{ xs: 12, md: 8 }}>
          {/* Add Item Card */}
          <Card sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Add Items
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Grid container spacing={2} alignItems="flex-start">
                <Grid size={{ xs: 12, sm: 4 }}>
                  <Autocomplete
                    value={selectedProduct}
                    onChange={(_, value) => handleProductChange(value)}
                    options={products || []}
                    getOptionLabel={(option) => `${option.name} (${option.size})`}
                    loading={productsLoading}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Product"
                        size="small"
                        InputProps={{
                          ...params.InputProps,
                          endAdornment: (
                            <>
                              {productsLoading && <CircularProgress size={20} />}
                              {params.InputProps.endAdornment}
                            </>
                          ),
                        }}
                      />
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 3 }}>
                  <Autocomplete
                    value={selectedContainer}
                    onChange={(_, value) => setSelectedContainer(value)}
                    options={containers || []}
                    getOptionLabel={(option) => option.name}
                    loading={containersLoading}
                    renderInput={(params) => (
                      <TextField
                        {...params}
                        label="Store In"
                        size="small"
                        helperText="Destination container"
                      />
                    )}
                  />
                </Grid>
                <Grid size={{ xs: 6, sm: 2 }}>
                  <TextField
                    label="Qty"
                    type="number"
                    size="small"
                    fullWidth
                    value={newQuantity}
                    onChange={(e) => setNewQuantity(parseInt(e.target.value) || 0)}
                    inputProps={{ min: 1 }}
                  />
                </Grid>
                <Grid size={{ xs: 6, sm: 2 }}>
                  <TextField
                    label="Price"
                    type="number"
                    size="small"
                    fullWidth
                    value={newUnitPrice}
                    onChange={(e) => setNewUnitPrice(parseFloat(e.target.value) || 0)}
                    inputProps={{ min: 0, step: 0.01 }}
                  />
                </Grid>
                <Grid size={{ xs: 12, sm: 1 }}>
                  <Button
                    variant="contained"
                    color="secondary"
                    onClick={handleAddItem}
                    disabled={!selectedProduct || !selectedContainer}
                    sx={{ minWidth: 0, px: 2 }}
                  >
                    <AddIcon />
                  </Button>
                </Grid>
              </Grid>
            </CardContent>
          </Card>

          {/* Items List Card */}
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Items ({items.length})
              </Typography>
              <Divider sx={{ mb: 2 }} />

              {items.length > 0 ? (
                <TableContainer>
                  <Table size="small">
                    <TableHead>
                      <TableRow>
                        <TableCell>Product</TableCell>
                        <TableCell>Store In</TableCell>
                        <TableCell align="right">Qty</TableCell>
                        <TableCell align="right">Price</TableCell>
                        <TableCell align="right">Total</TableCell>
                        <TableCell align="center">Actions</TableCell>
                      </TableRow>
                    </TableHead>
                    <TableBody>
                      {items.map((item) => (
                        <TableRow key={item.id}>
                          <TableCell>
                            <Typography variant="body2" fontWeight={500}>
                              {item.product?.name}
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                              {item.product?.size} • {item.product?.packing}
                            </Typography>
                          </TableCell>
                          <TableCell>
                            <Chip label={item.container?.name} size="small" variant="outlined" color="secondary" />
                          </TableCell>
                          <TableCell align="right">{item.quantity}</TableCell>
                          <TableCell align="right">{formatCurrency(item.unit_price)}</TableCell>
                          <TableCell align="right" sx={{ fontWeight: 500 }}>
                            {formatCurrency(item.quantity * item.unit_price)}
                          </TableCell>
                          <TableCell align="center">
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleRemoveItem(item.id)}
                            >
                              <DeleteIcon fontSize="small" />
                            </IconButton>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </TableContainer>
              ) : (
                <Typography variant="body2" color="text.secondary" sx={{ py: 4, textAlign: 'center' }}>
                  No items added yet. Use the form above to add products.
                </Typography>
              )}
            </CardContent>
          </Card>
        </Grid>

        {/* Right Column - Summary */}
        <Grid size={{ xs: 12, md: 4 }}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Purchase Details
              </Typography>
              <Divider sx={{ mb: 2 }} />

              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2.5 }}>
                <TextField
                  label="Date"
                  type="date"
                  size="small"
                  fullWidth
                  value={transactionDate}
                  onChange={(e) => setTransactionDate(e.target.value)}
                  InputLabelProps={{ shrink: true }}
                />

                <Autocomplete
                  value={selectedContact}
                  onChange={(_, value) => setSelectedContact(value)}
                  options={contacts || []}
                  getOptionLabel={(option) => `${option.name} (${option.phone})`}
                  loading={contactsLoading}
                  renderInput={(params) => (
                    <TextField
                      {...params}
                      label="Supplier"
                      size="small"
                      required
                    />
                  )}
                />

                <Divider />

                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="body2">Subtotal</Typography>
                  <Typography variant="body2">{formatCurrency(subtotal)}</Typography>
                </Box>

                <TextField
                  label="Tax Amount"
                  type="number"
                  size="small"
                  fullWidth
                  value={taxAmount}
                  onChange={(e) => setTaxAmount(parseFloat(e.target.value) || 0)}
                  inputProps={{ min: 0, step: 0.01 }}
                />

                <TextField
                  label="Discount Amount"
                  type="number"
                  size="small"
                  fullWidth
                  value={discountAmount}
                  onChange={(e) => setDiscountAmount(parseFloat(e.target.value) || 0)}
                  inputProps={{ min: 0, step: 0.01 }}
                />

                <Divider />

                <Box sx={{ display: 'flex', justifyContent: 'space-between' }}>
                  <Typography variant="h6">Total</Typography>
                  <Typography variant="h6" color="secondary">
                    {formatCurrency(totalAmount)}
                  </Typography>
                </Box>

                <Divider />

                <TextField
                  label="Amount Paid Now"
                  type="number"
                  size="small"
                  fullWidth
                  value={paidAmount}
                  onChange={(e) => setPaidAmount(parseFloat(e.target.value) || 0)}
                  inputProps={{ min: 0, max: totalAmount, step: 0.01 }}
                />

                {paidAmount > 0 && (
                  <>
                    <TextField
                      label="Payment Method"
                      select
                      size="small"
                      fullWidth
                      value={paymentMethod}
                      onChange={(e) => setPaymentMethod(e.target.value as PaymentMethod)}
                    >
                      {Object.values(PAYMENT_METHODS).map((method) => (
                        <MenuItem key={method} value={method}>
                          {method.replace('_', ' ').toUpperCase()}
                        </MenuItem>
                      ))}
                    </TextField>

                    <TextField
                      label="Payment Reference"
                      size="small"
                      fullWidth
                      value={paymentReference}
                      onChange={(e) => setPaymentReference(e.target.value)}
                      placeholder="Check #, UPI ID, etc."
                    />
                  </>
                )}

                <TextField
                  label="Notes"
                  size="small"
                  fullWidth
                  multiline
                  rows={2}
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                />

                <Box sx={{ display: 'flex', justifyContent: 'space-between', mt: 1 }}>
                  <Typography variant="body2" color="text.secondary">Balance Due</Typography>
                  <Typography
                    variant="body1"
                    fontWeight={600}
                    color={totalAmount - paidAmount > 0 ? 'error.main' : 'success.main'}
                  >
                    {formatCurrency(totalAmount - paidAmount)}
                  </Typography>
                </Box>

                <Button
                  variant="contained"
                  color="secondary"
                  size="large"
                  fullWidth
                  onClick={handleSubmit}
                  disabled={createPurchaseMutation.isPending || items.length === 0 || !selectedContact}
                >
                  {createPurchaseMutation.isPending ? 'Creating...' : 'Create Purchase'}
                </Button>
              </Box>
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default CreatePurchasePage;
