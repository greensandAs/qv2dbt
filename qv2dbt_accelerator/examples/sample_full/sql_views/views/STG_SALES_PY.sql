-- SalesPY  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_SALES_PY as
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
