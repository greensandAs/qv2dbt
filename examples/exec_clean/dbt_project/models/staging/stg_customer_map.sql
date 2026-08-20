-- Model: stg_customer_map  (layer: staging)
-- Migrated from QlikView table 'CustomerMap' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    CustKey,
    CustKeyAR
    from {{ source('qlikview_raw', 'customermap') }}
)

select *
from base
