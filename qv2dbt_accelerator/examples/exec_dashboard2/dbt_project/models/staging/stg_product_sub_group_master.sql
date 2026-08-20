-- Model: stg_product_sub_group_master  (layer: staging)
-- Migrated from QlikView table 'ProductSubGroupMaster' [qvd]
-- WARNING: Table 'ProductSubGroupMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Product Sub Group",
    "Product Sub Group Desc"
    from {{ source('qlikview_raw', 'productsubgroupmaster') }}
)

select *
from base
