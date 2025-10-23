Sales & Purchases:
  POST   /api/transactions/sales              Create sale
  POST   /api/transactions/purchases          Create purchase
  GET    /api/transactions                    List all (filters: type, status, contact_id, from_date, to_date)
  GET    /api/transactions/{id}               Get details
  DELETE /api/transactions/{id}               Soft delete

Payments:
  POST   /api/transactions/{id}/payments      Record payment
  GET    /api/transactions/{id}/payments      List payments
  
Reports:
  GET    /api/transactions/summary            Financial summary
  GET    /api/transactions/outstanding        Outstanding receivables/payables

Products (Enhanced):
  PUT    /api/products/{id}/pricing           Update default prices




  # 🎯 FINAL SYSTEM DESIGN: Sales & Purchase Entry Module

Based on your feedback, here's the finalized plan:

---

## 📊 DATABASE SCHEMA (Final)

### **1. Update Products Table**
Add default pricing to existing products:
```python
# Add to Product model:
default_sale_price: Decimal = Numeric(15, 2), nullable=True, default=0.0
default_purchase_price: Decimal = Numeric(15, 2), nullable=True, default=0.0
```

### **2. Transactions Table**
```python
class TransactionType(enum):
    sale = "sale"
    purchase = "purchase"

class PaymentStatus(enum):
    paid = "paid"
    partial = "partial"
    unpaid = "unpaid"

class Transaction(BaseModel):
    transaction_number: str           # Unique: "SALE-0001", "PUR-0001"
    transaction_date: date
    type: TransactionType
    
    contact_id: int (FK)
    
    # Financial fields
    subtotal: Decimal(15,2)          # Sum of line items
    tax_amount: Decimal(15,2)        # Simple tax field
    discount_amount: Decimal(15,2)
    total_amount: Decimal(15,2)      # subtotal + tax - discount
    
    paid_amount: Decimal(15,2)       # Amount paid so far
    payment_status: PaymentStatus
    
    notes: str (optional)
```

### **3. Transaction Items Table**
```python
class TransactionItem(BaseModel):
    transaction_id: int (FK)
    product_id: int (FK)
    container_id: int (FK, optional)  # Required for sales, optional for purchases
    
    quantity: int
    unit_price: Decimal(15,2)        # Can override product default price
    line_total: Decimal(15,2)        # quantity * unit_price
```

### **4. Payments Table**
```python
class PaymentMethod(enum):
    cash = "cash"
    bank_transfer = "bank_transfer"
    upi = "upi"
    cheque = "cheque"
    other = "other"

class Payment(BaseModel):
    transaction_id: int (FK)
    payment_date: date
    amount: Decimal(15,2)
    payment_method: PaymentMethod
    reference_number: str (optional)
    notes: str (optional)
```

---

## 🔄 BUSINESS LOGIC (Final)

### **SALES FLOW**
1. Create Transaction (type=sale)
2. For each item:
   - Use product.default_sale_price OR custom price
   - Validate container has enough quantity
   - Reduce inventory from container
   - Create InventoryLog (action="sale")
3. Calculate: subtotal → add tax → subtract discount → total
4. If paid_amount > 0: create Payment record
5. Update contact.balance (if unpaid/partial)
6. Auto-generate transaction_number

### **PURCHASE FLOW**
1. Create Transaction (type=purchase)
2. For each item:
   - Use product.default_purchase_price OR custom price
   - Add inventory to specified container
   - Create InventoryLog (action="purchase")
3. Calculate totals
4. If paid_amount > 0: create Payment record
5. Update contact.balance (if unpaid/partial)
6. Auto-generate transaction_number

### **PAYMENT RECORDING**
1. Create Payment record
2. Update transaction.paid_amount
3. Update payment_status (unpaid/partial/paid)
4. Adjust contact.balance

---

## 📁 IMPLEMENTATION PLAN (Step by Step)

### **PHASE 1: Database Setup**
- ✅ **Step 1.1:** Add pricing fields to Product model
- ✅ **Step 1.2:** Create Transaction model
- ✅ **Step 1.3:** Create TransactionItem model
- ✅ **Step 1.4:** Create Payment model
- ✅ **Step 1.5:** Generate and run Alembic migration

### **PHASE 2: Schemas**
- ✅ **Step 2.1:** Create request schemas (TransactionCreate, TransactionItemCreate, PaymentCreate)
- ✅ **Step 2.2:** Create response schemas (TransactionResponse, TransactionItemResponse, PaymentResponse)
- ✅ **Step 2.3:** Create update schemas

### **PHASE 3: Service Layer - Sales**
- ✅ **Step 3.1:** Implement `create_sale()`
  - Validate contact is customer/both
  - Validate products exist
  - Validate container stock availability
  - Create transaction + items
  - Update inventory
  - Create inventory logs
  - Update contact balance
  - Create payment if paid_amount > 0
  
