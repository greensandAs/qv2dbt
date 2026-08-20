-- Model: stg_customer_address_master  (layer: staging)
-- Migrated from QlikView table 'CustomerAddressMaster' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    "Address Number",
    "Customer Address 1",
    "Zip Code"
    from {{ source('qlikview_raw', 'customeraddressmaster') }}
)

select *
from base
