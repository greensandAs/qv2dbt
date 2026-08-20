-- Model: stg_account_master  (layer: staging)
-- Migrated from QlikView table 'AccountMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    Account,
    AccountGroup
    from {{ source('qlikview_raw', 'accountmaster') }}
)

select *
from base
