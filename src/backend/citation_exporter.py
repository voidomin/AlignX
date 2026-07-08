"""
Citation Exporter Module.

Assembles a "Methods & Citations" export (plain text + BibTeX) for a
completed Compare or Discover run, covering exactly what that run actually
used: the alignment/search algorithm, the structure source database(s) the
input structures came from, and (for Discover) the annotation sources that
contributed to the function hypothesis. A researcher citing a StructScope
result needs this to be accurate, not exhaustive - an unused source cited
"just in case" is as wrong as a missing one.
"""

import re
from datetime import datetime
from pathlib import Path
from tempfile import gettempdir
from typing import Any, Dict, List

from src.backend.pdb_manager import PDBManager

# Matches _safe_segment()'s pattern in api.py - every run_id this project
# generates (see src/utils/run_id.py) is alnum/underscore/hyphen only.
# api.py already validates run_id before ever calling export(), but this
# module has no visibility into that from a static-analysis standpoint
# (and shouldn't rely on it regardless) - it's the one thing here that
# reaches a filesystem path, so it validates for itself too.
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")

# Each entry is the citation for one underlying tool/database/algorithm.
# `bibtex` keys are unique but otherwise arbitrary - they only need to be
# stable and collision-free within a single export.
BIBLIOGRAPHY: Dict[str, Dict[str, str]] = {
    "structscope": {
        "text": "StructScope v{VERSION} (https://github.com/voidomin/AlignX).",
        "bibtex": (
            "@software{structscope,\n"
            "  title = {StructScope},\n"
            "  version = {{VERSION}},\n"
            "  url = {https://github.com/voidomin/AlignX}\n"
            "}"
        ),
    },
    "mustang": {
        "text": (
            "Konagurthu, A.S., Whisstock, J.C., Stuckey, P.J. and Lesk, A.M. "
            "(2006) MUSTANG: A multiple structural alignment algorithm. "
            "Proteins, 64(3), 559-574."
        ),
        "bibtex": (
            "@article{mustang2006,\n"
            "  author = {Konagurthu, Arun S. and Whisstock, James C. and "
            "Stuckey, Peter J. and Lesk, Arthur M.},\n"
            "  title = {MUSTANG: A multiple structural alignment algorithm},\n"
            "  journal = {Proteins},\n"
            "  volume = {64},\n"
            "  number = {3},\n"
            "  pages = {559--574},\n"
            "  year = {2006}\n"
            "}"
        ),
    },
    "foldseek": {
        "text": (
            "van Kempen, M., Kim, S.S., Tumescheit, C. et al. (2024) Fast "
            "and accurate protein structure search with Foldseek. Nature "
            "Biotechnology, 42, 243-246."
        ),
        "bibtex": (
            "@article{foldseek2024,\n"
            "  author = {van Kempen, Michel and Kim, Stephanie S. and "
            'Tumescheit, Charlotte and Mirdita, Milot and S{\\"o}ding, '
            "Johannes and Steinegger, Martin},\n"
            "  title = {Fast and accurate protein structure search with "
            "Foldseek},\n"
            "  journal = {Nature Biotechnology},\n"
            "  volume = {42},\n"
            "  pages = {243--246},\n"
            "  year = {2024}\n"
            "}"
        ),
    },
    "pdb": {
        "text": (
            "Berman, H.M., Westbrook, J., Feng, Z. et al. (2000) The "
            "Protein Data Bank. Nucleic Acids Research, 28(1), 235-242."
        ),
        "bibtex": (
            "@article{pdb2000,\n"
            "  author = {Berman, Helen M. and Westbrook, John and Feng, "
            "Zukang and Gilliland, Gary and Bhat, T. N. and Weissig, Helge "
            "and Shindyalov, Ilya N. and Bourne, Philip E.},\n"
            "  title = {The Protein Data Bank},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {28},\n"
            "  number = {1},\n"
            "  pages = {235--242},\n"
            "  year = {2000}\n"
            "}"
        ),
    },
    "alphafold_db": {
        "text": (
            "Varadi, M., Anyango, S., Deshpande, M. et al. (2022) AlphaFold "
            "Protein Structure Database: massively expanding the structural "
            "coverage of protein-sequence space with high-accuracy models. "
            "Nucleic Acids Research, 50(D1), D439-D444."
        ),
        "bibtex": (
            "@article{alphafolddb2022,\n"
            "  author = {Varadi, Mihaly and Anyango, Stephen and Deshpande, "
            "Mandar and others},\n"
            "  title = {AlphaFold Protein Structure Database: massively "
            "expanding the structural coverage of protein-sequence space "
            "with high-accuracy models},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {50},\n"
            "  number = {D1},\n"
            "  pages = {D439--D444},\n"
            "  year = {2022}\n"
            "}"
        ),
    },
    "swissmodel": {
        "text": (
            "Waterhouse, A., Bertoni, M., Bienert, S. et al. (2018) "
            "SWISS-MODEL: homology modelling of protein structures and "
            "complexes. Nucleic Acids Research, 46(W1), W296-W303."
        ),
        "bibtex": (
            "@article{swissmodel2018,\n"
            "  author = {Waterhouse, Andrew and Bertoni, Martino and "
            "Bienert, Stefan and others},\n"
            "  title = {SWISS-MODEL: homology modelling of protein "
            "structures and complexes},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {46},\n"
            "  number = {W1},\n"
            "  pages = {W296--W303},\n"
            "  year = {2018}\n"
            "}"
        ),
    },
    "esm_atlas": {
        "text": (
            "Lin, Z., Akin, H., Rao, R. et al. (2023) Evolutionary-scale "
            "prediction of atomic-level protein structure with a language "
            "model. Science, 379(6637), 1123-1130."
        ),
        "bibtex": (
            "@article{esmatlas2023,\n"
            "  author = {Lin, Zeming and Akin, Halil and Rao, Roshan and "
            "others},\n"
            "  title = {Evolutionary-scale prediction of atomic-level "
            "protein structure with a language model},\n"
            "  journal = {Science},\n"
            "  volume = {379},\n"
            "  number = {6637},\n"
            "  pages = {1123--1130},\n"
            "  year = {2023}\n"
            "}"
        ),
    },
    "interpro": {
        "text": (
            "Paysan-Lafosse, T., Blum, M., Chuguransky, S. et al. (2023) "
            "InterPro in 2022. Nucleic Acids Research, 51(D1), D418-D427."
        ),
        "bibtex": (
            "@article{interpro2023,\n"
            "  author = {Paysan-Lafosse, Typhaine and Blum, Matthias and "
            "Chuguransky, Sara and others},\n"
            "  title = {InterPro in 2022},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {51},\n"
            "  number = {D1},\n"
            "  pages = {D418--D427},\n"
            "  year = {2023}\n"
            "}"
        ),
    },
    "quickgo": {
        "text": (
            "Binns, D., Dimmer, E., Huntley, R. et al. (2009) QuickGO: a "
            "web-based tool for Gene Ontology searching. Bioinformatics, "
            "25(22), 3045-3046."
        ),
        "bibtex": (
            "@article{quickgo2009,\n"
            "  author = {Binns, David and Dimmer, Emily and Huntley, "
            "Rachael and others},\n"
            "  title = {QuickGO: a web-based tool for Gene Ontology "
            "searching},\n"
            "  journal = {Bioinformatics},\n"
            "  volume = {25},\n"
            "  number = {22},\n"
            "  pages = {3045--3046},\n"
            "  year = {2009}\n"
            "}"
        ),
    },
    "string": {
        "text": (
            "Szklarczyk, D., Kirsch, R., Koutrouli, M. et al. (2023) The "
            "STRING database in 2023: protein-protein association networks "
            "and functional enrichment analyses for any sequenced genome of "
            "interest. Nucleic Acids Research, 51(D1), D638-D646."
        ),
        "bibtex": (
            "@article{string2023,\n"
            "  author = {Szklarczyk, Damian and Kirsch, Rebecca and "
            "Koutrouli, Mikaela and others},\n"
            "  title = {The STRING database in 2023: protein-protein "
            "association networks and functional enrichment analyses for "
            "any sequenced genome of interest},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {51},\n"
            "  number = {D1},\n"
            "  pages = {D638--D646},\n"
            "  year = {2023}\n"
            "}"
        ),
    },
    "reactome": {
        "text": (
            "Gillespie, M., Jassal, B., Stephan, R. et al. (2022) The "
            "reactome pathway knowledgebase 2022. Nucleic Acids Research, "
            "50(D1), D687-D692."
        ),
        "bibtex": (
            "@article{reactome2022,\n"
            "  author = {Gillespie, Marc and Jassal, Bijay and Stephan, "
            "Ralf and others},\n"
            "  title = {The reactome pathway knowledgebase 2022},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {50},\n"
            "  number = {D1},\n"
            "  pages = {D687--D692},\n"
            "  year = {2022}\n"
            "}"
        ),
    },
    "sifts": {
        "text": (
            "Dana, J.M., Gutmanas, A., Tyagi, N. et al. (2019) SIFTS: "
            "updated Structure Integration with Function, Taxonomy and "
            "Sequences resource allows 40-fold increase in coverage of "
            "structure-based annotations for proteins. Nucleic Acids "
            "Research, 47(D1), D482-D489."
        ),
        "bibtex": (
            "@article{sifts2019,\n"
            "  author = {Dana, Jose M. and Gutmanas, Aleksandras and Tyagi, "
            "Nidhi and others},\n"
            "  title = {SIFTS: updated Structure Integration with Function, "
            "Taxonomy and Sequences resource allows 40-fold increase in "
            "coverage of structure-based annotations for proteins},\n"
            "  journal = {Nucleic Acids Research},\n"
            "  volume = {47},\n"
            "  number = {D1},\n"
            "  pages = {D482--D489},\n"
            "  year = {2019}\n"
            "}"
        ),
    },
    "gmgc": {
        "text": (
            "Coelho, L.P., Alves, R., Monteiro, P. et al. (2022) The "
            "Global Microbial Gene Catalog GMGC: complete and curated "
            "metagenomic gene catalogs. bioRxiv."
        ),
        "bibtex": (
            "@article{gmgc2022,\n"
            "  author = {Coelho, Luis Pedro and Alves, Renato and Monteiro, "
            "Pedro and others},\n"
            "  title = {The Global Microbial Gene Catalog GMGC: complete "
            "and curated metagenomic gene catalogs},\n"
            "  journal = {bioRxiv},\n"
            "  year = {2022}\n"
            "}"
        ),
    },
}

