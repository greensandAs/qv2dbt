-- Model: int_history_flag  (layer: intermediate)
-- Migrated from QlikView table 'HistoryFlag' [resident]
-- WARNING: Table 'HistoryFlag' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    DISTINCT
    YYYYMM,
    CASE WHEN YYYYMM <= DATE_TRUNC('MONTH', TO_NUMBER(DATE_FROM_PARTS(2013, 5, 31))) THEN 1 ELSE 0 END as _HISTORYFLAG
    from {{ ref('stg_fact_table') }}
)

select *
from base
