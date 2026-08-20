-- ItemMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_ITEM_MASTER as
select
    "Product Group",
    "Product Line",
    "Product Sub Group",
    "Product Type",
    "Short Name"
from LUNDBECK_UKIE.RAW.ITEMMASTER as base
;
