"""
Phase 4 - ETL Pipeline
Extract  : read raw CSVs from data/raw/
Transform: clean, validate, apply business rules
Load     : insert into SQL Server (parents before children)

Idempotent: clears target tables first, so it can be re-run safely.
"""

import os
import pandas as pd
from urllib.parse import quote_plus
from sqlalchemy import create_engine, text

RAW     = os.path.join('data', 'raw')
CLEANED = os.path.join('data', 'cleaned')
os.makedirs(CLEANED, exist_ok=True)

# ---------------------------------------------------------------
# CONNECTION
# Change SERVER below if your instance name differs.
# ---------------------------------------------------------------
params = quote_plus(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    "SERVER=localhost\\SQLEXPRESS01;"
    "DATABASE=RetailSalesDB;"
    "Trusted_Connection=yes;"
    "TrustServerCertificate=yes;"
)
engine = create_engine(f"mssql+pyodbc:///?odbc_connect={params}",
                       fast_executemany=True)   # batches inserts = much faster


# ---------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------
def extract(name):
    df = pd.read_csv(os.path.join(RAW, name))
    print(f"  extracted {name:<20} {len(df):>6} rows")
    return df


def parse_mixed_dates(series):
    """Our source has two date formats. Parse both, keep whichever worked."""
    iso  = pd.to_datetime(series, format='%Y-%m-%d %H:%M:%S', errors='coerce')
    euro = pd.to_datetime(series, format='%d-%m-%Y %H:%M',    errors='coerce')
    return iso.fillna(euro)


def load(df, table, conn):
    """Load a DataFrame, supplying our own IDENTITY values."""
    conn.execute(text(f"SET IDENTITY_INSERT {table} ON"))
    df.to_sql(table, conn, if_exists='append', index=False)
    conn.execute(text(f"SET IDENTITY_INSERT {table} OFF"))
    print(f"  loaded    {table:<20} {len(df):>6} rows")


def load_plain(df, table, conn):
    """For tables with no IDENTITY column (Inventory)."""
    df.to_sql(table, conn, if_exists='append', index=False)
    print(f"  loaded    {table:<20} {len(df):>6} rows")


# ===============================================================
# EXTRACT
# ===============================================================
print("\n--- EXTRACT ---")
regions    = extract('regions.csv')
categories = extract('categories.csv')
suppliers  = extract('suppliers.csv')
stores     = extract('stores.csv')
products   = extract('products.csv')
customers  = extract('customers.csv')
employees  = extract('employees.csv')
orders     = extract('orders.csv')
details    = extract('order_details.csv')
payments   = extract('payments.csv')
inventory  = extract('inventory.csv')
returns    = extract('returns.csv')

# ===============================================================
# TRANSFORM
# ===============================================================
print("\n--- TRANSFORM ---")

# --- Customers: whitespace, casing, duplicates ---
before = len(customers)
customers['Email'] = customers['Email'].str.strip().str.lower()
customers = customers.drop_duplicates(subset='CustomerID', keep='first')
customers = customers.drop_duplicates(subset='Email', keep='first')
print(f"  customers: removed {before - len(customers)} duplicate rows")

missing_phone = customers['Phone'].isna().sum()
print(f"  customers: {missing_phone} missing phones left as NULL (not imputed)")

# Phone read as float because of NaNs -> convert to clean string
customers['Phone'] = customers['Phone'].apply(
    lambda x: str(int(x)) if pd.notna(x) else None)
customers['RegistrationDate'] = pd.to_datetime(customers['RegistrationDate']).dt.date

# --- Products: business rule - selling price must cover cost ---
bad = products[products['SellingPrice'] < products['CostPrice']]
products = products[products['SellingPrice'] >= products['CostPrice']]
print(f"  products: dropped {len(bad)} rows failing price rule")

# --- Employees: empty ManagerID -> NULL ---
employees['ManagerID'] = employees['ManagerID'].astype('Int64')
employees['HireDate']  = pd.to_datetime(employees['HireDate']).dt.date

stores['OpenedDate'] = pd.to_datetime(stores['OpenedDate']).dt.date

# --- Orders: mixed date formats + empty EmployeeID ---
orders['OrderDate']  = parse_mixed_dates(orders['OrderDate'])
unparsed = orders['OrderDate'].isna().sum()
orders = orders.dropna(subset=['OrderDate'])
print(f"  orders: standardised dates, dropped {unparsed} unparseable")
orders['EmployeeID'] = orders['EmployeeID'].astype('Int64')

# --- Order details: quantity/price rules ---
before = len(details)
details = details[(details['Quantity'] > 0) & (details['UnitPrice'] >= 0)]
print(f"  order_details: dropped {before - len(details)} invalid lines")

# --- Referential integrity checks (do this BEFORE loading) ---
details = details[details['OrderID'].isin(orders['OrderID'])]
details = details[details['ProductID'].isin(products['ProductID'])]
orders  = orders[orders['CustomerID'].isin(customers['CustomerID'])]
details = details[details['OrderID'].isin(orders['OrderID'])]   # re-check after
payments = payments[payments['OrderID'].isin(orders['OrderID'])]
returns  = returns[returns['OrderDetailID'].isin(details['OrderDetailID'])]
inventory = inventory[inventory['ProductID'].isin(products['ProductID'])]
print("  referential integrity: orphan rows removed")

payments['PaymentDate']   = pd.to_datetime(payments['PaymentDate'])
returns['ReturnDate']     = pd.to_datetime(returns['ReturnDate']).dt.date
inventory['LastRestockDate'] = pd.to_datetime(inventory['LastRestockDate']).dt.date

# --- Save cleaned copies (audit trail) ---
frames = {
    'regions': regions, 'categories': categories, 'suppliers': suppliers,
    'stores': stores, 'products': products, 'customers': customers,
    'employees': employees, 'orders': orders, 'order_details': details,
    'payments': payments, 'inventory': inventory, 'returns': returns
}
for name, df in frames.items():
    df.to_csv(os.path.join(CLEANED, f"{name}.csv"), index=False)
print("  cleaned CSVs written to data/cleaned/")

# ===============================================================
# LOAD
# ===============================================================
print("\n--- LOAD ---")
with engine.begin() as conn:          # one transaction, one session
    # clear child tables first (reverse FK order) so re-runs are safe
    for t in ['Returns', 'Inventory', 'Payments', 'OrderDetails', 'Orders',
              'Employees', 'Customers', 'Products', 'Stores',
              'Suppliers', 'Categories', 'Regions']:
        conn.execute(text(f"DELETE FROM {t}"))
    print("  existing rows cleared")

    load(regions,    'Regions',      conn)
    load(categories, 'Categories',   conn)
    load(suppliers,  'Suppliers',    conn)
    load(stores,     'Stores',       conn)
    load(products,   'Products',     conn)
    load(customers,  'Customers',    conn)
    load(employees,  'Employees',    conn)
    load(orders,     'Orders',       conn)
    load(details,    'OrderDetails', conn)
    load(payments,   'Payments',     conn)
    load_plain(inventory, 'Inventory', conn)
    load(returns,    'Returns',      conn)

print("\nETL complete.")