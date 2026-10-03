# steganography — payloads (verbatim from kali-claw)

# Steganography Payloads

> This file is a companion to `SKILL.md`, containing all steganography commands and payloads organized by tool and technique.

---

## 1. Format Identification and Initial Triage

### File Type Verification

```bash
# Determine true file type regardless of extension
file suspicious_image.jpg

# Inspect magic bytes directly
xxd suspicious_image.jpg | head -5

# Common magic bytes reference:
# JPEG: FF D8 FF
# PNG:  89 50 4E 47 0D 0A 1A 0A
# BMP:  42 4D
# GIF:  47 49 46 38
# WAV:  52 49 46 46 ... 57 41 56 45
# PDF:  25 50 44 46

# Check for file type mismatch (common CTF trick)
python3 -c "
import magic
real_type = magic.from_file('suspicious_image.jpg')
print(f'Real type: {real_type}')
"

# Calculate file hash for integrity tracking
md5sum suspicious_image.jpg
sha256sum suspicious_image.jpg
```

### Size and Entropy Analysis

```bash
# Check file size and compare to expected size for resolution
ls -la suspicious_image.jpg
identify suspicious_image.jpg  # Requires ImageMagick

# Entropy analysis: high entropy may indicate hidden encrypted data
python3 -c "
import math
from collections import Counter
with open('suspicious_image.jpg', 'rb') as f:
    data = f.read()
freq = Counter(data)
entropy = -sum((c/len(data)) * math.log2(c/len(data)) for c in freq.values())
print(f'File entropy: {entropy:.4f} bits/byte (max=8.0)')
print(f'File size: {len(data)} bytes')
if entropy > 7.9:
    print('HIGH entropy - may contain encrypted/compressed hidden data')
"

# Quick strings extraction for embedded text
strings -n 8 suspicious_image.jpg | head -30
strings -n 8 suspicious_image.jpg | grep -iE 'flag|ctf|password|key'
```

---

## 2. Steghide - JPEG/BMP/WAV Embedding and Extraction

### Embedding Data with Steghide

```bash
# Basic embedding into JPEG
steghide embed -cf carrier.jpg -ef secret.txt

# Embed with specific passphrase
steghide embed -cf carrier.jpg -ef secret.txt -p "mypassword"

# Embed with maximum compression
steghide embed -cf carrier.jpg -ef secret.txt -z 9

# Embed without compression (faster, larger capacity)
steghide embed -cf carrier.jpg -ef secret.txt -z 0

# Embed into BMP file
steghide embed -cf carrier.bmp -ef secret.txt

# Embed into WAV audio file
steghide embed -cf carrier.wav -ef secret.txt

# Embed with custom passphrase and specify output file
steghide embed -cf original.jpg -ef payload.txt -p "secret123" -sf output.jpg

# Check embedding capacity of a carrier file
steghide info carrier.jpg
# This shows how many bytes can be embedded
```

### Extracting Data with Steghide

```bash
# Basic extraction (will prompt for passphrase)
steghide extract -sf carrier.jpg

# Extract with known passphrase
steghide extract -sf carrier.jpg -p "mypassword"

# Extract with empty passphrase (common in CTF)
steghide extract -sf carrier.jpg -p ""

# Extract and specify output filename
steghide extract -sf carrier.jpg -p "password" -f extracted_data.txt

# Force extraction even if integrity check fails
steghide extract -sf carrier.jpg -p "password" -f output.txt --force

# Get info about embedded data without extracting
steghide info carrier.jpg
```

### Steghide Detection and Analysis

```bash
# Check if file contains steghide embedding
steghide info carrier.jpg
# If embedding exists, shows: embedded file name, size, compression

# Try extraction with empty passphrase first (common CTF default)
steghide extract -sf carrier.jpg -p ""

# Batch extraction attempt with common passphrases
for pass in "" "password" "123456" "secret" "hidden" "steg"; do
  echo "Trying passphrase: '$pass'"
  steghide extract -sf carrier.jpg -p "$pass" -f extracted.tmp 2>/dev/null && \
    echo "SUCCESS with passphrase: '$pass'" && break
  rm -f extracted.tmp 2>/dev/null
done
```

---

## 3. Stegcracker - Steghide Password Recovery

### Basic Brute Force

```bash
# Basic wordlist attack against steghide-protected file
stegcracker carrier.jpg /usr/share/wordlists/rockyou.txt

# Use SecLists steganography-specific wordlists
stegcracker carrier.jpg /usr/share/seclists/Passwords/Common-Credentials/best1050.txt

# Custom wordlist attack
stegcracker carrier.jpg custom_wordlist.txt

# With extension hint (speeds up extraction)
stegcracker carrier.jpg rockyou.txt -e txt
```

