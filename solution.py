import os
import base64
import requests
import struct
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("ACCESS_TOKEN").strip()
PROBLEM_URL = f"https://hackattic.com/challenges/the_redis_one/problem?access_token={TOKEN}"
SOLVE_URL = f"https://hackattic.com/challenges/the_redis_one/solve?access_token={TOKEN}"

class RDBParser:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        
    def read_bytes(self, n):
        if self.pos + n > len(self.data):
            # Prevent crashing if we hit the end early
            n = len(self.data) - self.pos
        res = self.data[self.pos : self.pos + n]
        self.pos += n
        return res

    def read_uint8(self):
        b = self.read_bytes(1)
        return b[0] if b else 0xFF

    def read_length(self):
        b = self.read_uint8()
        if b == 0xFF: return 0, False
        encoding = (b & 0xC0) >> 6
        if encoding == 0: return b & 0x3F, False
        if encoding == 1: return ((b & 0x3F) << 8) | self.read_uint8(), False
        if encoding == 2: return struct.unpack('>I', self.read_bytes(4))[0], False
        if encoding == 3: return b & 0x3F, True
        return 0, False

    def read_string(self):
        length, is_special = self.read_length()
        if is_special:
            # Special integer encodings
            if length == 0: return str(struct.unpack('<b', self.read_bytes(1))[0])
            if length == 1: return str(struct.unpack('<h', self.read_bytes(2))[0])
            if length == 2: return str(struct.unpack('<i', self.read_bytes(4))[0])
            return "" # LZF or other special types
        return self.read_bytes(length).decode('utf-8', errors='ignore')

    def skip_value(self, val_type):
        """Correctly handles both standard collections and encoded blobs."""
        # Type 0 (String) AND Types 9-14 (Encoded blobs: Ziplist, Intset, etc.)
        # In RDB, these are all stored as a single string-encoded block.
        if val_type == 0 or (val_type >= 9 and val_type <= 14):
            return self.read_string()
        
        # Types 1, 2, 3, 4 are 'Old Style' collections that need looping
        if val_type in [1, 2, 3, 4]:
            count, _ = self.read_length()
            if val_type == 4: count *= 2 # Hash pairs
            for _ in range(count):
                self.read_string()
                if val_type == 3: self.read_string() # ZSet scores
        return "complex_type"

def solve():
    print("Fetching problem...")
    resp = requests.get(PROBLEM_URL).json()
    rdb_data = bytearray(base64.b64decode(resp['rdb']))
    target_key = resp['requirements']['check_type_of']
    
    # Heal Header
    rdb_data[:9] = b"REDIS0007"
    
    parser = RDBParser(rdb_data)
    parser.pos = 9
    
    results = {
        "db_count": 0,
        "emoji_key_value": None,
        "expiry_millis": None,
        target_key: None
    }
    
    type_mapping = {
        0: "string", 1: "list", 2: "set", 3: "zset", 4: "hash",
        9: "hash", 10: "list", 11: "set", 12: "zset", 13: "hash", 14: "list"
    }

    last_expiry = None
    seen_dbs = set()

    while parser.pos < len(rdb_data):
        op = parser.read_uint8()
        
        if op == 0xFF: break
        elif op == 0xFE: # Select DB
            db_idx, _ = parser.read_length()
            seen_dbs.add(db_idx)
        elif op == 0xFB: # Resize DB
            parser.read_length(); parser.read_length()
        elif op == 0xFA: # Aux
            parser.read_string(); parser.read_string()
        elif op == 0xFD: # Expire Sec
            last_expiry = struct.unpack('<I', parser.read_bytes(4))[0] * 1000
        elif op == 0xFC: # Expire Millis
            last_expiry = struct.unpack('<Q', parser.read_bytes(8))[0]
        else:
            val_type_name = type_mapping.get(op, "unknown")
            key_name = parser.read_string()
            value_data = parser.skip_value(op)
            
            if any(ord(c) > 127 for c in key_name):
                results["emoji_key_value"] = value_data
            if key_name == target_key:
                results[target_key] = val_type_name
            if last_expiry:
                results["expiry_millis"] = last_expiry
                last_expiry = None

    results["db_count"] = len(seen_dbs)
    
    print("Found Results:", results)
    final_resp = requests.post(SOLVE_URL, json=results)
    print("Hackattic Feedback:", final_resp.text)

if __name__ == "__main__":
    solve()