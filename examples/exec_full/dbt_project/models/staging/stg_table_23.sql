-- Model: stg_table_23  (layer: staging)
-- Migrated from QlikView table 'table_23' [qvd]

{{ config(materialized='view') }}

with base as (
    select
    AccountGroup,
    AccountGroupDesc
    from {{ source('qlikview_raw', 'accountgroupmaster') }}
)

select *
from base
