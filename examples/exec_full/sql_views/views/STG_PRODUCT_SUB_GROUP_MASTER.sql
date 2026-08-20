-- ProductSubGroupMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_PRODUCT_SUB_GROUP_MASTER as
select
    "Product Sub Group",
    "Product Sub Group Desc"
from LUNDBECK_UKIE.RAW.PRODUCTSUBGROUPMASTER as base
;
