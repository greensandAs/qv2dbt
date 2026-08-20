-- Model: stg_item_branch_master  (layer: staging)
-- Migrated from QlikView table 'ItemBranchMaster' [qvd]
-- WARNING: Table 'ItemBranchMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Item-Branch Key",
    "Short Name"
    from {{ source('qlikview_raw', 'itembranchmaster') }}
)

select *
from base
