-- table_23  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_TABLE_23 as
select
    AccountGroup,
    AccountGroupDesc
from LUNDBECK_UKIE.RAW.ACCOUNTGROUPMASTER as base
;
