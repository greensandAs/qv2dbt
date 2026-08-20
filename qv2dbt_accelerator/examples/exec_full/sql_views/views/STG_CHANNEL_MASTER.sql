-- ChannelMaster  [staging]  (from QlikView 'qvd')
create or replace view LUNDBECK_UKIE.STAGING.STG_CHANNEL_MASTER as
select
    Segment,
    SegmentDesc,
    SegmentGroup
from LUNDBECK_UKIE.RAW.CHANNELMASTER as base
;