- ✅ **Step 3.2:** Implement `record_sale_payment()`
  - Create payment record
  - Update transaction amounts
  - Update contact balance

### **PHASE 4: Service Layer - Purchases**
- ✅ **Step 4.1:** Implement `create_purchase()`
  - Validate contact is supplier/both
  - Validate products exist
  - Create transaction + items
  - Update inventory
  - Create inventory logs
  - Update contact balance
  - Create payment if paid_amount > 0
  
- ✅ **Step 4.2:** Implement `record_purchase_payment()`
  - Create payment record
  - Update transaction amounts
  - Update contact balance

### **PHASE 5: Service Layer - Common**
- ✅ **Step 5.1:** Implement `get_transaction(id)` - Get single transaction with all details
- ✅ **Step 5.2:** Implement `list_transactions()` - List with filters (type, status, contact, date range)
- ✅ **Step 5.3:** Implement `get_transaction_summary()` - Financial summary
- ✅ **Step 5.4:** Implement `get_outstanding_transactions()` - Unpaid/partial transactions
- ✅ **Step 5.5:** Implement `delete_transaction()` - Soft delete with inventory reversal

### **PHASE 6: API Routes**
- ✅ **Step 6.1:** `POST /api/transactions/sales` - Create sale
- ✅ **Step 6.2:** `POST /api/transactions/purchases` - Create purchase
- ✅ **Step 6.3:** `GET /api/transactions` - List all transactions
- ✅ **Step 6.4:** `GET /api/transactions/{id}` - Get transaction details
- ✅ **Step 6.5:** `DELETE /api/transactions/{id}` - Delete transaction
- ✅ **Step 6.6:** `POST /api/transactions/{id}/payments` - Record payment
- ✅ **Step 6.7:** `GET /api/transactions/{id}/payments` - List payments
- ✅ **Step 6.8:** `GET /api/transactions/summary` - Financial summary
- ✅ **Step 6.9:** `GET /api/transactions/outstanding` - Outstanding dues

### **PHASE 7: Update Existing Modules**
- ✅ **Step 7.1:** Update Products router to handle default prices
- ✅ **Step 7.2:** Register transactions router in main.py
- ✅ **Step 7.3:** Update Contacts router to show balance in listings

### **PHASE 8: Testing**
- ✅ **Step 8.1:** Test creating a sale with single product
- ✅ **Step 8.2:** Test creating a sale with multiple products
- ✅ **Step 8.3:** Test insufficient stock validation
- ✅ **Step 8.4:** Test partial payment flow
- ✅ **Step 8.5:** Test creating a purchase
- ✅ **Step 8.6:** Test contact balance updates
- ✅ **Step 8.7:** Test transaction listing and filtering
- ✅ **Step 8.8:** Test payment recording

---

## 🎨 API ENDPOINTS (Final)

```
Sales & Purchases:
  POST   /api/transactions/sales              Create sale
  POST   /api/transactions/purchases          Create purchase
  GET    /api/transactions                    List all (filters: type, status, contact_id, from_date, to_date)
  GET    /api/transactions/{id}               Get details
  DELETE /api/transactions/{id}               Soft delete

Payments:
  POST   /api/transactions/{id}/payments      Record payment
  GET    /api/transactions/{id}/payments      List payments
  
Reports:
  GET    /api/transactions/summary            Financial summary
  GET    /api/transactions/outstanding        Outstanding receivables/payables

Products (Enhanced):
  PUT    /api/products/{id}/pricing           Update default prices
```

---

## 📋 REQUEST/RESPONSE EXAMPLES

### **Create Sale Request:**
```json
{
  "transaction_date": "2025-10-22",
  "contact_id": 5,
  "items": [
    {
      "product_id": 10,
      "container_id": 3,
      "quantity": 100,
      "unit_price": 25.50
    },
    {
      "product_id": 12,
      "container_id": 3,
      "quantity": 50,
      "unit_price": 30.00
    }
  ],
  "tax_amount": 450.00,
  "discount_amount": 50.00,
  "paid_amount": 2000.00,
  "payment_method": "upi",
  "notes": "Diwali discount applied"
}
```

