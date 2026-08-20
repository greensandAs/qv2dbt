-- SalesEnriched__join6  [intermediate]  (from QlikView 'resident')
create or replace view LUNDBECK_UKIE.STAGING.INT_SALES_ENRICHED_JOIN6 as
select
    ProductID,
    ProductName,
    TherapeuticArea
from LUNDBECK_UKIE.STAGING.STG_PRODUCTS as base
;
