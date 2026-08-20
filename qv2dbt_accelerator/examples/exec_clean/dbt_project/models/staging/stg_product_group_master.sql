-- Model: stg_product_group_master  (layer: staging)
-- Migrated from QlikView table 'ProductGroupMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Product Group",
    "Product Group Desc"
    from {{ source('qlikview_raw', 'productgroupmaster') }}
)

select *
from base
