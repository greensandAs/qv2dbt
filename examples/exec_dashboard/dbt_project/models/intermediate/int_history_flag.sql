-- Model: int_history_flag  (layer: intermediate)
-- Migrated from QlikView table 'HistoryFlag' [resident]

{{ config(materialized='view') }}

with base as (
    select
    distinct
    YYYYMM,
    CASE WHEN YYYYMM <= DATE_TRUNC('MONTH', TO_NUMBER(DATE_FROM_PARTS(2013, 5, 31))) THEN 1 ELSE 0 END as _HISTORYFLAG
    from {{ ref('stg_fact_table') }}
)

select *
from base
