# from cryptography import x509
# from cryptography.x509.oid import ExtendedKeyUsageOID as EKU, NameOID
# from cryptography.hazmat.primitives.asymmetric import ed25519
# from cryptography.hazmat.primitives import serialization
# from ipaddress import ip_address
# from datetime import datetime, timedelta
#
#
# def generate_cert(keys, ips: str, alternative_name: str):
#     priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
#
#     sans = [x509.IPAddress(ip_address(ip.strip()))
#             for ip in ips.split(",") if ip.strip()]
#     sans.append(x509.DNSName(alternative_name))
#
#     name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "jamnps-node")])
#
#     cert = (
#         x509.CertificateBuilder()
#         .subject_name(name).issuer_name(name)
#         .public_key(priv.public_key())
#         .serial_number(x509.random_serial_number())
#         .not_valid_before(datetime.utcnow() - timedelta(minutes=5))
#         .not_valid_after(datetime.utcnow() + timedelta(days=365))
#         # ---- LEAF EXTENSIONS – **none** of them critical -------------------
#         # .add_extension(
#         #     x509.BasicConstraints(ca=False, path_length=None), critical=False
#         # )
#         # .add_extension(
#         #     x509.KeyUsage(
#         #         digital_signature=True,
#         #         key_encipherment=False,
#         #         content_commitment=False,
#         #         data_encipherment=False,
#         #         key_agreement=False,
#         #         key_cert_sign=False,
#         #         crl_sign=False,
#         #         encipher_only=False,
#         #         decipher_only=False,
#         #     ),
#         #     critical=False,
#         # )
#         # .add_extension(
#         #     x509.ExtendedKeyUsage([EKU.SERVER_AUTH]), critical=False
#         # )
#         .add_extension(
#             x509.SubjectAlternativeName(sans), critical=False
#         )
#         .sign(priv, algorithm=None)
#     )
#
#     return (
#         priv.private_bytes(
#             serialization.Encoding.PEM,
#             serialization.PrivateFormat.PKCS8,
#             serialization.NoEncryption(),
#         ),
#         cert.public_bytes(serialization.Encoding.PEM),
#     )
#
#
# def write_cert(pk_pem, pk_file, cert_pem, cert_file):
#
#     with open(pk_file, 'wb') as f:
#         f.write(pk_pem)
#
#     with open(cert_file, 'wb') as f:
#         f.write(cert_pem)

from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID as EKU, NameOID
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from ipaddress import ip_address
from datetime import datetime, timedelta

from cryptography import x509
from cryptography.x509.oid import NameOID

from pyjamaz.utils import quic_peer_id


def generate_cert(keys, ips: str):
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)

    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
    ])
    issuer = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"rcgen self signed cert"),
    ])
    serial_numer = 76354585232599687591316365089471291226684720524
    not_valid_before = datetime(1975, 1, 1, 0, 0)
    not_valid_after = datetime(4096, 1, 1, 0, 0)
    peer_id = quic_peer_id(keys.ed25519.public_key)
    #print(peer_id)
    ext = x509.SubjectAlternativeName(x509.GeneralNames([x509.DNSName(peer_id)]))

    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(priv.public_key())
        .serial_number(serial_numer)
        .not_valid_before(not_valid_before)
        .not_valid_after(not_valid_after)
        .add_extension(x509.SubjectAlternativeName(
            x509.GeneralNames(ext)), critical=False)
    )

    cert = builder.sign(private_key=priv, algorithm=None)  # Note: Ed25519 = algorithm None

    #der_bytes = cert.public_bytes(serialization.Encoding.DER)
    #pem_bytes = cert.public_bytes(serialization.Encoding.PEM)
    # with open("clone2.pem", "wb") as f:
    #     f.write(pem_bytes)

    return (
        priv.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ),
        cert.public_bytes(serialization.Encoding.PEM),
    )


def write_cert(pk_pem, pk_file, cert_pem, cert_file):

    with open(pk_file, 'wb') as f:
        f.write(pk_pem)

    with open(cert_file, 'wb') as f:
        f.write(cert_pem)


def read_cert_public_key(cert_file: str) -> bytes:
    with open(cert_file, "rb") as f:
        cert_pem = f.read()

    cert = x509.load_pem_x509_certificate(cert_pem)
    public_key = cert.public_key()
    try:
        return public_key.public_bytes_raw()
    except AttributeError:
        return public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw,
        )