# Foldseek search-database keys (see foldseek_client.py's ALLOWED_DATABASES)
# mapped to the bibliography entry backing that database's content.
_FOLDSEEK_DB_SOURCE = {
    "pdb100": "pdb",
    "afdb50": "alphafold_db",
    "afdb-swissprot": "alphafold_db",
    "afdb-proteome": "alphafold_db",
    "mgnify_esm30": "esm_atlas",
    "gmgcl_id": "gmgc",
}
# Both the PDB and CATH Foldseek databases resolve hits to a UniProt
# accession via SIFTS (see annotation_aggregator.py) - cite it whenever
# either was searched.
_SIFTS_TRIGGER_DBS = {"pdb100", "cath50"}


def _structure_source_citation(pdb_id: str) -> str:
    source = PDBManager.detect_source(pdb_id)
    return {
        "alphafold": "alphafold_db",
        "swissmodel": "swissmodel",
        "esmfold": "esm_atlas",
    }.get(source, "pdb")


def citations_for_compare_run(pdb_ids: List[str]) -> List[str]:
    """Citation ids for a Compare run: Mustang plus one entry per distinct
    structure source database actually referenced by the input IDs."""
    ids = ["mustang"]
    for pdb_id in pdb_ids or []:
        source_id = _structure_source_citation(pdb_id)
        if source_id not in ids:
            ids.append(source_id)
    return ids


