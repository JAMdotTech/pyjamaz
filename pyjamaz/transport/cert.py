"""JAMNP-S e0b7d291 Ed25519 transport identities."""

from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.x509.oid import NameOID, SignatureAlgorithmOID

from pyjamaz.utils import quic_peer_id


def generate_cert(keys, ips: str, alternative_name: str):
    # JAMNP-S v1: the only SAN is the DNS name derived from the public key.
    # Keep ips in this existing CLI interface; IP SANs are no longer permitted.
    private = ed25519.Ed25519PrivateKey.from_private_bytes(keys.ed25519.private_key)
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if alternative_name != quic_peer_id(public):
        raise ValueError("certificate name does not match the Ed25519 key")
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "jamnps-node")])
    now = datetime.now(timezone.utc)
    certificate = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
                   .public_key(private.public_key()).serial_number(x509.random_serial_number())
                   .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=365))
                   .add_extension(x509.SubjectAlternativeName([x509.DNSName(alternative_name)]), critical=False)
                   .sign(private, algorithm=None))
    return (private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()),
            certificate.public_bytes(serialization.Encoding.PEM))


def validate_peer_certificate(certificate: x509.Certificate, expected_key: bytes | None = None) -> bytes:
    """Check the v1 identity; TLS separately verifies possession of the key."""
    if certificate is None or not isinstance(certificate.public_key(), ed25519.Ed25519PublicKey):
        raise ValueError("peer did not present an Ed25519 certificate")
    if certificate.signature_algorithm_oid != SignatureAlgorithmOID.ED25519:
        raise ValueError("peer certificate is not signed with Ed25519")
    public = certificate.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    if expected_key is not None and public != expected_key:
        raise ValueError("peer certificate does not match the expected validator")
    try:
        names = list(certificate.extensions.get_extension_for_class(x509.SubjectAlternativeName).value)
    except x509.ExtensionNotFound as exc:
        raise ValueError("peer certificate has no subject alternative name") from exc
    if len(names) != 1 or not isinstance(names[0], x509.DNSName) or names[0].value != quic_peer_id(public):
        raise ValueError("peer certificate has an invalid JAMNP-S subject alternative name")
    return public


def write_cert(pk_pem, pk_file, cert_pem, cert_file):
    with open(pk_file, "wb") as file:
        file.write(pk_pem)
    with open(cert_file, "wb") as file:
        file.write(cert_pem)
