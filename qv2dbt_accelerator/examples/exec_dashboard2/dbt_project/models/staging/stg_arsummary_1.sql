-- Model: stg_arsummary_1  (layer: staging)
-- Migrated from QlikView table 'ARSummary-1' [qvd]
-- WARNING: Table 'ARSummary-1' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

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
