-- Budget  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_BUDGET as
select
    MonthlyRegionKey,
    "Budget Amount"
from LUNDBECK_UKIE.RAW.BUDGET as base
;
