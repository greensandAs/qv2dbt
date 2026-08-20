-- ProductTypeMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_PRODUCT_TYPE_MASTER as
select
    "Product Type",
    "Product Type Desc"
from LUNDBECK_UKIE.RAW.PRODUCTTYPEMASTER as base
;
