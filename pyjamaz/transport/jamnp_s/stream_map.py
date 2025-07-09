from pyjamaz.transport.jamnp_s.stream_base import StreamType
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP
from pyjamaz.transport.jamnp_s.streams.stream_128 import StreamBlockRequest

StreamLookup = {
    StreamType.UP0_BlockAnnouncement.value: StreamUP,
    StreamType.CE128_BlockRequest.value: StreamBlockRequest,
    # StreamType.CE129_StateRequest.value: ,
    # StreamType.CE131_SafroleTicketDistributionStep1.value: ,
    # StreamType.CE132_SafroleTicketDistributionStep2.value: ,
    # StreamType.CE133_WorkPackageSubmission.value: ,
    # StreamType.CE134_WorkPackageSharing.value: ,
    # StreamType.CE135_WorkReportDistribution.value: ,
    # StreamType.CE136_WorkReportRequest.value: ,
    # StreamType.CE137_ShardDistribution.value: ,
    # StreamType.CE138_AuditShardRequest.value: ,
    # StreamType.CE139_SegmentShardRequest.value: ,
    # StreamType.CE140_SegmentShardRequestJustification.value: ,
    # StreamType.CE141_AssuranceDistribution.value: ,
}