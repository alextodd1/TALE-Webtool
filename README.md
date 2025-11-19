# 🧬 TALE Pair Finder v0.2.0 (beta)

## Overview

Transcription Activator-Like Effectors (TALEs) are DNA-binding proteins from _Xanthomonas_ bacteria that recognize specific DNA sequences through a modular repeat domain. Each repeat contains a repeat-variable diresidue (RVD) at positions 12-13 that specifies binding to a single nucleotide: NI binds adenine, HD binds cytosine, NN/NH bind guanine, and NG binds thymine. This simple, predictable code enables engineering of custom DNA-binding proteins with 15-30 bp specificity.

TALEs were largely abandoned after 2012 despite their superior specificity and predictable binding compared to zinc fingers, primarily due to CRISPR's emergence offering simpler cloning and multiplexing capabilities. The repetitive nature of TALE arrays (typically 15-20 nearly identical 34-amino acid repeats) made them challenging to synthesise and clone using traditional methods, while CRISPR required only a short guide RNA. However, modern DNA synthesis capabilities and falling costs now make TALE construction economically viable, potentially reviving interest in these highly specific, non-cutting DNA binding proteins for applications where CRISPR's DNA cleavage is undesirable.

This tool identifies optimal TALE binding site pairs in genomic sequences for various TALE-based applications. This tool aims to **in future** supports multiple TALE architectures including transcriptional activators, repressors, and future base editors. The algorithm searches for paired binding sites on opposite DNA strands with user-defined spacing, applying quality filters to maximise success probability.

### Algorithm

The search algorithm employs several optimisations for efficient genome-scale analysis:

1. **Pre-computation Phase:** Generates complementary strand, calculates cumulative GC arrays, and identifies CpG islands using 200bp sliding windows (≥50% GC, CpG observed/expected ≥0.6)

2. **Sliding Window Search:** Iterates through all possible TALE lengths and positions, checking each potential site against quality filters:
   - Position 0 must be T
   - GC content ≥25% (ensures binding stability)
   - No overlap with CpG islands ±100bp (avoids methylation)
   - Excludes ≥7 consecutive A/T (prevents synthesis issues)
   - Requires ≥3 strong RVDs (NN or HD) per TALE

3. **Pair Formation:** For each valid TALE, searches for complementary binding sites within the specified spacer range, applying identical quality filters

### Features

- Processes sequences up to 100,000 bp
- Configurable TALE lengths (10-30 bp) and spacer distances (1-100 bp)
- Position-specific searching for targeted regions
- Export functionality (CSV/TSV formats)
- Genomic viewer

### Current Limitations 

**Visualisation Issues:**
- Current bugs include rendering inconsistencies at different zoom levels
- Incorrect positioning of elements when switching between view modes
- Missing colour-coding options for TALE properties (length, GC content, RVD composition)

### Planned Enhancements

**Direct sequence-to-plasmid functionality**

Direct sequence-to-plasmid functionality is not yet implemented. Hopefully V3+ will enable clicking on identified TALE pairs to automatically generate annotated plasmid sequences with appropriate promoters, coding sequences, and assembly sites.

**Immediate Development**

- Multiple TALE architectures: TALEN nucleases (FokI fusions), transcriptional activators (VP64/VP160), repressors (KRAB/SID), and suppressor TALEs
- Direct plasmid generation with Golden Gate assembly sites (BsaI/Esp3I compatible)
- Integration with genome browsers for contextual analysis

**Algorithm Improvements**

- Enhanced RVD Options: Addition of NS (degenerate binding), NK (improved G specificity), and position-specific RVD preferences
- Refined Constraints: Position 2 A-avoidance, terminal NG preference (85% in natural TALEs), base composition scoring (31±16% A, 37±13% C, 9±8% G, 22±10% T)
- C-terminal Variants: Support for +28 and +63 architectures with spacer-specific recommendations (12-13 bp for +28/+28, 12-21 bp for +63/+63)
- Activity Prediction: Machine learning model incorporating RVD composition, spacer optimization, and terminal preferences
- Assembly Validation: Homology checking to prevent recombination, array diversity requirements, synthesis complexity scoring

**Advanced Features**

- Context-dependent binding predictions
- Mismatch tolerance mapping
- Batch design for library construction
- Cost optimisation for synthesis approaches


## How to Use

1. **Enter DNA Sequence** (100 - 100,000 bp)
2. **Configure Search Parameters**
   - TALE length: 10-30 bp
   - Spacer length: 1-100 bp
   - Guanine code: NH or NN
   - Optional position-specific search
3. **Start Search** - Progress updates in real-time
4. **Review Results** - Sort, filter, and analyze findings
5. **Export Data** - Download as CSV or TSV

The tool applies multiple quality filters to potential TALEs:

- **GC content:** ≥25% for optimal specificity
- **CpG islands:** Avoided (potential methylation)
- **Consecutive A/T:** Rejects 7+ consecutive A or T
- **Strong RVDs:** Requires ≥3 strong binding pairs (NN, HD) in the TALE

## RVD Encoding

- **NI** → Adenine (A)
- **HD** → Cytosine (C)
- **NN/NH** → Guanine (G)
- **NG** → Thymine (T)

## Documentation

- [DEPLOYMENT.md](DEPLOYMENT.md) - Complete deployment guide with technical details, configuration, API endpoints, security, monitoring, and troubleshooting
- [/about](http://localhost:8000/about) - Application documentation

## Good References for TALE targeting

- Boch et al. (2009) - TALE DNA binding specificity
- Miller et al. (2011) - TALEN genome editing
- Cermak et al. (2011) - TALE architecture

## License

MIT License

Copyright (c) 2025 Alex Todd

---

Developed by Alex Todd for bioinfo research and gene engineering.

![Version](https://img.shields.io/badge/version-2.0.0-blue)
![Python](https://img.shields.io/badge/python-3.10+-green)
![License](https://img.shields.io/badge/license-MIT-orange)





