#!/usr/bin/env bash
# Provisions a real, production-scale Foldseek search database for the
# self-hosted Discover backend (foldseek.backend: local in config.yaml).
#
# This is a deployment-time operation, not something run during development
# or CI - it downloads and indexes a real Foldseek database (potentially
# hundreds of GB), which takes real disk, bandwidth, and time (minutes to
# many hours depending on which database and your connection). Run it on
# the actual host/volume that will serve Discover traffic, with the target
# directory on a disk that has enough free space for the option you pick.
#
# Usage:
#   scripts/provision_foldseek_db.sh <database-name> <output-dir> [tmp-dir]
#
# See `foldseek databases -h` (run with no args below) for the full list of
# database names and their descriptions - the ones actually relevant to
# Discover's default `pdb100`/`afdb50` search set, roughly smallest-to-
# largest based on Foldseek's own docs, are:
#
#   CATH50                  CATH domain database (AlphaFold + PDB, clustered
#                            50% seq. id.) - narrower scope than full PDB.
#   PDB                     The full Protein Data Bank - matches Discover's
#                            default pdb100 database exactly.
#   BFVD                    Predicted viral protein structures only - only
#                            useful if most of your queries are viral.
#   Alphafold/Swiss-Prot    AlphaFold structures for reviewed UniProt/
#                            Swiss-Prot entries only - much smaller than the
#                            full AlphaFold DB, still broad taxonomic
#                            coverage.
#   Alphafold/UniProt50-minimal
#                           AlphaFold DB clustered at 50% identity,
#                            representative structures only - matches
#                            Discover's default afdb50 database, a
#                            meaningfully smaller download than the full
#                            Alphafold/UniProt option below.
#   Alphafold/UniProt       The FULL AlphaFold Protein Structure Database -
#                            Foldseek's own docs list this at ~700GB
#                            download / ~950GB extracted. Only provision
#                            this if you specifically need full AFDB
#                            coverage and have the disk/bandwidth budget for
#                            it; Alphafold/UniProt50 or -minimal cover the
#                            same structures at a small fraction of the size.
#
# Known caveat (as of this writing): `foldseek databases BFMD ...` has an
# open upstream issue where the download doesn't actually work despite being
# listed (https://github.com/steineggerlab/foldseek/issues/563) - check
# that issue before relying on BFMD.
#
# After this completes, point config.yaml at the result:
#   foldseek:
#     backend: local
#     local:
#       binary_path: /usr/local/bin/foldseek   # or wherever it's installed
#       database_dir: <output-dir>/<database-name>   # the -o prefix below

set -euo pipefail

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <database-name> <output-dir> [tmp-dir]" >&2
    echo "Run 'foldseek databases' with no arguments for the full list of database names." >&2
    exit 1
fi

DB_NAME="$1"
OUTPUT_DIR="$2"
TMP_DIR="${3:-${OUTPUT_DIR}/tmp}"

if ! command -v foldseek >/dev/null 2>&1; then
    echo "foldseek binary not found on PATH. Install it first - see:" >&2
    echo "  https://github.com/steineggerlab/foldseek#installation" >&2
    exit 1
fi

mkdir -p "$OUTPUT_DIR" "$TMP_DIR"
OUTPUT_PREFIX="${OUTPUT_DIR}/${DB_NAME//\//_}"

echo "Provisioning Foldseek database '${DB_NAME}' -> ${OUTPUT_PREFIX}"
echo "This can take from minutes to many hours depending on the database and your connection."
echo

foldseek databases "$DB_NAME" "$OUTPUT_PREFIX" "$TMP_DIR"

echo
echo "Done. Set in config.yaml:"
echo "  foldseek.backend: local"
echo "  foldseek.local.database_dir: ${OUTPUT_PREFIX}"