### Custom Dictionary Generation

```bash
# Generate context-specific wordlist for CTF
# Combine theme keywords with common patterns
cat > ctf_words.txt << 'EOF'
password
secret
hidden
flag
ctf
stego
steganography
EOF

# Mutate wordlist with common variations
cat ctf_words.txt | while read word; do
  echo "$word"
  echo "${word}123"
  echo "${word}!"
  echo "$(echo "$word" | tr '[:lower:]' '[:upper:]')"
  echo "${word}_hidden"
done > ctf_mutated.txt

stegcracker carrier.jpg ctf_mutated.txt
```

### Batch Password Recovery

```bash
# Try multiple wordlists in sequence
for wordlist in rockyou.txt common_passwords.txt ctf_wordlist.txt; do
  if [ -f "/usr/share/wordlists/$wordlist" ]; then
    echo "Trying $wordlist..."
    stegcracker carrier.jpg "/usr/share/wordlists/$wordlist" && break
  fi
done

# Manual brute force with steghide (fallback if stegcracker unavailable)
while IFS= read -r password; do
  if steghide extract -sf carrier.jpg -p "$password" -f extracted.tmp 2>/dev/null; then
    echo "PASSWORD FOUND: $password"
    cat extracted.tmp
    break
  fi
done < /usr/share/wordlists/rockyou.txt
```

---

## 4. zsteg - PNG/BMP LSB Analysis

### Basic Detection

```bash
# Scan all possible LSB channels
zsteg -a suspicious.png

# Scan specific bit plane (e.g., LSB of red channel)
zsteg -b 1 -o 1 suspicious.png

# Extract data from specific channel
zsteg -b 1,0,0 suspicious.png  # bit 1, red channel only

# Show all found data with offsets
zsteg -v suspicious.png

# Try all zlib-compressed streams
zsteg -a --try-zlib suspicious.png
```

### Targeted LSB Extraction

```bash
# Extract LSB from red channel, most significant bit first
zsteg -b 1,rgb,lsb,xy suspicious.png

# Extract from blue channel
zsteg -b 1,bgr,lsb,xy suspicious.png

# Extract and save to file
zsteg -a suspicious.png -o extracted.bin

# Extract with zlib decompression
zsteg -a --try-zlib suspicious.png -o decompressed.bin

# Check specific pixel ordering
zsteg -b 1,rgba,lsb,xy suspicious.png
zsteg -b 1,rgba,msb,xy suspicious.png
zsteg -b 1,rgba,lsb,yx suspicious.png
```

### BMP-Specific Analysis

```bash
# zsteg also works with BMP files
zsteg -a suspicious.bmp

# BMP often stores data in unused padding bytes
# Check for hidden content after image data
python3 -c "
import struct
with open('suspicious.bmp', 'rb') as f:
    f.seek(2)
    file_size = struct.unpack('<I', f.read(4))[0]
    f.seek(10)
    data_offset = struct.unpack('<I', f.read(4))[0]
    f.seek(0, 2)
    actual_size = f.tell()
    print(f'BMP declared size: {file_size}')
    print(f'Actual file size: {actual_size}')
    print(f'Data offset: {data_offset}')
    if actual_size > file_size:
        print(f'EXTRA DATA: {actual_size - file_size} bytes after declared EOF')
        f.seek(file_size)
        extra = f.read()
        print(f'Extra bytes preview: {extra[:100]}')
"
```

---

## 5. binwalk - Embedded File Extraction

### Signature Scanning

```bash
# Scan for embedded file signatures
binwalk suspicious.png

# Scan with detailed entropy analysis
binwalk -E suspicious.png

# Scan and extract all embedded files (recursive)
binwalk -Me suspicious.png

# Extract to specific directory
binwalk -Me suspicious.png -C /tmp/extracted/

# Scan specific file types
binwalk --signature suspicious.png

# Display all recognized signatures
binwalk --list-signatures
```

### Firmware and Binary Analysis

```bash
# Extract firmware components
binwalk -Me firmware.bin

# Extract specific offset
binwalk -dd '.*' firmware.bin

# Manual extraction at known offset
dd if=suspicious.png bs=1 skip=OFFSET of=extracted.bin

# Compare entropy across the file
binwalk -E -J suspicious.png
# Generates entropy plot image

# Recursive extraction with depth limit
binwalk -Me -depth 3 suspicious.png

# Extract only specific file types
binwalk -e --include zlib, gzip, png suspicious.png
```

