-- FactTable Init  [mart]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.MARTS.MART_FACT_TABLE_INIT as
select
    MonthlyRegionKey,
    Region,
    "Address Number",
    CustKey,
    "Invoice Number",
    "Item-Branch Key",
    "Late Shipment",
    "Line Desc 1",
    "Open Order Amount",
    "Order Number",
    "Order Status",
    DATEADD('MONTH', 9, OrderDate) as ORDERDATE,
    OrderID,
    OrderStat,
    DATEADD('MONTH', 9, "Promised Delivery Date") as PROMISED DELIVERY DATE,
    "Sales Amount",
    "Sales Cost Amount",
    "Sales Margin Amount",
    "Sales Price",
    "Sales Quantity",
    "Ship To",
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM
from LUNDBECK_UKIE.RAW.FACTTABLE as base
;
