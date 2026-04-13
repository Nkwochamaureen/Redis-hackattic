import base64
import requests
import os
import struct
import struct
from dotenv import load_dotenv

load_dotenv()
# Configuration
TOKEN = os.getenv("ACCESS_TOKEN")
if not TOKEN:
    raise ValueError("ACCESS_TOKEN not found in .env file! Please check your file.")
PROBLEM_URL = f"https://hackattic.com/challenges/the_redis_one/problem?access_token={TOKEN}"
SOLVE_URL = f"https://hackattic.com/challenges/the_redis_one/solve?access_token={TOKEN}"

class RDBParser:
    def __init__(self, data):
        self.data = data
        self.pos = 0
        
    def read_bytes(self, n):
        res = self.data[self.pos : self.pos + n]
        self.pos += n
        return res

    def read_uint8(self):
        return self.read_bytes(1)[0]

    def read_length(self):
        """Implements the Redis Length Encoding logic."""
        b = self.read_uint8()
        encoding = (b & 0xC0) >> 6
        
        if encoding == 0: # 00: 6-bit length
            return b & 0x3F, False
        elif encoding == 1: # 01: 14-bit length
            next_byte = self.read_uint8()
            return ((b & 0x3F) << 8) | next_byte, False
        elif encoding == 2: # 10: 32-bit length
            return struct.unpack('>I', self.read_bytes(4))[0], False
        elif encoding == 3: # 11: Special (Integer as string)
            return b & 0x3F, True

    def read_string(self):
        """Reads a Redis-encoded string."""
        length, is_special = self.read_length()
        if is_special:
            # Special cases: Integer encoded as 1, 2, or 4 bytes
            if length == 0: return str(struct.unpack('<b', self.read_bytes(1))[0])
            if length == 1: return str(struct.unpack('<h', self.read_bytes(2))[0])
            if length == 2: return str(struct.unpack('<i', self.read_bytes(4))[0])
            return "" # Compressed strings (LZF) not handled for simplicity here
        return self.read_bytes(length).decode('utf-8', errors='ignore')

def solve():
    # 1. Fetch Problem
    resp = requests.get(PROBLEM_URL).json()
    rdb_data = bytearray(base64.b64decode(resp['rdb']))
    target_key = resp['requirements']['check_type_of']
    
    # 2. Heal Header
    rdb_data[:9] = b"REDIS0007"
    
    parser = RDBParser(rdb_data)
    parser.pos = 9 # Skip the header
    
    # State tracking
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

    # 3. Main Loop: Iterate through Opcodes
    while parser.pos < len(rdb_data):
        op = parser.read_uint8()
        
        if op == 0xFF: # EOF
            break
        elif op == 0xFE: # SELECT DB
            db_idx, _ = parser.read_length()
            seen_dbs.add(db_idx)
        elif op == 0xFB: # RESIZE DB
            parser.read_length() # Skip hash table size
            parser.read_length() # Skip expire hash table size
        elif op == 0xFA: # AUX Fields (Metadata)
            parser.read_string() # name
            parser.read_string() # value
        elif op == 0xFD: # EXPIRE SECONDS
            last_expiry = struct.unpack('<I', parser.read_bytes(4))[0] * 1000
        elif op == 0xFC: # EXPIRE MILLIS
            last_expiry = struct.unpack('<Q', parser.read_bytes(8))[0]
        else:
            # This is a Key-Value pair! 
            # 'op' here is actually the Value Type
            val_type = type_mapping.get(op, "unknown")
            key_name = parser.read_string()
            
            # The value part: 
            # For simplicity, if it's a 'string' type, read it. 
            # If it's a collection, you might need to skip its elements.
            if op == 0: # String
                val_data = parser.read_string()
            else:
                # For this challenge, non-string types usually don't contain the emoji.
                # If they do, we'd need to parse the specific collection structure.
                val_data = "complex_type" 
                # (Logic to skip complex types would go here)

            # --- Check requirements ---
            
            # 1. Is it the emoji key? (Non-ASCII characters)
            if any(ord(c) > 127 for c in key_name):
                results["emoji_key_value"] = val_data
            
            # 2. Is it the key we need to type check?
            if key_name == target_key:
                results[target_key] = val_type
            
            # 3. Did it have an expiry?
            if last_expiry:
                results["expiry_millis"] = last_expiry
                last_expiry = None # Reset for next key

    results["db_count"] = len(seen_dbs)
    
    # 4. Submit
    print("Found Results:", results)
    # final_resp = requests.post(SOLVE_URL, json=results)
    # print(final_resp.json())

if __name__ == "__main__":
    solve()