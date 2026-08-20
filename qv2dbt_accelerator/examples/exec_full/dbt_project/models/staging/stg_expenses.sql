-- Model: stg_expenses  (layer: staging)
-- Migrated from QlikView table 'Expenses' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    MonthlyRegionKey,
    Account,
    ExpenseActual,
    ExpenseBudget
    from {{ source('qlikview_raw', 'expenses') }}
)

select *
from base
