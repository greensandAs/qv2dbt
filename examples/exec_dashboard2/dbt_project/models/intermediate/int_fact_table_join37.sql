-- Model: int_fact_table_join37  (layer: intermediate)
-- Migrated from QlikView table 'FactTable__join37' [resident]

{{ config(materialized='view') }}

with base as (
    select
    MonthlyRegionKey,
    Region,
    YYYYMM
    from {{ ref('stg_expenses') }}
)

select *
from base
