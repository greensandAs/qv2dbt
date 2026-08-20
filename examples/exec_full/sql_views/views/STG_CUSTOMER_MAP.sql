-- CustomerMap  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CUSTOMER_MAP as
select
    CustKey,
    CustKeyAR
from LUNDBECK_UKIE.RAW.CUSTOMERMAP as base
;
