-- Model: stg_product_sub_group_master  (layer: staging)
-- Migrated from QlikView table 'ProductSubGroupMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Product Sub Group",
    "Product Sub Group Desc"
    from {{ source('qlikview_raw', 'productsubgroupmaster') }}
)

select *
from base
