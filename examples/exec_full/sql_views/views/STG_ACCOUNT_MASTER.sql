-- AccountMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ACCOUNT_MASTER as
select
    Account,
    AccountGroup
from LUNDBECK_UKIE.RAW.ACCOUNTMASTER as base
;
