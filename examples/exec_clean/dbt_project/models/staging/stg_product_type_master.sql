-- Model: stg_product_type_master  (layer: staging)
-- Migrated from QlikView table 'ProductTypeMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Product Type",
    "Product Type Desc"
    from {{ source('qlikview_raw', 'producttypemaster') }}
)

select *
from base
