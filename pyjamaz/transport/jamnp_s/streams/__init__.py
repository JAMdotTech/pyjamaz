from pyjamaz.transport.jamnp_s.streams.ce129 import CE129Handler
from pyjamaz.transport.jamnp_s.streams.ce128 import CE128Handler
from pyjamaz.transport.jamnp_s.streams.ce131 import CE131Handler
from pyjamaz.transport.jamnp_s.streams.ce132 import CE132Handler
from pyjamaz.transport.jamnp_s.streams.ce133 import CE133Handler
from pyjamaz.transport.jamnp_s.streams.ce134 import CE134Handler
from pyjamaz.transport.jamnp_s.streams.ce135 import CE135Handler
from pyjamaz.transport.jamnp_s.streams.ce136 import CE136Handler
from pyjamaz.transport.jamnp_s.streams.ce137 import CE137Handler
from pyjamaz.transport.jamnp_s.streams.ce138 import CE138Handler
from pyjamaz.transport.jamnp_s.streams.ce139 import CE139Handler
from pyjamaz.transport.jamnp_s.streams.ce140 import CE140Handler
from pyjamaz.transport.jamnp_s.streams.ce141 import CE141Handler
from pyjamaz.transport.jamnp_s.streams.ce142 import CE142Handler
from pyjamaz.transport.jamnp_s.streams.ce143 import CE143Handler
from pyjamaz.transport.jamnp_s.streams.ce144 import CE144Handler
from pyjamaz.transport.jamnp_s.streams.ce145 import CE145Handler
from pyjamaz.transport.jamnp_s.streams.context import ProtocolContext, ProtocolSharedState
from pyjamaz.transport.jamnp_s.streams.up0 import UP0Handler


def register_handlers(stream_manager, context: ProtocolContext):
    handlers = [
        UP0Handler(context),
        CE128Handler(context),
        CE129Handler(context),
        CE131Handler(context),
        CE132Handler(context),
        CE133Handler(context),
        CE134Handler(context),
        CE135Handler(context),
        CE136Handler(context),
        CE137Handler(context),
        CE138Handler(context),
        CE139Handler(context),
        CE140Handler(context),
        CE141Handler(context),
        CE142Handler(context),
        CE143Handler(context),
        CE144Handler(context),
        CE145Handler(context),
    ]

    for handler in handlers:
        context.register_handler(handler)
        stream_manager.register_handler(handler)
    return context.handlers


__all__ = [
    "ProtocolContext",
    "ProtocolSharedState",
    "register_handlers",
]
