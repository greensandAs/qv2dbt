-- Model: stg_expenses  (layer: staging)
-- Migrated from QlikView table 'Expenses' [file]

{{ config(materialized='view') }}

with base as (
    select
    Region  ||  '_'  ||  TO_DATE(DATEADD('MONTH', 12, YYYYMM), 'YYYYMM') as MONTHLYREGIONKEY,
    Region,
    Account,
    DATEADD('MONTH', 12, YYYYMM) as YYYYMM,
    ExpenseActual,
    ExpeenseBudget as EXPENSEBUDGET
    from {{ source('qlikview_raw', 'expenses') }}
)

select *
from base
