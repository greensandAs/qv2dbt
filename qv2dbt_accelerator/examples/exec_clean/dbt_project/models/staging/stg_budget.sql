-- Model: stg_budget  (layer: staging)
-- Migrated from QlikView table 'Budget' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    MonthlyRegionKey,
    "Budget Amount"
    from {{ source('qlikview_raw', 'budget') }}
)

select *
from base
