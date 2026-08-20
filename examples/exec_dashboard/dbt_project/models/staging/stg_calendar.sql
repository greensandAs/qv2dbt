-- Model: stg_calendar  (layer: staging)
-- Migrated from QlikView table 'Calendar' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Fiscal Quarter",
    "Fiscal Year"+1 as FISCAL YEAR,
    MONTH(DATEADD('MONTH', 12, YYYYMM)) as FISCALMONTH,
    TO_NUMBER(MONTH(DATEADD('MONTH', 12, YYYYMM))) as FISCALMONTHNUM,
    FiscalRollQt,
    DATEADD('MONTH', 12, YYYYMM) as YYYYMM
    from {{ source('qlikview_raw', 'calendar') }}
)

select *
from base
