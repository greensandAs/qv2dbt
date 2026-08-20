-- Accounts  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ACCOUNTS as
select
    Account,
    AccountDesc
from LUNDBECK_UKIE.RAW.ACCOUNTS as base
;
