-- Model: stg_account_group_master  (layer: staging)
-- Migrated from QlikView table 'AccountGroupMaster' [qvd]
-- WARNING: Table 'AccountGroupMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    AccountGroup,
    AccountGroupDesc
    from {{ source('qlikview_raw', 'accountgroupmaster') }}
)

select *
from base
