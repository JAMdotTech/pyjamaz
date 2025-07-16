from pyjamaz.transport.jamnp_s.stream_base import StreamType
from pyjamaz.transport.jamnp_s.streams.stream_0 import StreamUP
from pyjamaz.transport.jamnp_s.streams.stream_128 import StreamBlockRequest
from pyjamaz.transport.jamnp_s.streams.stream_131 import StreamSafroleTicketDistributionStep1
from pyjamaz.transport.jamnp_s.streams.stream_132 import StreamSafroleTicketDistributionStep2
from pyjamaz.transport.jamnp_s.streams.stream_134 import StreamWorkPackageSharing
from pyjamaz.transport.jamnp_s.streams.stream_141 import StreamAssuranceDistribution
from pyjamaz.transport.jamnp_s.streams.stream_142 import StreamPreimageAnnouncement
from pyjamaz.transport.jamnp_s.streams.stream_143 import StreamPreimageRequest
from pyjamaz.transport.jamnp_s.streams.stream_133 import StreamWorkPackageSubmission
from pyjamaz.transport.jamnp_s.streams.stream_135 import StreamWorkReportDistribution
from pyjamaz.transport.jamnp_s.streams.stream_136 import StreamWorkReportRequest

StreamLookup = {
    StreamType.UP0_BlockAnnouncement.value: StreamUP,
    StreamType.CE128_BlockRequest.value: StreamBlockRequest,
    StreamType.CE131_SafroleTicketDistributionStep1.value: StreamSafroleTicketDistributionStep1,
    StreamType.CE132_SafroleTicketDistributionStep2.value: StreamSafroleTicketDistributionStep2,
    StreamType.CE134_WorkPackageSharing.value: StreamWorkPackageSharing,
    StreamType.CE141_AssuranceDistribution.value: StreamAssuranceDistribution,
    StreamType.CE142_PreimageAnnouncement.value: StreamPreimageAnnouncement,
    StreamType.CE143_PreimageRequest.value: StreamPreimageRequest,
    StreamType.CE133_WorkPackageSubmission.value: StreamWorkPackageSubmission,
    StreamType.CE135_WorkReportDistribution.value: StreamWorkReportDistribution,
    StreamType.CE136_WorkReportRequest.value: StreamWorkReportRequest,
    # StreamType.CE137_ShardDistribution.value: ,
    # StreamType.CE138_AuditShardRequest.value: ,
    # StreamType.CE139_SegmentShardRequest.value: ,
    # StreamType.CE140_SegmentShardRequestJustification.value: ,
    # StreamType.CE141_AssuranceDistribution.value: ,
}