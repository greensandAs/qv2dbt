-- SalesRaw  [intermediate]  (from QlikView 'file')
select
    OrderID,
    ProductID,
    CustomerID,
    CountryCode,
    TO_DATE(OrderDate, 'YYYY-MM-DD') as ORDERDATE,
    TO_NUMBER(Quantity) as QUANTITY,
    TO_NUMBER(UnitPrice) * TO_NUMBER(Quantity) as GROSSAMOUNT,
    coalesce((select MAPPED_VALUE from LUNDBECK_UKIE.STAGING.MAP_COUNTRY_MAP where MAPPED_KEY = CountryCode limit 1), 'Unknown') as COUNTRY,
    LEFT(OrderID, 4) as ORDERPREFIX
from LUNDBECK_UKIE.RAW.SALES_2026 as base
union all
select * from LUNDBECK_UKIE.STAGING.INT_SALES_RAW_JOIN4
where LENGTH(OrderID) > 0
;
