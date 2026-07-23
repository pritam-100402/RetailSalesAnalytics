USE RetailSalesDB;
GO

/* ---- Safety reset: drop child tables before parents ---- */
DROP TABLE IF EXISTS Returns;
DROP TABLE IF EXISTS Inventory;
DROP TABLE IF EXISTS Payments;
DROP TABLE IF EXISTS OrderDetails;
DROP TABLE IF EXISTS Orders;
DROP TABLE IF EXISTS Employees;
DROP TABLE IF EXISTS Customers;
DROP TABLE IF EXISTS Products;
DROP TABLE IF EXISTS Stores;
DROP TABLE IF EXISTS Suppliers;
DROP TABLE IF EXISTS Categories;
DROP TABLE IF EXISTS Regions;
GO

/* ---- 1. Regions ---- */
CREATE TABLE Regions (
    RegionID    INT IDENTITY(1,1) PRIMARY KEY,
    RegionName  VARCHAR(50) NOT NULL UNIQUE
);

/* ---- 2. Categories ---- */
CREATE TABLE Categories (
    CategoryID    INT IDENTITY(1,1) PRIMARY KEY,
    CategoryName  VARCHAR(50) NOT NULL UNIQUE,
    Description   VARCHAR(255) NULL
);

/* ---- 3. Suppliers ---- */
CREATE TABLE Suppliers (
    SupplierID    INT IDENTITY(1,1) PRIMARY KEY,
    SupplierName  VARCHAR(100) NOT NULL,
    ContactName   VARCHAR(100) NULL,
    Email         VARCHAR(100) NULL,
    Phone         VARCHAR(20)  NULL,
    City          VARCHAR(50)  NULL
);

/* ---- 4. Stores ---- */
CREATE TABLE Stores (
    StoreID     INT IDENTITY(1,1) PRIMARY KEY,
    StoreName   VARCHAR(100) NOT NULL,
    City        VARCHAR(50)  NOT NULL,
    State       VARCHAR(50)  NOT NULL,
    RegionID    INT          NOT NULL,
    OpenedDate  DATE         NULL,
    CONSTRAINT FK_Stores_Regions
        FOREIGN KEY (RegionID) REFERENCES Regions(RegionID)
);

/* ---- 5. Products: CostPrice + SellingPrice let us compute profit ---- */
CREATE TABLE Products (
    ProductID     INT IDENTITY(1,1) PRIMARY KEY,
    ProductName   VARCHAR(100)  NOT NULL,
    CategoryID    INT           NOT NULL,
    SupplierID    INT           NOT NULL,
    CostPrice     DECIMAL(10,2) NOT NULL,
    SellingPrice  DECIMAL(10,2) NOT NULL,
    IsActive      BIT           NOT NULL DEFAULT 1,
    CONSTRAINT FK_Products_Categories
        FOREIGN KEY (CategoryID) REFERENCES Categories(CategoryID),
    CONSTRAINT FK_Products_Suppliers
        FOREIGN KEY (SupplierID) REFERENCES Suppliers(SupplierID),
    CONSTRAINT CK_Products_CostPrice    CHECK (CostPrice >= 0),
    CONSTRAINT CK_Products_SellingPrice CHECK (SellingPrice >= 0)
);

/* ---- 6. Customers ---- */
CREATE TABLE Customers (
    CustomerID        INT IDENTITY(1,1) PRIMARY KEY,
    FirstName         VARCHAR(50)  NOT NULL,
    LastName          VARCHAR(50)  NOT NULL,
    Email             VARCHAR(100) NOT NULL UNIQUE,
    Phone             VARCHAR(20)  NULL,
    City              VARCHAR(50)  NULL,
    State             VARCHAR(50)  NULL,
    RegistrationDate  DATE NOT NULL DEFAULT CAST(GETDATE() AS DATE)
);

/* ---- 7. Employees: ManagerID is a SELF-REFERENCING FK (org hierarchy) ---- */
CREATE TABLE Employees (
    EmployeeID  INT IDENTITY(1,1) PRIMARY KEY,
    FirstName   VARCHAR(50)  NOT NULL,
    LastName    VARCHAR(50)  NOT NULL,
    Email       VARCHAR(100) NOT NULL UNIQUE,
    JobTitle    VARCHAR(50)  NOT NULL,
    HireDate    DATE         NOT NULL,
    StoreID     INT          NOT NULL,
    ManagerID   INT          NULL,
    CONSTRAINT FK_Employees_Stores
        FOREIGN KEY (StoreID) REFERENCES Stores(StoreID),
    CONSTRAINT FK_Employees_Manager
        FOREIGN KEY (ManagerID) REFERENCES Employees(EmployeeID)
);

