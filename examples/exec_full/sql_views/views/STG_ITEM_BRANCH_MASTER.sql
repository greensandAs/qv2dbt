-- ItemBranchMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ITEM_BRANCH_MASTER as
select
    "Item-Branch Key",
    "Short Name"
from LUNDBECK_UKIE.RAW.ITEMBRANCHMASTER as base
;
