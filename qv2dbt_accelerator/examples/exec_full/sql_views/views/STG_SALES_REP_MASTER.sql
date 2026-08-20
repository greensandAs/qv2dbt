-- SalesRepMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_SALES_REP_MASTER as
select
    "Sales Rep",
    "Sales Rep Name"
from LUNDBECK_UKIE.RAW.SALESREPMASTER as base
;