### Manual Offset Extraction

```bash
# If binwalk identifies an embedded ZIP at offset 12345
dd if=suspicious.png bs=1 skip=12345 of=hidden.zip

# Extract the discovered archive
unzip hidden.zip

# If embedded PNG is found at offset
dd if=suspicious.png bs=1 skip=OFFSET of=hidden_image.png

# Compare original and extracted files
binwalk suspicious.png
# Note: use the offsets shown to extract manually

# Check for appended data after image EOF
python3 -c "
import struct
# For PNG: IEND chunk marks end
with open('suspicious.png', 'rb') as f:
    data = f.read()
    iend_pos = data.find(b'IEND')
    if iend_pos != -1:
        # IEND chunk: 4 bytes length + 4 bytes 'IEND' + 4 bytes CRC = 12 bytes after IEND
        eof = iend_pos + 8  # past IEND + CRC
        if len(data) > eof:
            extra = data[eof:]
            print(f'APPENDED DATA: {len(extra)} bytes after PNG EOF')
            print(f'Preview: {extra[:100]}')
            # Save appended data
            with open('appended.bin', 'wb') as out:
                out.write(extra)
"
```

---

## 6. foremost - File Carving

### Basic File Carving

```bash
# Carve common file types from a carrier file
foremost -i suspicious.bin -o /tmp/carved/

# Carve specific file types
foremost -t jpg,png,pdf,zip -i suspicious.bin -o /tmp/carved/

# Carve from disk image
foremost -t all -i disk_image.dd -o /tmp/carved/

# Verbose output
foremost -v -t jpg,png -i suspicious.bin -o /tmp/carved/

# Quick mode (faster, less thorough)
foremost -q -t jpg,png,pdf -i suspicious.bin -o /tmp/carved/
```

### Custom Signature Carving

```bash
# Add custom signatures to foremost.conf
# Edit /etc/foremost.conf or create local config
cat > foremost_custom.conf << 'EOF'
# Custom signature for flag files
flag x 0x666c6167 0x0a MAX 1000
# Custom signature for hidden ZIP archives
zip y 504b0304 MAX 10000000
EOF

foremost -c foremost_custom.conf -i suspicious.bin -o /tmp/carved/

# Carve and verify carved files
foremost -t jpg,png -i suspicious.bin -o /tmp/carved/
file /tmp/carved/jpg/*
file /tmp/carved/png/*
```

---

## 7. exiftool - Metadata Analysis

### Comprehensive Metadata Extraction

```bash
# Extract all metadata including duplicate tags
exiftool -a -G1 suspicious.jpg

# Extract specific metadata groups
exiftool -EXIF:All suspicious.jpg
exiftool -IPTC:All suspicious.jpg
exiftool -XMP:All suspicious.jpg
exiftool -PNG:All suspicious.png

# Extract comment and description fields (common hiding spots)
exiftool -Comment -UserComment -ImageDescription -Description suspicious.jpg

# Extract GPS coordinates (OSINT correlation)
exiftool -GPS:All suspicious.jpg

# Extract all metadata as JSON for parsing
exiftool -json suspicious.jpg > metadata.json

# Extract metadata from all files in directory
exiftool -r -a -G1 /path/to/images/
```

### Hidden Data in Metadata Fields

```bash
# Check for base64-encoded data in comments
exiftool -Comment suspicious.jpg | grep -oP '[A-Za-z0-9+/=]{20,}' | base64 -d

# Check for hex-encoded data
exiftool -Comment suspicious.jpg | grep -oP '[0-9a-fA-F]{20,}' | xxd -r -p

# Look for URLs or flags in all text metadata
exiftool -a -s suspicious.jpg | grep -iE 'flag|http|password|key|secret'

# Check file history and software tags
exiftool -Software -CreatorTool -History suspicious.jpg

# Recursive metadata extraction with text search
exiftool -r -fast2 /path/to/images/ | grep -iE 'flag\{|ctf|hidden'

# Compare metadata between original and suspected modified file
diff <(exiftool original.jpg) <(exiftool suspicious.jpg)
```

### Metadata Stripping (Defensive)

```bash
# Strip all metadata from a file
exiftool -all= clean_image.jpg

# Strip only GPS data
exiftool -GPS:all= clean_image.jpg

# Strip and overwrite original
exiftool -all= -overwrite_original clean_image.jpg

# Batch metadata stripping
exiftool -all= -r /path/to/images/
```

