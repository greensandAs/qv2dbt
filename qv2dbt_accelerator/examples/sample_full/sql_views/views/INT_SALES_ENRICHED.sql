-- SalesEnriched  [intermediate]  (from QlikView 'resident')
create or replace view LUNDBECK_UKIE.STAGING.INT_SALES_ENRICHED as
select *
from (select 
    OrderID,
    ProductID,
    CustomerID,
    Country,
    OrderDate,
    Quantity,
    GrossAmount
from LUNDBECK_UKIE.STAGING.INT_SALES_RAW) as base
left join LUNDBECK_UKIE.STAGING.INT_SALES_ENRICHED_JOIN6 as j1 using (PRODUCTID)
;
