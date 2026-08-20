-- FactTable  [mart]  (from QlikView 'resident')
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
    OrderDate,
    OrderID,
    OrderStat,
    "Promised Delivery Date",
    "Sales Amount",
    "Sales Cost Amount",
    "Sales Margin Amount",
    "Sales Price",
    "Sales Quantity",
    "Ship To",
    YYYYMM
from LUNDBECK_UKIE.MARTS.MART_FACT_TABLE_INIT as base
;
