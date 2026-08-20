-- Model: int_orders_join3  (layer: intermediate)
-- Migrated from QlikView table 'Orders__join3' [resident]

{{ config(materialized='view') }}

with base as (
    select
    CustomerID,
    Country,
    CreditLimit
    from {{ ref('stg_customers') }}
)

select *
from base
