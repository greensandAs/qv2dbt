-- SalesPY  [staging]  (from QlikView 'qvd')
select
    OrderID,
    ProductID,
    CustomerID,
    CountryCode,
    TO_DATE(OrderDate, 'YYYY-MM-DD') as ORDERDATE,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(GrossAmount) as GROSSAMOUNT
from LUNDBECK_UKIE.RAW.SALES_2025 as base
;
