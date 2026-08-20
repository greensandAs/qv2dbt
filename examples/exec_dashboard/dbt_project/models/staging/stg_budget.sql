-- Model: stg_budget  (layer: staging)
-- Migrated from QlikView table 'Budget' [file]

{{ config(materialized='view') }}

with base as (
    select
    Region  ||  '_'  ||  TO_DATE(DATEADD('MONTH', 12, Month), 'YYYYMM') as MONTHLYREGIONKEY,
    Budget as BUDGET AMOUNT
    from {{ source('qlikview_raw', 'regionalsales') }}
)

select *
from base
