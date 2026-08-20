-- Model: stg_account_group_master  (layer: staging)
-- Migrated from QlikView table 'AccountGroupMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    AccountGroup,
    AccountGroupDesc
    from {{ source('qlikview_raw', 'accountgroupmaster') }}
)

select *
from base
