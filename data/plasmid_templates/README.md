# Plasmid Templates Directory

Place your plasmid template files here. The TALE Finder will use these templates
for generating plasmid designs.

## Directory Structure

```
plasmid_templates/
├── backbones/           # Plasmid backbone sequences
│   ├── pCMV-TALEN.gb    # Standard TALEN expression vector
│   ├── pTAL-VP64.gb     # Transcription activator
│   └── pTAL-KRAB.gb     # Transcription repressor
├── promoters/           # Promoter sequences
│   ├── CMV.fasta
│   ├── EF1a.fasta
│   └── CAG.fasta
├── effectors/           # Effector domain sequences
│   ├── FokI.fasta       # Standard FokI nuclease
│   ├── FokI_Sharkey.fasta
│   ├── VP64.fasta
│   └── KRAB.fasta
├── terminators/         # Polyadenylation signals
│   ├── bGH_polyA.fasta
│   └── SV40_polyA.fasta
└── rvd_modules/         # RVD repeat module sequences
    ├── NI.fasta         # For Adenine
    ├── HD.fasta         # For Cytosine
    ├── NN.fasta         # For Guanine (strong)
    ├── NH.fasta         # For Guanine (specific)
    └── NG.fasta         # For Thymine
```

## File Formats

### GenBank (.gb) files
Used for complete plasmid backbones with annotations.

### FASTA (.fasta) files
Used for individual sequence components.

## Adding New Templates

1. Place the file in the appropriate subdirectory
2. Ensure the filename follows the naming convention
3. For GenBank files, include feature annotations

## Template Sources

You can obtain template sequences from:
- Addgene (https://www.addgene.org/)
- NCBI GenBank
- Published literature

Note: Ensure you have appropriate rights to use template sequences.
