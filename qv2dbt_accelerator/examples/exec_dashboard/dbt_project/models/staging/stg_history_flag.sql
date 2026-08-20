-- Model: stg_history_flag  (layer: staging)
-- Migrated from QlikView table 'HistoryFlag' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    DATEADD('MONTH', 9, YYYYMM) as YYYYMM,
    _HistoryFlag
    from {{ source('qlikview_raw', 'historyflag') }}
)

select *
from base
