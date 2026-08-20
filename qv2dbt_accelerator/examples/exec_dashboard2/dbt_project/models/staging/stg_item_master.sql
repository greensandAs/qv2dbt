-- Model: stg_item_master  (layer: staging)
-- Migrated from QlikView table 'ItemMaster' [qvd]
-- WARNING: Table 'ItemMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Product Group",
    "Product Line",
    "Product Sub Group",
    "Product Type",
    "Short Name"
    from {{ source('qlikview_raw', 'itemmaster') }}
)

select *
from base
