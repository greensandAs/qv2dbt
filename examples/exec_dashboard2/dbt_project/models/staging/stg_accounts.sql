-- Model: stg_accounts  (layer: staging)
-- Migrated from QlikView table 'Accounts' [file]
-- WARNING: Table 'Accounts' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

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
