# Redis RDB Binary Parser & Data Extractor

## 📌 Project Overview

This project is a high-performance binary parser built to interact with Redis RDB (Redis Database) snapshots. The goal was to programmatically fetch a raw, base64-encoded RDB dump from an API, "heal" a corrupted binary header, and traverse the byte stream to extract specific metadata without using standard Redis tools.

This challenge mimics real-world Cloud Disaster Recovery scenarios where an engineer must recover data from a corrupted backup or perform offline analysis of database snapshots for cost and performance optimization.

## 🛠️ Technical Challenges & Solutions

1. **Binary Header "Healing"**  
   The RDB snapshots provided were intentionally tampered with by corrupting the "Magic Bytes" (the first 9 bytes of the file).  
   **Solution:** I implemented a fix that manually overwrites the corrupted header with a valid `REDIS0007` signature, allowing the binary stream to be processed by custom logic.

2. **Variable-Length Encoding Logic**  
   Redis saves space by using a complex length-encoding scheme where the first two bits of a byte determine how many subsequent bytes represent a length or a special integer type.  
   **Solution:** Built a bit-masking logic to decode 6-bit, 14-bit, and 32-bit lengths, ensuring the parser never "loses its place" in the stream.

3. **State-Machine Byte Parsing**  
   The parser functions as a state machine, walking through the binary data and responding to specific opcodes:
   - `0xFE`: Database Selector (used to track the total `db_count`)
   - `0xFD` & `0xFC`: Expiry timestamps in Seconds/Milliseconds
   - `0xFF`: End of File marker

4. **Handling Optimized Data Blobs (Ziplists / Intsets)**  
   Modern Redis versions store collections (Sets, Lists, Hashes) as single "encoded blobs" rather than individual strings to save RAM.  
   **Solution:** Developed a robust `skip_value` function to handle both "Old Style" collections and "Modern" encoded types (`Types 9-14`), preventing buffer overruns and `IndexError`s.

## 🚀 Key Features

- **Emoji Detection:** Scans for non-ASCII key names in the binary stream to identify and extract unique emoji-based keys.
- **TTL Extraction:** Captures and converts Unix timestamps from binary to human-readable / millisecond formats.
- **Dynamic Key Typing:** Identifies the internal Redis data type (`String`, `Hash`, `Set`, etc.) for any specific key requested by the requirements.
- **Cloud-Ready Security:** Implements `.env` project isolation to handle API access tokens securely.

## 🧰 Tools & Libraries

- **Language:** Python 3.13
- **Libraries:**
  - `struct` — For C-style binary data conversion
  - `requests` — For API interaction
  - `python-dotenv` — For secure environment variable management
  - `base64` — For decoding the RDB transport format

## 📖 How to Run

1. Clone the repository.
2. Create a `.venv` and install requirements:
   ```bash
   pip install -r requirements.txt
   ```
3. Create a `.env` file and add your `ACCESS_TOKEN`.
4. Run the solution:
   ```bash
   python solution.py
   ```