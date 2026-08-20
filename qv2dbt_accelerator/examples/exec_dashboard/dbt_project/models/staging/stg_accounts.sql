-- Model: stg_accounts  (layer: staging)
-- Migrated from QlikView table 'Accounts' [file]

{{ config(materialized='view') }}

with base as (
    select
    Account,
    AccountDesc
    from {{ source('qlikview_raw', 'expenseaccounts') }}
    where AccountDesc > 0
)

select *
from base