---

## 8. Advanced Detection Techniques

### Statistical Steganalysis (Chi-Square Test)

```python
#!/usr/bin/env python3
"""
Chi-square based steganalysis for LSB detection in BMP/PNG images.
Compares observed vs expected distribution of even/odd pixel values.
"""
from PIL import Image
import math
from collections import Counter

def chi_square_steganalysis(image_path, block_size=1000):
    """Run chi-square test on LSB distribution of image pixels."""
    img = Image.open(image_path).convert('RGB')
    pixels = list(img.getdata())

    results = []
    for start in range(0, len(pixels) - block_size, block_size):
        block = pixels[start:start + block_size]

        # Count even and odd LSBs across all channels
        even_count = 0
        odd_count = 0
        for pixel in block:
            for channel in pixel:
                if channel % 2 == 0:
                    even_count += 1
                else:
                    odd_count += 1

        total = even_count + odd_count
        expected = total / 2

        # Chi-square statistic
        chi_sq = ((even_count - expected) ** 2 / expected +
                  (odd_count - expected) ** 2 / expected)

        # Probability of embedding (higher chi_sq = more likely)
        embedding_prob = min(1.0, chi_sq / 10.0)
        results.append({
            'offset': start,
            'even': even_count,
            'odd': odd_count,
            'chi_square': chi_sq,
            'probability': embedding_prob
        })

    return results

# Usage
results = chi_square_steganalysis('suspicious.bmp')
for r in results[:10]:
    status = "SUSPICIOUS" if r['probability'] > 0.5 else "NORMAL"
    print(f"Block {r['offset']:6d}: chi_sq={r['chi_square']:.2f} prob={r['probability']:.2f} [{status}]")
```

### Visual Analysis with Bit Plane Extraction

```python
#!/usr/bin/env python3
"""
Extract individual bit planes from an image for visual inspection.
LSB steganography is visible when viewing the least significant bit plane.
"""
from PIL import Image
import sys

def extract_bit_plane(image_path, bit_position, channel=0):
    """Extract a specific bit plane from an image."""
    img = Image.open(image_path).convert('RGB')
    width, height = img.size
    output = Image.new('L', (width, height))

    for y in range(height):
        for x in range(width):
            pixel = img.getpixel((x, y))
            bit_val = (pixel[channel] >> bit_position) & 1
            output.putpixel((x, y), bit_val * 255)

    return output

# Extract LSB plane from red channel (most common LSB embedding target)
for channel_name, channel_idx in [('red', 0), ('green', 1), ('blue', 2)]:
    for bit in range(8):
        plane = extract_bit_plane('suspicious.png', bit, channel_idx)
        plane.save(f'bitplane_{channel_name}_bit{bit}.png')
        print(f'Saved: bitplane_{channel_name}_bit{bit}.png')

print('Inspect LSB planes (bit0) for patterns indicating hidden data.')
print('Random noise in LSB plane = possible steganography.')
print('Structured pattern in LSB plane = likely normal image data.')
```

### Appended Data Detection

```bash
# Check for data after declared EOF for various formats

# JPEG: data after FFD9 marker
python3 -c "
with open('suspicious.jpg', 'rb') as f:
    data = f.read()
    eoi = data.rfind(b'\xff\xd9')
    if eoi != -1 and eoi + 2 < len(data):
        extra = data[eoi + 2:]
        print(f'APPENDED DATA after JPEG EOI: {len(extra)} bytes')
        print(f'Preview: {extra[:100]}')
        with open('appended.bin', 'wb') as out:
            out.write(extra)
        print('Saved to appended.bin')
    else:
        print('No data appended after JPEG EOF marker')
"

# GIF: data after 0x3B trailer
python3 -c "
with open('suspicious.gif', 'rb') as f:
    data = f.read()
    trailer = data.rfind(b'\x3b')
    if trailer != -1 and trailer + 1 < len(data):
        extra = data[trailer + 1:]
        print(f'APPENDED DATA after GIF trailer: {len(extra)} bytes')
        print(f'Preview: {extra[:100]}')
"

# PDF: check for data before %PDF header
python3 -c "
with open('suspicious.pdf', 'rb') as f:
    data = f.read()
    pdf_start = data.find(b'%PDF')
    if pdf_start > 0:
        header_extra = data[:pdf_start]
        print(f'DATA BEFORE PDF HEADER: {pdf_start} bytes')
        print(f'Preview: {header_extra[:100]}')
"
```

---

