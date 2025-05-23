from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID as EKU, NameOID
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
from ipaddress import ip_address
from datetime import datetime, timedelta


def generate_cert(keys, ips: str, alternative_name: str):
    priv = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)

    sans = [x509.IPAddress(ip_address(ip.strip()))
            for ip in ips.split(",") if ip.strip()]
    sans.append(x509.DNSName(alternative_name))

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "jamnps-node")])

    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(priv.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.utcnow() - timedelta(minutes=5))
        .not_valid_after(datetime.utcnow() + timedelta(days=365))
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None), critical=True
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,       # <- still present
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([EKU.SERVER_AUTH]), critical=False
        )
        .add_extension(
            x509.SubjectAlternativeName(sans), critical=False
        )
        .sign(priv, algorithm=None)
    )

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