### **Transaction Response:**
```json
{
  "id": 1,
  "transaction_number": "SALE-0001",
  "transaction_date": "2025-10-22",
  "type": "sale",
  "contact": {
    "id": 5,
    "name": "Rajesh Trading Co.",
    "phone": "9876543210",
    "type": "customer",
    "balance": 3900.00
  },
  "items": [
    {
      "id": 1,
      "product": { "id": 10, "name": "Rice", "size": "25kg" },
      "container": { "id": 3, "name": "Godown-A" },
      "quantity": 100,
      "unit_price": 25.50,
      "line_total": 2550.00
    },
    {
      "id": 2,
      "product": { "id": 12, "name": "Wheat", "size": "50kg" },
      "container": { "id": 3, "name": "Godown-A" },
      "quantity": 50,
      "unit_price": 30.00,
      "line_total": 1500.00
    }
  ],
  "subtotal": 4050.00,
  "tax_amount": 450.00,
  "discount_amount": 50.00,
  "total_amount": 4450.00,
  "paid_amount": 2000.00,
  "payment_status": "partial",
  "balance_due": 2450.00,
  "notes": "Diwali discount applied",
  "payments": [
    {
      "id": 1,
      "payment_date": "2025-10-22",
      "amount": 2000.00,
      "payment_method": "upi",
      "reference_number": null
    }
  ],
  "created_at": "2025-10-22T10:30:00"
}
```

---

## ✅ VALIDATION RULES (Final)

### **Sales:**
- ✅ Contact must be type "customer" or "both"
- ✅ All products must exist
- ✅ Each item must specify container_id
- ✅ Container must have sufficient quantity (current_qty >= sale_qty)
- ✅ quantity > 0, unit_price >= 0
- ✅ paid_amount <= total_amount

### **Purchases:**
- ✅ Contact must be type "supplier" or "both"
- ✅ All products must exist
- ✅ If container_id not specified, create error (must specify destination)
- ✅ quantity > 0, unit_price >= 0
- ✅ paid_amount <= total_amount

### **Payments:**
- ✅ amount > 0
- ✅ Sum of all payments <= total_amount
- ✅ payment_date >= transaction_date (warning only)

---

## 🗃️ DATABASE INDEXES (Performance)

```python
# transactions table
- transaction_number (unique)
- contact_id
- transaction_date
- (type, payment_status) composite
- created_at

# transaction_items table
- transaction_id
- product_id
- (transaction_id, product_id) composite

# payments table
- transaction_id
- payment_date
```

---

## 🔢 AUTO-NUMBERING LOGIC

```python
def generate_transaction_number(type: TransactionType) -> str:
    prefix = "SALE" if type == "sale" else "PUR"
    
    # Get last transaction of this type
    last = session.query(Transaction)\
        .filter(Transaction.type == type)\
        .order_by(Transaction.id.desc())\
        .first()
    
    if not last:
        return f"{prefix}-0001"
    
    # Extract number, increment
    last_num = int(last.transaction_number.split('-')[1])
    new_num = last_num + 1
    
    return f"{prefix}-{new_num:04d}"
```

---

## 📝 NOTES & CLARIFICATIONS

1. **Container Selection for Sales:** User MUST specify which container to sell from (no auto-selection)

2. **Container for Purchases:** User MUST specify destination container

3. **Price Override:** Every transaction item can have custom unit_price, but UI can pre-fill from product.default_sale_price or product.default_purchase_price

4. **Transaction Editing:** For Phase 1, transactions are immutable once created. Delete and recreate if needed. (Can add edit later)

5. **Inventory Logs:** Will automatically track "sale" and "purchase" actions. Existing manual logs remain separate.

6. **Contact Balance:**
   - Positive = Customer owes you (receivable)
   - Negative = You owe supplier (payable)
   - Zero = Settled

7. **Soft Delete:** Deleting a transaction will:
   - Soft delete transaction, items, payments
   - Reverse inventory changes
   - Reverse contact balance changes

---

## 🚀 EXECUTION PLAN

I'll implement one step at a time, waiting for your approval before moving to the next. We'll follow this order:

1. **Start with Models** → Migration → Test migration
2. **Then Schemas** → Review structure
3. **Then Service for Sales** → Test thoroughly
4. **Then Service for Purchases** → Test thoroughly
5. **Then API Routes** → Test end-to-end
6. **Finally Integration** → Update existing modules

Each step will be tested before moving forward.

---

## ❓ FINAL QUESTIONS

1. **Auto-fill prices in UI?** When creating sale/purchase, should API return product's default price so frontend can pre-fill? (My answer: Yes, add to product response)

2. **Payment on delete?** If a transaction with payments is deleted, should we just mark it soft-deleted or actually reverse payments? (My answer: Soft delete only, don't physically remove)

3. **Date validation?** Should transaction_date be restricted to not be in future? (My answer: No restriction, allow future-dated transactions)

---

## 🎯 READY TO START?

**If this plan looks good to you, just say "START" and I'll begin with Phase 1: Database Models & Migration!** 

I'll do one phase at a time, show you the code, and wait for your approval before moving to the next phase. 🚀