"""
Phase 3 - Data Generation
Creates realistic (and deliberately imperfect) CSV files in data/raw/.
Parent entities are generated before children so foreign keys stay valid.
"""

import os
import random
import pandas as pd
from datetime import datetime, timedelta
from faker import Faker

fake = Faker('en_IN')
Faker.seed(42)          # seeds make the run reproducible —
random.seed(42)         # anyone cloning the repo gets identical data

RAW = os.path.join('data', 'raw')
os.makedirs(RAW, exist_ok=True)

START_DATE = datetime(2023, 1, 1)
END_DATE   = datetime(2024, 12, 31)


def save(df, name):
    path = os.path.join(RAW, name)
    df.to_csv(path, index=False)
    print(f"  {name:<22} {len(df):>6} rows")


# ---------- 1. Regions ----------
regions = pd.DataFrame({
    'RegionID': range(1, 7),
    'RegionName': ['North', 'South', 'East', 'West', 'Central', 'North-East']
})
save(regions, 'regions.csv')

# ---------- 2. Categories ----------
cat_names = ['Electronics', 'Clothing', 'Grocery', 'Home & Kitchen', 'Beauty',
             'Sports', 'Books', 'Toys', 'Footwear', 'Stationery']
categories = pd.DataFrame({
    'CategoryID': range(1, len(cat_names) + 1),
    'CategoryName': cat_names,
    'Description': [f"{c} products" for c in cat_names]
})
save(categories, 'categories.csv')

# ---------- 3. Suppliers ----------
suppliers = pd.DataFrame([{
    'SupplierID': i,
    'SupplierName': fake.company(),
    'ContactName': fake.name(),
    'Email': fake.company_email(),
    'Phone': fake.msisdn()[:10],
    'City': fake.city()
} for i in range(1, 31)])
save(suppliers, 'suppliers.csv')

# ---------- 4. Stores ----------
stores = pd.DataFrame([{
    'StoreID': i,
    'StoreName': f"RetailMart {fake.city()}",
    'City': fake.city(),
    'State': fake.state(),
    'RegionID': random.randint(1, 6),
    'OpenedDate': fake.date_between(datetime(2015, 1, 1), datetime(2022, 12, 31))
} for i in range(1, 26)])
save(stores, 'stores.csv')

# ---------- 5. Products ----------
products = []
for i in range(1, 501):
    cost = round(random.uniform(50, 5000), 2)
    products.append({
        'ProductID': i,
        'ProductName': f"{fake.word().capitalize()} {random.choice(cat_names)} Item {i}",
        'CategoryID': random.randint(1, len(cat_names)),
        'SupplierID': random.randint(1, 30),
        'CostPrice': cost,
        'SellingPrice': round(cost * random.uniform(1.15, 1.60), 2),  # 15-60% markup
        'IsActive': random.choices([1, 0], weights=[92, 8])[0]
    })
products = pd.DataFrame(products)
save(products, 'products.csv')

# ---------- 6. Customers (with deliberate defects) ----------
customers = []
for i in range(1, 5001):
    first, last = fake.first_name(), fake.last_name()
    customers.append({
        'CustomerID': i,
        'FirstName': first,
        'LastName': last,
        # ~4% get stray whitespace / mixed case — ETL will normalise
        'Email': f"{first.lower()}.{last.lower()}{i}@example.com".upper()
                 if random.random() < 0.04
                 else f"  {first.lower()}.{last.lower()}{i}@example.com ",
        'Phone': fake.msisdn()[:10] if random.random() > 0.12 else None,   # 12% missing
        'City': fake.city() if random.random() > 0.05 else None,           # 5% missing
        'State': fake.state(),
        'RegistrationDate': fake.date_between(datetime(2020, 1, 1), END_DATE)
    })
customers = pd.DataFrame(customers)

# inject ~50 exact duplicate rows for the ETL to remove
dupes = customers.sample(50, random_state=1)
customers = pd.concat([customers, dupes], ignore_index=True)
save(customers, 'customers.csv')

# ---------- 7. Employees (self-referencing hierarchy) ----------
employees = []
for i in range(1, 51):
    store = ((i - 1) % 25) + 1
    is_manager = i <= 25                       # first 25 are store managers
    employees.append({
        'EmployeeID': i,
        'FirstName': fake.first_name(),
        'LastName': fake.last_name(),
        'Email': f"emp{i}@retailmart.com",
        'JobTitle': 'Store Manager' if is_manager else
                    random.choice(['Sales Associate', 'Cashier', 'Stock Clerk']),
        'HireDate': fake.date_between(datetime(2018, 1, 1), datetime(2024, 6, 30)),
        'StoreID': store,
        'ManagerID': '' if is_manager else store   # staff report to their store's manager
    })
