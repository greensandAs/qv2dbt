-- Model: stg_item_master  (layer: staging)
-- Migrated from QlikView table 'ItemMaster' [qvd]

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