/* ---- 8. Orders: no TotalAmount — it's derived from OrderDetails ---- */
CREATE TABLE Orders (
    OrderID      INT IDENTITY(1,1) PRIMARY KEY,
    CustomerID   INT      NOT NULL,
    StoreID      INT      NOT NULL,
    EmployeeID   INT      NULL,
    OrderDate    DATETIME NOT NULL DEFAULT GETDATE(),
    OrderStatus  VARCHAR(20) NOT NULL DEFAULT 'Completed',
    CONSTRAINT FK_Orders_Customers
        FOREIGN KEY (CustomerID) REFERENCES Customers(CustomerID),
    CONSTRAINT FK_Orders_Stores
        FOREIGN KEY (StoreID) REFERENCES Stores(StoreID),
    CONSTRAINT FK_Orders_Employees
        FOREIGN KEY (EmployeeID) REFERENCES Employees(EmployeeID),
    CONSTRAINT CK_Orders_Status
        CHECK (OrderStatus IN ('Completed', 'Pending', 'Cancelled'))
);

/* ---- 9. OrderDetails: UnitPrice = historical price at time of sale ---- */
CREATE TABLE OrderDetails (
    OrderDetailID  INT IDENTITY(1,1) PRIMARY KEY,
    OrderID        INT           NOT NULL,
    ProductID      INT           NOT NULL,
    Quantity       INT           NOT NULL,
    UnitPrice      DECIMAL(10,2) NOT NULL,
    CONSTRAINT FK_OrderDetails_Orders
        FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
    CONSTRAINT FK_OrderDetails_Products
        FOREIGN KEY (ProductID) REFERENCES Products(ProductID),
    CONSTRAINT CK_OrderDetails_Quantity  CHECK (Quantity > 0),
    CONSTRAINT CK_OrderDetails_UnitPrice CHECK (UnitPrice >= 0),
    CONSTRAINT UQ_OrderDetails_OrderProduct UNIQUE (OrderID, ProductID)
);

/* ---- 10. Payments: UNIQUE on OrderID makes this ONE-TO-ONE ---- */
CREATE TABLE Payments (
    PaymentID      INT IDENTITY(1,1) PRIMARY KEY,
    OrderID        INT           NOT NULL UNIQUE,
    PaymentDate    DATETIME      NOT NULL,
    PaymentMethod  VARCHAR(20)   NOT NULL,
    Amount         DECIMAL(10,2) NOT NULL,
    CONSTRAINT FK_Payments_Orders
        FOREIGN KEY (OrderID) REFERENCES Orders(OrderID),
    CONSTRAINT CK_Payments_Method
        CHECK (PaymentMethod IN ('Card','UPI','Cash','NetBanking','Wallet')),
    CONSTRAINT CK_Payments_Amount CHECK (Amount >= 0)
);

/* ---- 11. Inventory: COMPOSITE primary key (StoreID, ProductID) ---- */
CREATE TABLE Inventory (
    StoreID          INT  NOT NULL,
    ProductID        INT  NOT NULL,
    QuantityInStock  INT  NOT NULL,
    ReorderLevel     INT  NOT NULL DEFAULT 10,
    LastRestockDate  DATE NULL,
    CONSTRAINT PK_Inventory PRIMARY KEY (StoreID, ProductID),
    CONSTRAINT FK_Inventory_Stores
        FOREIGN KEY (StoreID) REFERENCES Stores(StoreID),
    CONSTRAINT FK_Inventory_Products
        FOREIGN KEY (ProductID) REFERENCES Products(ProductID),
    CONSTRAINT CK_Inventory_Qty CHECK (QuantityInStock >= 0)
);

/* ---- 12. Returns: links to a specific order LINE ---- */
CREATE TABLE Returns (
    ReturnID          INT IDENTITY(1,1) PRIMARY KEY,
    OrderDetailID     INT  NOT NULL,
    ReturnDate        DATE NOT NULL,
    QuantityReturned  INT  NOT NULL,
    Reason            VARCHAR(100) NULL,
    CONSTRAINT FK_Returns_OrderDetails
        FOREIGN KEY (OrderDetailID) REFERENCES OrderDetails(OrderDetailID),
    CONSTRAINT CK_Returns_Qty CHECK (QuantityReturned > 0)
);
GO

/* ---- Verification: should list all 12 tables ---- */
SELECT TABLE_NAME
FROM INFORMATION_SCHEMA.TABLES
WHERE TABLE_TYPE = 'BASE TABLE'
ORDER BY TABLE_NAME;
GO