# Per-neighbor annotation fields (see annotation_aggregator.py) mapped to
# the citation they justify - cited only if at least one neighbor actually
# has data in that field, not just because Discover mode can query it.
_ANNOTATION_FIELD_SOURCE = [
    ("domains", "interpro"),
    ("go_terms", "quickgo"),
    ("string_partners", "string"),
    ("reactome_pathways", "reactome"),
]


def citations_for_discover_run(results: Dict[str, Any]) -> List[str]:
    """Citation ids for a Discover run: Foldseek, the query structure's own
    source database, every Foldseek database actually searched, and every
    annotation source that actually contributed data to at least one
    neighbor - not every source Discover mode is capable of querying."""
    ids: List[str] = []
    seen = set()

    def add(citation_id: str) -> None:
        if citation_id not in seen:
            seen.add(citation_id)
            ids.append(citation_id)

    add("foldseek")
    add(_structure_source_citation(results.get("pdb_id", "")))

    databases_searched = results.get("databases_searched") or []
    for db in databases_searched:
        source_id = _FOLDSEEK_DB_SOURCE.get(db)
        if source_id:
            add(source_id)
    if any(db in _SIFTS_TRIGGER_DBS for db in databases_searched):
        add("sifts")

    per_neighbor = (results.get("annotations") or {}).get("per_neighbor") or []
    for field, citation_id in _ANNOTATION_FIELD_SOURCE:
        if any(n.get(field) for n in per_neighbor):
            add(citation_id)

    return ids


class CitationExporter:
    """Renders a citation-id list into a combined plain-text + BibTeX file."""

    def export(
        self, citation_ids: List[str], run_id: str, version: str = "0.0.0"
    ) -> Path:
        if not _SAFE_RUN_ID.match(run_id):
            raise ValueError(f"Invalid run_id: {run_id!r}")

        ids = list(dict.fromkeys(citation_ids + ["structscope"]))
        entries = [BIBLIOGRAPHY[c] for c in ids if c in BIBLIOGRAPHY]

        lines = [
            "StructScope - Methods & Citations",
            f"Run: {run_id}",
            f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "This run used the tools and databases below. Cite the ones",
            "relevant to your use of this result.",
            "",
            "== Plain text ==",
            "",
        ]
        for entry in entries:
            lines.append(entry["text"].replace("{VERSION}", version))
            lines.append("")

        lines.append("== BibTeX ==")
        lines.append("")
        for entry in entries:
            lines.append(entry["bibtex"].replace("{VERSION}", version))
            lines.append("")

        out_path = Path(gettempdir()) / f"structscope_citations_{run_id}.txt"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path
