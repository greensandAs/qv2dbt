-- Model: stg_customer_master  (layer: staging)
-- Migrated from QlikView table 'CustomerMaster' [qvd]
-- WARNING: Table 'CustomerMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    "Address Number",
    "Business Family",
    Segment,
    Customer,
    "Customer Number",
    "Customer Type",
    "Distribution Channel Mgr",
    Division,
    Phone,
    "Region Code",
    "Regional Sales Mgr",
    "Zone Mgr",
    "Sales Rep"
    from {{ source('qlikview_raw', 'customermaster') }}
)

select *
from base
