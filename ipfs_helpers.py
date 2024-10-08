import hashlib
from typing import Dict, Any, Tuple, List
from multibase import encode as multibase_encode, decode as multibase_decode

# Constants
CODEC_RAW = 0x55
CODEC_DAG_PB = 0x70

def compute_hash(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def cid_to_string(cid: bytes) -> str:
    return multibase_encode('base32', cid).decode()

def string_to_cid(string: str) -> bytes:
    return multibase_decode(string)

def pack_cid(cid_data: Dict[str, Any]) -> bytes:
    version = cid_data.get('version', 1)
    codec = cid_data.get('codec', CODEC_RAW)
    hash_type = cid_data.get('hashType', 0x12)
    hash_ = cid_data['hash']
    
    if version == 0:
        return b'\x12\x20' + hash_
    
    return bytes([version, codec, hash_type, len(hash_)]) + hash_

def read_varint(data: bytes, offset: int) -> Tuple[int, int]:
    value = 0
    shift = 0
    while True:
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7f) << shift
        if byte < 0x80:
            return value, offset
        shift += 7

def write_varint(value: int) -> bytes:
    buffer = bytearray()
    while True:
        byte = value & 0x7f
        value >>= 7
        if value == 0:
            buffer.append(byte)
            return bytes(buffer)
        buffer.append(byte | 0x80)

def read_proto(data: bytes, process_field):
    result = {}
    offset = 0
    while offset < len(data):
        field_tag, offset = read_varint(data, offset)
        field_number = field_tag >> 3
        wire_type = field_tag & 0x7
        if wire_type == 0:  # Varint
            value, offset = read_varint(data, offset)
        elif wire_type == 1:  # 64-bit
            value = int.from_bytes(data[offset:offset+8], 'little')
            offset += 8
        elif wire_type == 2:  # Length-delimited
            length, offset = read_varint(data, offset)
            value = data[offset:offset+length]
            offset += length
        else:
            raise ValueError(f"Unsupported wire type: {wire_type}")
        process_field(field_number, value, result)
    return result

def read_pb_link(data: bytes) -> Dict[str, Any]:
    def process_field(field_number, value, result):
        if field_number == 1:
            result['cid'] = value
        elif field_number == 2:
            result['name'] = value.decode('utf-8')
        elif field_number == 3:
            result['size'] = value
    return read_proto(data, process_field)

def read_pb_node(data: bytes) -> Dict[str, Any]:
    def process_field(field_number, value, result):
        if field_number == 1:
            result['data'] = value
        elif field_number == 2:
            result.setdefault('links', []).append(read_pb_link(value))
    return read_proto(data, process_field)

def write_pb_node(node: Dict[str, Any]) -> bytes:
    def write_pb_link(link):
        return (
            write_varint((1 << 3) | 2) + write_varint(len(link['cid'])) + link['cid'] +
            write_varint((2 << 3) | 2) + write_varint(len(link['name'])) + link['name'].encode('utf-8') +
            write_varint((3 << 3) | 0) + write_varint(link['size'])
        )

    result = b''
    for link in node.get('links', []):
        result += write_varint((2 << 3) | 2) + write_varint(len(write_pb_link(link))) + write_pb_link(link)
    if 'data' in node:
        result += write_varint((1 << 3) | 2) + write_varint(len(node['data'])) + node['data']
    return result

def read_unixfs_data(data: bytes) -> Dict[str, Any]:
    def process_field(field_number, value, result):
        if field_number == 1:
            result['type'] = value
        elif field_number == 2:
            result['data'] = value
        elif field_number == 3:
            result['fileSize'] = value
    return read_proto(data, process_field)

def read_cid(data: bytes) -> Dict[str, Any]:
    if data[0] == 0x12 and data[1] == 0x20:
        return {
            'version': 0,
            'codec': CODEC_DAG_PB,
            'hashType': 0x12,
            'hash': data[2:34]
        }
    
    version = data[0]
    if version != 1:
        raise ValueError(f"Unsupported CID version: {version}")
    
    codec = data[1]
    hash_type = data[2]
    if hash_type != 0x12:
        raise ValueError(f"Unsupported hash type: {hash_type}. Only SHA-256 is supported.")
    
    hash_size = data[3]
    if hash_size != 32:
        raise ValueError("Wrong SHA-256 hash size")
    
    hash_ = data[4:36]
    return {'version': version, 'codec': codec, 'hashType': hash_type, 'hash': hash_}

def validate_block(cid: bytes, block_data: bytes):
    cid_data = read_cid(cid)
    computed_hash = hashlib.sha256(block_data).digest()
    if cid_data['hash'] != computed_hash:
        raise ValueError("Hash mismatch")

def read_car(file_data: bytes) -> List[Dict[str, Any]]:
    blocks = []
    offset = 0
    while offset < len(file_data):
        block_length, data_offset = read_varint(file_data, offset)
        data = file_data[data_offset:data_offset + block_length]
        blocks.append({
            'blockLength': block_length,
            'data': data,
            'startOffset': offset
        })
        offset = data_offset + block_length
    return blocks

def read_block(data: bytes) -> Dict[str, Any]:
    cid_data = read_cid(data)
    cid = pack_cid(cid_data)
    block_data = data[len(cid):]
    
    if cid_data['codec'] == CODEC_RAW:
        return {'cid': cid, 'codec': CODEC_RAW, 'data': block_data}
    elif cid_data['codec'] == CODEC_DAG_PB:
        try:
            node = read_pb_node(block_data)
            return {'cid': cid, 'codec': CODEC_DAG_PB, 'data': block_data, 'node': node}
        except Exception as e:
            raise ValueError(f"Error reading PBNode: {str(e)}")
    else:
        raise ValueError(f"Unsupported multicodec: {cid_data['codec']}")
