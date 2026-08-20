-- Model: stg_table_25  (layer: staging)
-- Migrated from QlikView table 'table_25' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    AccountGroup,
    AccountGroupDesc
    from {{ source('qlikview_raw', 'accountgroupmaster') }}
)

select *
from base
