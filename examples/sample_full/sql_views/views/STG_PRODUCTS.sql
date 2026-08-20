-- Products  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_PRODUCTS as
select
    ProductID,
    ProductName,
    "Therapeutic Area" as THERAPEUTICAREA,
    TO_NUMBER(UnitPrice) as UNITPRICE,
    CASE WHEN Discontinued = 1 THEN 'Y' ELSE 'N' END as ISDISCONTINUED
from LUNDBECK_UKIE.RAW.PRODUCTS as base
;
