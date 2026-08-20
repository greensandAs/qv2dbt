-- Model: stg_arsummary_1  (layer: staging)
-- Migrated from QlikView table 'ARSummary-1' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    CustKeyAR,
    ARAge,
    ARAgeBal
    from {{ source('qlikview_raw', 'arsummary_1') }}
)

select *
from base
