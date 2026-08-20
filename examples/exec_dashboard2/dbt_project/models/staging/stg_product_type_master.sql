-- Model: stg_product_type_master  (layer: staging)
-- Migrated from QlikView table 'ProductTypeMaster' [qvd]
-- WARNING: Table 'ProductTypeMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Product Type",
    "Product Type Desc"
    from {{ source('qlikview_raw', 'producttypemaster') }}
)

select *
from base
