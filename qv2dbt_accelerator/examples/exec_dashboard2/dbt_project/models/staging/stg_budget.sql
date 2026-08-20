-- Model: stg_budget  (layer: staging)
-- Migrated from QlikView table 'Budget' [file]
-- WARNING: Table 'Budget' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    Region  ||  '_'  ||  TO_DATE(DATEADD('MONTH', 12, Month), 'YYYYMM') as MONTHLYREGIONKEY,
    Budget as BUDGET AMOUNT
    from {{ source('qlikview_raw', 'regionalsales') }}
)

select *
from base
