-- Model: stg_channel_master  (layer: staging)
-- Migrated from QlikView table 'ChannelMaster' [qvd]

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
