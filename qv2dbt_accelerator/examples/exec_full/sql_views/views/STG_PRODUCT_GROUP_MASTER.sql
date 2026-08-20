-- ProductGroupMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_PRODUCT_GROUP_MASTER as
select
    "Product Group",
    "Product Group Desc"
from LUNDBECK_UKIE.RAW.PRODUCTGROUPMASTER as base
;
