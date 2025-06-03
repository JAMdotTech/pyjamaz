import asyncio
import datetime
import logging
import os
import ssl
from typing import cast

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent, HandshakeCompleted, ConnectionTerminated
from cryptography import x509

from pyjamaz.app import Keys
from pyjamaz.utils import quic_peer_id

#certificate_file = os.path.join("./pyjamaz/data/alice", "cert.pem")
#certificate_file = os.path.join("./", "clone2.pem")
certificate_file = os.path.join("./pyjamaz/data/alice", "cert.pem")
pk_file = os.path.join("./pyjamaz/data/alice", "cert.key")

PROTOCOL_ALPN = "jamnp-s/0/b5af8eda"

from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519


class ServerProtocol(QuicConnectionProtocol):
    """
    The tiniest QUIC protocol: just dump every event to the log.
    """

    def quic_event_received(self, event: QuicEvent) -> None:
        #logging.info("EVENT from %s: %s", event)
        print("SERVER:", event)
        if isinstance(event, HandshakeCompleted):
            print("Handshake")
        if isinstance(event, ConnectionTerminated):
            print("Terminated")


async def server():
    configuration = QuicConfiguration(
        alpn_protocols=[PROTOCOL_ALPN],
        is_client=False,
        # verify_mode=ssl.CERT_REQUIRED,
        verify_mode=ssl.CERT_NONE,
        idle_timeout=300000
    )
    configuration.load_cert_chain(certfile=certificate_file, keyfile=pk_file)
    print("SERVER")
    await serve(
        "127.0.0.1",
        40000,
        configuration=configuration,
        create_protocol=ServerProtocol,
        retry=True,
    )


# async def client():
#     configuration = QuicConfiguration(
#         #b5af8edad70d962097eefa2cef92c8284cf0a7578b70a6b7554cf53ae6d51222
#         alpn_protocols=[PROTOCOL_APLN],
#         #alpn_protocols=["jamnp-s/0/0259fbe9"],
#         is_client=True,
#         # verify_mode=ssl.CERT_REQUIRED,
#         verify_mode=False,
#         idle_timeout=300000
#     )
#     configuration.load_cert_chain(certfile=certificate_file, keyfile=pk_file)
#
#     print("CLIENt")
#     async with connect("127.0.0.1", 40001, configuration=configuration)  as connection:
#
#         await connection.wait_connected()
#
#         await asyncio.sleep(2)
#         cert = connection._quic.tls._peer_certificate
#         keys = Keys.from_seed(bytes(32))
#         #priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
#         priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
#
#         """
#         from cryptography import x509
#         from cryptography.x509.oid import NameOID
#
#         subject = x509.Name([
#             x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
#         ])
#         issuer = x509.Name([
#             x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
#         ])
#         pubkey!!!!!
#         serial_numer = 76354585232599687591316365089471291226684720524
#         not_valid_before=datetime.datetime(1975, 1, 1, 0, 0)
#         not_valid_after=datetime.datetime(4096, 1, 1, 0, 0)
#         extension = x509.SubjectAlternativeName(x509.GeneralNames([x509.DNSName("e3r2oc62zwfj3crnuifuvsxvbtlzetk4o5qyhetkhagsc2fgl2oka")])
#         """
#
#         builder = (
#             x509.CertificateBuilder()
#             .subject_name(cert.subject)
#             .issuer_name(cert.issuer)
#             .public_key(priv.public_key())
#             .serial_number(cert.serial_number)
#             .not_valid_before(cert.not_valid_before)
#             .not_valid_after(cert.not_valid_after)
#             .add_extension(x509.SubjectAlternativeName(x509.GeneralNames([x509.DNSName("e3r2oc62zwfj3crnuifuvsxvbtlzetk4o5qyhetkhagsc2fgl2oka")])), critical=False)
#         )
#
#         # copy every extension verbatim
#         # for ext in cert.extensions:
#         #     builder = builder.add_extension(ext.value, critical=ext.critical)
#
#         # @127.0.0.1:40000
#         #ehnvcppgow2sc2yvdvdicu3ynonsteflxdxrehjr2ybekdc2z3iuq
#
#         # ------------------------------------------------------------
#         # 2) sign with the *same* private key
#         # ------------------------------------------------------------
#         clone = builder.sign(private_key=priv, algorithm=None)  # Ed25519 = algorithm None
#
#         # ------------------------------------------------------------
#         # 3) serialize
#         # ------------------------------------------------------------
#         der_bytes = clone.public_bytes(serialization.Encoding.DER)
#         pem_bytes = clone.public_bytes(serialization.Encoding.PEM)
#
#         with open("clone.pem", "wb") as f:
#             f.write(pem_bytes)
#


class ClientProtocol(QuicConnectionProtocol):
    def quic_event_received(self, event: QuicEvent) -> None:
        #logging.info("EVENT from %s: %s", event)
        print("CLIENT????", event)


async def client():
    configuration = QuicConfiguration(
        alpn_protocols=[PROTOCOL_ALPN],
        is_client=True,
        #verify_mode=ssl.CERT_REQUIRED,
        verify_mode=ssl.CERT_NONE,
        idle_timeout=300000
    )

    configuration.load_cert_chain(certfile=certificate_file, keyfile=pk_file)

    print("CLIENT START")
    async with connect("127.0.0.1", 40001, configuration=configuration, create_protocol=ClientProtocol)  as connection:
        client_conn = cast(ClientProtocol, connection)
        await client_conn.wait_closed()


async def main():
    async with asyncio.TaskGroup() as tg:
        tg.create_task(server())   # background
        await client()               # foreground; when it returns the
                                   # task-group is cancelled automatically


if __name__ == "__main__":
    # #asyncio.run(server())
    # print("start client")
    # loop = asyncio.get_event_loop()
    # loop.run_until_complete(test())
    # loop.run_until_complete(server())
    # print("fin?")
    #
    # keys = Keys.from_seed(bytes(32))
    # priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
    #
    # from cryptography import x509
    # from cryptography.x509.oid import NameOID
    #
    # subject = x509.Name([
    #     x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
    # ])
    # issuer = x509.Name([
    #     x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
    # ])
    # serial_numer = 76354585232599687591316365089471291226684720524
    # not_valid_before = datetime.datetime(1975, 1, 1, 0, 0)
    # not_valid_after = datetime.datetime(4096, 1, 1, 0, 0)
    # peer_id = quic_peer_id(keys.ed25519.public_key)
    # print(peer_id)
    # ext = x509.SubjectAlternativeName(x509.GeneralNames([x509.DNSName(peer_id)]))
    #
    # builder = (
    #     x509.CertificateBuilder()
    #     .subject_name(subject)
    #     .issuer_name(issuer)
    #     .public_key(priv.public_key())
    #     .serial_number(serial_numer)
    #     .not_valid_before(not_valid_before)
    #     .not_valid_after(not_valid_after)
    #     .add_extension(x509.SubjectAlternativeName(
    #         x509.GeneralNames(ext)), critical=False)
    # )
    #
    # clone = builder.sign(private_key=priv, algorithm=None)  # Note: Ed25519 = algorithm None
    #
    # der_bytes = clone.public_bytes(serialization.Encoding.DER)
    # pem_bytes = clone.public_bytes(serialization.Encoding.PEM)
    #
    # with open("clone2.pem", "wb") as f:
    #     f.write(pem_bytes)

    asyncio.run(main())
