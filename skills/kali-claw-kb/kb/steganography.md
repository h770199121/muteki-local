# steganography

# Skill: Steganography

> **Supplementary Files**:
> - `payloads.md` — Steganography command reference covering format identification, embedding and extraction with steghide, PNG analysis with zsteg, firmware extraction with binwalk, file carving with foremost, metadata analysis with exiftool, and password recovery with stegcracker
> - `test-cases.md` — Structured test case list covering format identification, steghide embedding/extraction, zsteg PNG analysis, binwalk firmware extraction, stegcracker password recovery, and metadata analysis with exiftool

## Summary

Unlike encryption, which makes data unreadable but visibly present, steganography hides the very existence of the hidden data.

**Tools**: steghide, stegcracker, zsteg, binwalk, foremost, exiftool

**Domain**: forensics

## Description

Steganography is the practice of concealing data within non-secret carrier files such as images, audio, video, and documents. Unlike encryption, which makes data unreadable but visibly present, steganography hides the very existence of the hidden data. This skill covers both offensive techniques (embedding covert data for exfiltration or C2 communication) and defensive techniques (detecting and extracting hidden data during forensics investigations and CTF challenges).

**Core Insight**: Steganography exploits the gap between what humans perceive and what digital files actually contain. A JPEG image that looks identical before and after embedding may carry megabytes of hidden data in its least-significant bits, quantization tables, or appended file segments. Detection requires statistical analysis, not visual inspection.

**Key Attack Surfaces**:

- **LSB Embedding**: Least-significant-bit manipulation in BMP/PNG/WAV files where altering the lowest bit of each color channel is imperceptible to the human eye
- **JPEG Coefficient Manipulation**: Modifying DCT coefficients in JPEG files using tools like steghide, which hides data in the frequency domain
- **Metadata Abuse**: Hiding data in EXIF fields, IPTC tags, XMP metadata, or comment sections where it is overlooked during casual inspection
- **Appended Data**: Concatenating archives, scripts, or binaries after the carrier file's EOF marker, invisible to standard viewers
- **Palette Manipulation**: Reordering or duplicating color palette entries in GIF/PNG to encode information

---

## Use Cases

1. **CTF Steganography Challenges** - Systematically identify carrier format, apply format-specific detection tools, extract hidden flags from images, audio files, and documents
2. **Data Exfiltration Detection** - Analyze suspected carrier files on compromised systems to detect hidden data channels used for intellectual property theft or C2 communication
3. **Anti-Forensics Analysis** - Detect steganographic tools and embedded payloads on seized devices during digital forensic investigations
4. **Covert Channel Assessment** - Test organizational defenses against data hiding techniques by embedding test data in common file types and measuring detection rates
5. **Malware Payload Analysis** - Extract steganographically-hidden payloads from images delivered via phishing emails or hosted on compromised websites

---

## Core Tools

| Tool | Purpose | Command Example |
|------|---------|-----------------|
| **steghide** | Embed and extract data in JPEG, BMP, WAV, and AU files with passphrase support | `steghide extract -sf carrier.jpg -p password` |
| **stegcracker** | Brute-force steghide passphrases using wordlists | `stegcracker carrier.jpg /usr/share/wordlists/rockyou.txt` |
| **zsteg** | Detect and extract LSB-encoded data in PNG and BMP files | `zsteg -a suspicious.png` |
| **binwalk** | Identify and extract embedded files, firmware components, and appended data | `binwalk -Me firmware.bin` |
| **foremost** | Carve files from disk images and carrier files based on header/footer signatures | `foremost -t jpg,png,pdf -i carrier.bin -o /output` |
| **exiftool** | Read and analyze file metadata including EXIF, IPTC, XMP, and custom tags | `exiftool -a -G1 suspicious.jpg` |

Auxiliary tools: **stegsolve** (visual analysis with bit-plane filters), **g stag** (generic steganography framework), **outguess** (JPEG steganography with statistical correction), **jsteg** (JPEG LSB embedding), **strings** (quick text extraction from any binary file).

---

## Methodology

### Analysis Chain

```
[1] Identify              [2] Analyze             [3] Detect
  - Carrier format          - File metadata          - Format-specific stego
    (JPEG/PNG/BMP/          - Size anomalies          detection
     WAV/PDF)               - Entropy analysis      - steghide info / zsteg /
  - True file type          - Comment fields           binwalk signatures
    vs extension          - Appended data            - Statistical tests
       |                        |                        |
       v                        v                        v
[4] Extract              [5] Crack               [6] Verify
  - Tool-specific           - stegcracker with        - Validate extracted
    extraction                wordlists                data integrity
  - LSB data recovery       - Custom dictionary       - Check file signatures
  - Carve embedded files    - Rule-based              - Confirm completeness
                              mutations
```

