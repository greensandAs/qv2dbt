-- Model: stg_customer_map  (layer: staging)
-- Migrated from QlikView table 'CustomerMap' [qvd]
-- WARNING: Table 'CustomerMap' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    CustKey,
    CustKeyAR
    from {{ source('qlikview_raw', 'customermap') }}
)

select *
from base
