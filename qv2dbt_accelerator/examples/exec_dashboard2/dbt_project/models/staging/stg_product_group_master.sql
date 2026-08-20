-- Model: stg_product_group_master  (layer: staging)
-- Migrated from QlikView table 'ProductGroupMaster' [qvd]
-- WARNING: Table 'ProductGroupMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Product Group",
    "Product Group Desc"
    from {{ source('qlikview_raw', 'productgroupmaster') }}
)

select *
from base
