-- Model: stg_history_flag  (layer: staging)
-- Migrated from QlikView table 'HistoryFlag' [qvd]
-- WARNING: Table 'HistoryFlag' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM,
    _HistoryFlag
    from {{ source('qlikview_raw', 'historyflag') }}
)

select *
from base
