
import zlib


PACKET_TYPE_MESSAGE = 1
PACKET_TYPE_COMMAND = 2
PACKET_TYPE_RESULT = 3
PACKET_TYPE_CONTROL = 4


def encode_packet(pkt_type: int, payload: str) -> str:
    checksum = f"{zlib.crc32(payload.encode()) & 0xffffffff:08x}"
    return f"{pkt_type}|{checksum}|{payload}"

def decode_packet(raw: str):
    try:
        parts = raw.strip().split("|", 2)
        if len(parts) != 3:
            return None, None, None
        pkt_type = int(parts[0])
        checksum = parts[1]
        payload = parts[2]
        expected_checksum = f"{zlib.crc32(payload.encode()) & 0xffffffff:08x}"
        if expected_checksum != checksum: 
            return None, None, None  # failed checksum
        return pkt_type, checksum, payload
    except Exception:
        return None, None, None
    
def send_packet_message(wfile, pkt_type: int, payload: str):
    """
    Encode and send a structured message through the given wfile.
    """
    try:
        msg = encode_packet(pkt_type, payload)
        wfile.write(msg + '\n')
        wfile.flush()
    except Exception as e:
        print(f"[WARN] Failed to send message: {e}")
        raise
