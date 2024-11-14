import datetime
import argparse

from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography import x509
from cryptography.hazmat.primitives import serialization
from cryptography.x509.oid import NameOID

from ipaddress import ip_address


def generate_cert(
        key,
        ips,
        domains,
        country,
        state,
        city,
        organization,
        website,
):

    # Replace this with your actual 32-byte raw private key bytes
    raw_private_key_bytes = bytes.fromhex(key)

    # Create an Ed25519 private key from raw bytes
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(raw_private_key_bytes)

    # Generate a public key
    public_key = private_key.public_key()

    origin_list = [x509.IPAddress(ip_address(ip.strip())) for ip in ips.split(",")]
    origin_list += [x509.DNSName(domain.strip()) for domain in domains.split(",")]
    # Encode the public key in base32 using the specified alphabet
    #public_bytes = public_key.public_bytes(
    #    encoding=serialization.Encoding.Raw,
    #    format=serialization.PublicFormat.Raw
    #)
    #public_key_b32 = base64.b32encode(public_bytes).lower().decode('ascii').strip('=')
    #origin_list += [x509.DNSName('e' + public_key_b32)]

    # Build the subject and issuer name
    name = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, country),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, state),
        x509.NameAttribute(NameOID.LOCALITY_NAME, city),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization),
        x509.NameAttribute(NameOID.COMMON_NAME, website),
    ])

    # Build the certificate
    certificate = x509.CertificateBuilder().subject_name(
        name
    ).issuer_name(
        name  # Self-signed
    ).public_key(
        public_key
    ).serial_number(
        x509.random_serial_number()
    ).not_valid_before(
        datetime.datetime.utcnow()
    ).not_valid_after(
        # Certificate valid for 1 year
        datetime.datetime.utcnow() + datetime.timedelta(days=365)
    ).add_extension(
        x509.BasicConstraints(ca=True, path_length=None), critical=True,
    ).add_extension(
        x509.SubjectAlternativeName(origin_list),
        # x509.SubjectAlternativeName([
        #     x509.DNSName(u"localhost"),
        #     x509.IPAddress(ip_address(u"127.0.0.1")),
        # ]),
        critical=False,
    ).sign(
        private_key,
        algorithm=None
    )

    # Serialize the private key and certificate to PEM format
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption()
    )

    certificate_pem = certificate.public_bytes(serialization.Encoding.PEM)

    return (private_key_pem, certificate_pem)


def write_cert(pk_pem, pk_file, cert_pem, cert_file):

    with open(pk_file, 'wb') as f:
        f.write(pk_pem)

    with open(cert_file, 'wb') as f:
        f.write(cert_pem)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convert ")
    parser.add_argument(
        "--key",
        type=str,
        default="0000000000000000000000000000000000000000000000000000000000000000",
        help="Private ed25519 key to create certificate for",
    )
    parser.add_argument(
        "--country",
        type=str,
        default="US",
        help="Issuing country",
    )
    parser.add_argument(
        "--state",
        type=str,
        default="test state",
        help="Issuing state or province",
    )
    parser.add_argument(
        "--city",
        type=str,
        default="test city",
        help="Issuing city",
    )
    parser.add_argument(
        "--organization",
        type=str,
        default="test",
        help="Issuing organization",
    )
    parser.add_argument(
        "--website",
        type=str,
        default="test.com",
        help="Issuing website",
    )
    parser.add_argument(
        "--domains",
        type=str,
        default="localhost",
        help="Comma sperated list of allowed domains for this certificate",
    )
    parser.add_argument(
        "--ips",
        type=str,
        default="127.0.0.1",
        help="Comma sperated list of allowed IP addresses for this certificate",
    )
    parser.add_argument(
        "--pk_file",
        type=str,
        default="peer.key",
        help="Filename to write out the generated private key PEM file",
    )
    parser.add_argument(
        "--cert_file",
        type=str,
        default="peer.crt",
        help="Filename to write out the generated certificate PEM file",
    )

    args = parser.parse_args()

    pk_pem, cert_pem = generate_cert(
        args.key,
        args.ips,
        args.domains,
        args.country,
        args.state,
        args.city,
        args.organization,
        args.website,
    )

    write_cert(pk_pem, args.pk_file, cert_pem, args.cert_file)

    print("Private key and certificate have been generated and saved.")
