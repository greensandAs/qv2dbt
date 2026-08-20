-- Model: int_sales_raw_join4  (layer: intermediate)
-- Migrated from QlikView table 'SalesRaw__join4' [resident]

{{ config(materialized='view') }}

with base as (
    select
    *
    from {{ ref('stg_sales_py') }}
)

select *
from base