save(pd.DataFrame(employees), 'employees.csv')

# ---------- 8. Orders ----------
# Weight products so a minority drive most sales (Pareto-ish, realistic)
product_weights = [random.paretovariate(1.3) for _ in range(500)]
days_span = (END_DATE - START_DATE).days

orders, details, payments = [], [], []
detail_id = 0

for order_id in range(1, 20001):
    order_dt = START_DATE + timedelta(days=random.randint(0, days_span),
                                      hours=random.randint(9, 21))
    # seasonal lift: Nov-Dec get more orders by re-rolling summer dates
    if order_dt.month in (6, 7) and random.random() < 0.3:
        order_dt = order_dt.replace(month=random.choice([11, 12]),
                                    day=min(order_dt.day, 30))

    status = random.choices(['Completed', 'Pending', 'Cancelled'],
                            weights=[90, 6, 4])[0]

    orders.append({
        'OrderID': order_id,
        'CustomerID': random.randint(1, 5000),
        'StoreID': random.randint(1, 25),
        'EmployeeID': random.randint(1, 50) if random.random() > 0.2 else '',
        # mixed date formats on purpose — ETL must standardise these
        'OrderDate': order_dt.strftime('%d-%m-%Y %H:%M')
                     if random.random() < 0.15
                     else order_dt.strftime('%Y-%m-%d %H:%M:%S'),
        'OrderStatus': status
    })

    # ---- order lines (unique products per order, 1-4 lines) ----
    n_items = random.choices([1, 2, 3, 4], weights=[40, 30, 20, 10])[0]
    chosen = random.choices(range(1, 501), weights=product_weights, k=n_items)
    order_total = 0
    for pid in set(chosen):
        detail_id += 1
        qty = random.choices([1, 2, 3, 5], weights=[55, 25, 15, 5])[0]
        base = products.loc[pid - 1, 'SellingPrice']
        price = round(base * random.uniform(0.9, 1.0), 2)   # occasional discount
        order_total += qty * price
        details.append({
            'OrderDetailID': detail_id,
            'OrderID': order_id,
            'ProductID': pid,
            'Quantity': qty,
            'UnitPrice': price
        })

    if status == 'Completed':
        payments.append({
            'PaymentID': len(payments) + 1,
            'OrderID': order_id,
            'PaymentDate': order_dt.strftime('%Y-%m-%d %H:%M:%S'),
            'PaymentMethod': random.choices(
                ['UPI', 'Card', 'Cash', 'NetBanking', 'Wallet'],
                weights=[40, 30, 15, 10, 5])[0],
            'Amount': round(order_total, 2)
        })

save(pd.DataFrame(orders), 'orders.csv')
details = pd.DataFrame(details)
save(details, 'order_details.csv')
save(pd.DataFrame(payments), 'payments.csv')

# ---------- 9. Inventory (composite key: StoreID + ProductID) ----------
inventory = []
for s in range(1, 26):
    for p in random.sample(range(1, 501), 300):    # each store stocks 300 products
        inventory.append({
            'StoreID': s,
            'ProductID': p,
            'QuantityInStock': random.choices(
                [random.randint(0, 9), random.randint(10, 200)],
                weights=[15, 85])[0],              # 15% below reorder level
            'ReorderLevel': 10,
            'LastRestockDate': fake.date_between(datetime(2024, 6, 1), END_DATE)
        })
save(pd.DataFrame(inventory), 'inventory.csv')

# ---------- 10. Returns (~4% of order lines) ----------
returned = details.sample(frac=0.04, random_state=2)
returns = [{
    'ReturnID': n + 1,
    'OrderDetailID': int(row.OrderDetailID),
    'ReturnDate': fake.date_between(START_DATE, END_DATE),
    'QuantityReturned': random.randint(1, int(row.Quantity)),
    'Reason': random.choice(['Damaged', 'Wrong item', 'Not as described',
                             'Changed mind', 'Late delivery'])
} for n, row in enumerate(returned.itertuples())]
save(pd.DataFrame(returns), 'returns.csv')

print("\nDone. CSV files are in data/raw/")