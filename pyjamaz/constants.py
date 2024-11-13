WELL_KNOWN_STORAGE_KEYS = {
    # Authorizer pool
    1: int(1).to_bytes().ljust(32, b'\x00'),
    # Authorizer queue
    2: int(2).to_bytes().ljust(32, b'\x00'),
    # Recent blocks
    3: int(3).to_bytes().ljust(32, b'\x00'),
    # Safrole
    4: int(4).to_bytes().ljust(32, b'\x00'),
    # Disputes
    5: int(5).to_bytes().ljust(32, b'\x00'),
    # Entropy
    6: int(6).to_bytes().ljust(32, b'\x00'),
    # Validator queue
    7: int(7).to_bytes().ljust(32, b'\x00'),
    # Validator pool
    8: int(8).to_bytes().ljust(32, b'\x00'),
    # Validator archive
    9: int(9).to_bytes().ljust(32, b'\x00'),
    # Assurances
    10: int(10).to_bytes().ljust(32, b'\x00'),
    # Timeslot
    11: int(11).to_bytes().ljust(32, b'\x00'),
    # Privileged services
    12: int(12).to_bytes().ljust(32, b'\x00'),
    # Statistics
    13: int(13).to_bytes().ljust(32, b'\x00'),
}
