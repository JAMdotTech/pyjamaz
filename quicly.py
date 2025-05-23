import asyncio
import logging
import os
import ssl

from aioquic.asyncio import serve, QuicConnectionProtocol
from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from aioquic.quic.events import QuicEvent
from cryptography import x509

from pyjamaz.app import Keys

#certificate_file = os.path.join("./pyjamaz/data/karel", "cert.pem")
certificate_file = os.path.join("./", "clone.pem")
pk_file = os.path.join("./pyjamaz/data/karel", "cert.key")


from cryptography import x509
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import ed25519


class ServerProtocol(QuicConnectionProtocol):
    """
    The tiniest QUIC protocol: just dump every event to the log.
    """

    def quic_event_received(self, event: QuicEvent) -> None:
        #logging.info("EVENT from %s: %s", event)
        print("HUH????", event)



async def server():
    configuration = QuicConfiguration(
        alpn_protocols=["jamnp-s/0/0259fbe9"],
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


async def client():
    configuration = QuicConfiguration(
        alpn_protocols=["jamnp-s/0/0259fbe9"],
        is_client=True,
        # verify_mode=ssl.CERT_REQUIRED,
        verify_mode=ssl.CERT_NONE,
        idle_timeout=300000
    )
    configuration.load_cert_chain(certfile=certificate_file, keyfile=pk_file)

    print("CLIENt")
    async with connect("127.0.0.1", 40001, configuration=configuration)  as connection:

        cert = connection._quic.tls._peer_certificate

        keys = Keys.from_seed(bytes(32))
        #priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
        priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)

        builder = (
            x509.CertificateBuilder()
            .subject_name(cert.subject)
            .issuer_name(cert.issuer)
            .public_key(priv.public_key())
            .serial_number(cert.serial_number)
            .not_valid_before(cert.not_valid_before)
            .not_valid_after(cert.not_valid_after)
        )

        # copy every extension verbatim
        # for ext in cert.extensions:
        #     builder = builder.add_extension(ext.value, critical=ext.critical)

        # @127.0.0.1:40000
        #ehnvcppgow2sc2yvdvdicu3ynonsteflxdxrehjr2ybekdc2z3iuq
        builder.add_extension(
            x509.SubjectAlternativeName(x509.GeneralNames([x509.DNSName("e3r2oc62zwfj3crnuifuvsxvbtlzetk4o5qyhetkhagsc2fgl2oka")])), critical=False
        )

        # ------------------------------------------------------------
        # 2) sign with the *same* private key
        # ------------------------------------------------------------
        clone = builder.sign(private_key=priv, algorithm=None)  # Ed25519 = algorithm None

        # ------------------------------------------------------------
        # 3) serialize
        # ------------------------------------------------------------
        der_bytes = clone.public_bytes(serialization.Encoding.DER)
        pem_bytes = clone.public_bytes(serialization.Encoding.PEM)

        with open("clone.pem", "wb") as f:
            f.write(pem_bytes)


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

    asyncio.run(main())