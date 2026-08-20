-- Model: stg_item_branch_master  (layer: staging)
-- Migrated from QlikView table 'ItemBranchMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Item-Branch Key",
    "Short Name"
    from {{ source('qlikview_raw', 'itembranchmaster') }}
)

select *
from base