## 9. Multi-Tool Pipeline

### Automated Triage Script

```bash
#!/bin/bash
# Automated steganography triage: run all detection tools in sequence
# Usage: ./stego_triage.sh <file>

TARGET="$1"
if [ -z "$TARGET" ]; then
    echo "Usage: $0 <file>"
    exit 1
fi

echo "=== Steganography Triage: $TARGET ==="
echo

# 1. File type identification
echo "[1] File Type Identification"
file "$TARGET"
echo

# 2. File size and hash
echo "[2] File Size and Hash"
ls -la "$TARGET"
md5sum "$TARGET"
echo

# 3. Metadata analysis
echo "[3] Metadata Analysis (exiftool)"
exiftool -a -G1 "$TARGET" 2>/dev/null | head -30
echo

# 4. Strings extraction
echo "[4] Strings Search"
strings -n 8 "$TARGET" | grep -iE 'flag|ctf|password|key|secret|hidden' | head -10
echo

# 5. Format-specific detection
FILETYPE=$(file -b "$TARGET" | head -1)
case "$FILETYPE" in
    *JPEG*|*JPEG*)
        echo "[5a] JPEG Steganography Detection"
        echo "Trying steghide info with empty passphrase..."
        steghide info "$TARGET" -p "" 2>&1
        echo
        ;;
    *PNG*)
        echo "[5b] PNG LSB Detection (zsteg)"
        zsteg -a "$TARGET" 2>&1 | head -20
        echo
        ;;
    *BMP*)
        echo "[5c] BMP Detection (zsteg + steghide)"
        zsteg -a "$TARGET" 2>&1 | head -20
        steghide info "$TARGET" -p "" 2>&1
        echo
        ;;
esac

# 6. Embedded file signatures
echo "[6] Embedded File Scan (binwalk)"
binwalk "$TARGET"
echo

echo "=== Triage Complete ==="
echo "Review results above and proceed with targeted extraction."
```

---

## 10. Encoding and Decoding Helpers

### Common Payload Decoding

```bash
# Base64 decode extracted data
cat extracted.txt | base64 -d > decoded.bin

# Hex decode extracted data
cat extracted.txt | xxd -r -p > decoded.bin

# Check if extracted data is a known file type
file decoded.bin

# If extracted data is compressed
gzip -d decoded.bin.gz
bunzip2 decoded.bin.bz2
xz -d decoded.bin.xz
zcat decoded.bin.Z > decompressed.bin

# If extracted data is a ZIP archive
unzip decoded.bin -d /tmp/zip_contents/

# If extracted data is a tar archive
tar xf decoded.bin -C /tmp/tar_contents/

# ROT13 decode (common in CTF)
echo "synt{fgneg" | tr 'A-Za-z' 'N-ZA-Mn-za-m'

# Binary to text
python3 -c "
data = open('decoded.bin', 'rb').read()
try:
    print(data.decode('utf-8'))
except:
    print(f'Binary data: {len(data)} bytes')
    print(f'Hex: {data.hex()[:200]}')
"
```

### Image Comparison for Hidden Data Detection

```bash
# Compare suspected image with known original
# Pixel-level differences reveal modified regions
python3 -c "
from PIL import Image
import sys

if len(sys.argv) < 3:
    print('Usage: compare.py original.jpg suspected.jpg')
    sys.exit(1)

orig = Image.open(sys.argv[1]).convert('RGB')
suspect = Image.open(sys.argv[2]).convert('RGB')

if orig.size != suspect.size:
    print(f'Size mismatch: {orig.size} vs {suspect.size}')
    sys.exit(1)

diff_pixels = 0
diff_img = Image.new('RGB', orig.size)
for y in range(orig.size[1]):
    for x in range(orig.size[0]):
        o = orig.getpixel((x, y))
        s = suspect.getpixel((x, y))
        if o != s:
            diff_pixels += 1
            # Amplify differences for visibility
            d = tuple(min(255, abs(a - b) * 10) for a, b in zip(o, s))
            diff_img.putpixel((x, y), d)

total = orig.size[0] * orig.size[1]
print(f'Different pixels: {diff_pixels}/{total} ({diff_pixels/total*100:.2f}%)')
diff_img.save('diff_output.png')
print('Difference image saved to diff_output.png')
" original.jpg suspected.jpg
```

---

## 11. Audio Steganography

### WAV LSB Extraction

```bash
# Check WAV file properties
file suspicious.wav
exiftool suspicious.wav


<!-- truncated for token budget; see external/kali-claw for the rest -->