**Phase Details**:

1. **Identify** - Determine the true file format regardless of extension using magic bytes (`file` command, `xxd | head`). JPEG files start with `FF D8 FF`, PNG with `89 50 4E 47`, BMP with `42 4D`, and WAV with `52 49 46 46`. Mismatched extensions are a common anti-analysis trick
2. **Analyze** - Extract comprehensive metadata with exiftool, compare file size against expected size for the format and resolution, check for unusually high entropy in regions that should be structured, and examine comment/annotation fields
3. **Detect** - Run format-appropriate detection: steghide info for JPEG/BMP, zsteg for PNG/BMP, binwalk for any binary with embedded signatures. Statistical analysis tools can reveal LSB manipulation through chi-square tests and sample-pair analysis
4. **Extract** - Use the appropriate tool based on format and embedding method: steghide for JPEG/BMP/WAV, zsteg for PNG LSB, binwalk for appended/embedded files, foremost for file carving from composite images
5. **Crack** - If the embedded data is passphrase-protected, use stegcracker with standard wordlists (rockyou.txt, SecLists). Custom dictionaries based on context (CTF theme, target organization) improve success rates
6. **Verify** - Validate the extracted data by checking file signatures, attempting to decompress archives, decoding base64 or hex payloads, and confirming data completeness against any embedded length indicators

## Practical Steps

### 1. Format Identification Phase

```bash
# Determine true file type regardless of extension
file suspicious_image.jpg
xxd suspicious_image.jpg | head -5

# Check for mismatched extensions (common CTF trick)
# PNG with .jpg extension or vice versa
python3 -c "
import magic
print(magic.from_file('suspicious_image.jpg'))
"
```

### 2. Metadata Analysis Phase

```bash
# Comprehensive metadata extraction
exiftool -a -G1 suspicious.jpg

# Check for unusual comment fields
exiftool -Comment -UserComment -ImageDescription suspicious.jpg

# Compare file size to expected size for resolution
identify suspicious.jpg  # ImageMagick for dimensions
```

# JPEG/BMP: check for steghide embedding
steghide info carrier.jpg

# PNG: run zsteg with all channels
zsteg -a suspicious.png

# Any binary: scan for embedded signatures
binwalk suspicious.png
```

> **For detailed payloads see `payloads.md`, and for the complete test checklist see `test-cases.md`.**

---

## Defense Evasion Techniques

### Steganography Stealth
- **Match container entropy**: Don't exceed container's natural entropy.
- **Sparse embedding**: Embed data sparsely; reduces statistical anomaly.
- **Use lossless formats**: PNG/BMP over JPEG; avoids recompression artifacts.
- **Color palette abuse**: Hide data in palette of 8-bit PNG; minimal visual change.

### Channel Selection
- **Audio over image**: WAV/FLAC less monitored than PNG/JPG.
- **Video steganography**: Frame-by-frame LSB; high bandwidth.
- **Network packet timing**: Encode in inter-packet delays; covert timing channel.
- **PDF object abuse**: Hide data in PDF object streams; less scanned.

## Detection and Evasion

Defenders detect steganography through statistical anomaly detection (chi-square tests on LSB distributions), file size monitoring (carrier files with hidden data are often larger than expected for their resolution), entropy analysis (regions of unusually high entropy in image data), and network traffic analysis (unusually large image uploads or frequent image transfers to unexpected destinations). Attackers evade detection by using JPEG-domain embedding (steghide) which preserves file size, adding noise to reduce statistical signatures, and distributing hidden data across multiple carrier files. For testing, use steghide with its built-in statistical correction to produce carriers that resist basic chi-square detection.

## Advanced Techniques

Beyond core LSB and DCT embedding, advanced steganography includes: adaptive embedding that avoids smooth image regions where modifications are more detectable, matrix embedding using Hamming codes to minimize the number of modified bits, palette-based hiding in indexed-color images (GIF/PNG-8) by reordering or duplicating palette entries, and spread-spectrum embedding that distributes hidden data across the frequency domain for robustness against compression and resizing. For audio carriers, echo hiding encodes data in the parameters of artificially introduced echoes. In video, motion vector steganography modifies inter-frame motion vectors to carry hidden data.
