-- Model: stg_account_master  (layer: staging)
-- Migrated from QlikView table 'AccountMaster' [qvd]
-- WARNING: Table 'AccountMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    Account,
    AccountGroup
    from {{ source('qlikview_raw', 'accountmaster') }}
)

select *
from base
