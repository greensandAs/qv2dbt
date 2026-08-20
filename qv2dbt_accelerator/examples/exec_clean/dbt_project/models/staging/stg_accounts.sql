-- Model: stg_accounts  (layer: staging)
-- Migrated from QlikView table 'Accounts' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    Account,
    AccountDesc
    from {{ source('qlikview_raw', 'accounts') }}
)

select *
from base
