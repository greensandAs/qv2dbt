-- Model: stg_calendar  (layer: staging)
-- Migrated from QlikView table 'Calendar' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Fiscal Quarter",
    FiscalMonthNum,
    "Fiscal Year",
    FiscalMonth,
    FiscalRollQt,
    YYYYMM
    from {{ source('qlikview_raw', 'calendar_2024') }}
)

select *
from base
