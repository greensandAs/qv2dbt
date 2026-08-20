-- Model: stg_arsummary  (layer: staging)
-- Migrated from QlikView table 'ARSummary' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    CustKeyAR,
    ARGross,
    AROpen,
    ARCurrent,
    "AR1-30",
    "AR31-60",
    "AR60+",
    ARCredit,
    ARSalesPerDay,
    ARAvgBal
    from {{ source('qlikview_raw', 'arsummary') }}
)

select *
from base
