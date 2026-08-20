-- Model: stg_sales_rep_master  (layer: staging)
-- Migrated from QlikView table 'SalesRepMaster' [qvd]
-- WARNING: Table 'SalesRepMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Sales Rep",
    "Sales Rep Name"
    from {{ source('qlikview_raw', 'salesrepmaster') }}
)

select *
from base
