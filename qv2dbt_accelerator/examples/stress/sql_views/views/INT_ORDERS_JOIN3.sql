-- Orders__join3  [intermediate]  (from QlikView 'resident')
create or replace view LUNDBECK_UKIE.STAGING.INT_ORDERS_JOIN3 as
select
    CustomerID,
    Country,
    CreditLimit
from LUNDBECK_UKIE.STAGING.STG_CUSTOMERS as base
;
