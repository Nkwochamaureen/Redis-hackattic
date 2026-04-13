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
        res = self.data[self.pos : self.pos + n]
        self.pos += n
        return res

    def read_uint8(self):
        return self.read_bytes(1)[0]

    def read_length(self):
        b = self.read_uint8()
        encoding = (b & 0xC0) >> 6
        if encoding == 0: return b & 0x3F, False
        if encoding == 1: return ((b & 0x3F) << 8) | self.read_uint8(), False
        if encoding == 2: return struct.unpack('>I', self.read_bytes(4))[0], False
        if encoding == 3: return b & 0x3F, True
        return 0, False

    def read_string(self):
        length, is_special = self.read_length()
        if is_special:
            if length == 0: return str(struct.unpack('<b', self.read_bytes(1))[0])
            if length == 1: return str(struct.unpack('<h', self.read_bytes(2))[0])
            if length == 2: return str(struct.unpack('<i', self.read_bytes(4))[0])
            return ""
        return self.read_bytes(length).decode('utf-8', errors='ignore')

    def skip_value(self, val_type):
        """Important: Moves the pointer past the value data and returns it."""
        if val_type == 0: # String
            return self.read_string()
        
        # For Lists, Sets, and Hashes:
        count, _ = self.read_length()
        
        # If it's a Hash, there are 'count' pairs (key and value)
        if val_type in [4, 9, 13]: 
            count *= 2
            
        for _ in range(count):
            self.read_string()
            # Sorted Sets have a score byte after each member
            if val_type in [3, 12]:
                self.read_uint8() 
        return "complex_type"

def solve():
    # 1. Fetch
    print("Fetching problem...")
    resp = requests.get(PROBLEM_URL).json()
    rdb_data = bytearray(base64.b64decode(resp['rdb']))
    target_key = resp['requirements']['check_type_of']
    
    # 2. Heal
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

    # 3. Parse Loop
    while parser.pos < len(rdb_data):
        op = parser.read_uint8()
        
        if op == 0xFF: # End of File
            break
        elif op == 0xFE: # Select DB
            db_idx, _ = parser.read_length()
            seen_dbs.add(db_idx)
        elif op == 0xFB: # Resize DB
            parser.read_length()
            parser.read_length()
        elif op == 0xFA: # Aux Fields
            parser.read_string()
            parser.read_string()
        elif op == 0xFD: # Expiry Seconds
            last_expiry = struct.unpack('<I', parser.read_bytes(4))[0] * 1000
        elif op == 0xFC: # Expiry Millis
            last_expiry = struct.unpack('<Q', parser.read_bytes(8))[0]
        else:
            # It's a key!
            val_type_name = type_mapping.get(op, "unknown")
            key_name = parser.read_string()
            
            # Use skip_value to jump past the value and get the data
            value_data = parser.skip_value(op)
            
            # Is it the emoji key? (non-ascii)
            if any(ord(c) > 127 for c in key_name):
                results["emoji_key_value"] = value_data
            
            # Is it the type-check key?
            if key_name == target_key:
                results[target_key] = val_type_name
            
            # Did it have an expiry?
            if last_expiry:
                results["expiry_millis"] = last_expiry
                last_expiry = None # Reset for next key

    results["db_count"] = len(seen_dbs)
    
    # 4. Submit
    print("Found Results:", results)
    final_resp = requests.post(SOLVE_URL, json=results)
    print("Hackattic Feedback:", final_resp.text)

if __name__ == "__main__":
    solve()