-- Model: stg_channel_master  (layer: staging)
-- Migrated from QlikView table 'ChannelMaster' [qvd]
-- WARNING: Table 'ChannelMaster' is defined by multiple LOADs - QlikView auto-concatenates these; review/merge the generated models (likely UNION ALL).

{{ config(materialized='view') }}

with base as (
    select
    Segment,
    SegmentDesc,
    SegmentGroup
    from {{ source('qlikview_raw', 'channelmaster') }}
)

select *
from base
