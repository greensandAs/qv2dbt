-- AccountGroupMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ACCOUNT_GROUP_MASTER as
select
    AccountGroup,
    AccountGroupDesc
from LUNDBECK_UKIE.RAW.ACCOUNTGROUPMASTER as base
;
