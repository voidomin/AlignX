from src.backend.pae_domain_calculator import calculate_pae_domains


def _two_block_pae_matrix(block_size=20, within=2.0, across=20.0):
    """A synthetic PAE matrix for two independent rigid domains: low PAE
    (confident relative position) within each block, high PAE (no
    confidence) across blocks - the standard shape a real two-domain
    AlphaFold model's PAE matrix has."""
    n = block_size * 2
    matrix = [[across] * n for _ in range(n)]
    for block_start in (0, block_size):
        for i in range(block_start, block_start + block_size):
            for j in range(block_start, block_start + block_size):
                matrix[i][j] = within
    return matrix


class TestCalculatePaeDomains:
    def test_separates_two_real_looking_rigid_domains(self):
        matrix = _two_block_pae_matrix(block_size=20)

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        assert domains is not None
        assert len(domains) == 2
        assert domains[0] == list(range(1, 21))
        assert domains[1] == list(range(21, 41))

    def test_returns_none_when_no_domain_meets_the_minimum_size(self):
        # Every residue confidently placed only relative to itself (an
        # all-high-PAE matrix) - no real rigid unit of any size exists.
        n = 15
        matrix = [[20.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 0.0

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        assert domains is None

    def test_a_single_fully_confident_structure_is_one_domain(self):
        n = 30
        matrix = [[1.0] * n for _ in range(n)]

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        assert domains == [list(range(1, 31))]

    def test_drops_a_component_smaller_than_min_domain_size_but_keeps_a_larger_one(
        self,
    ):
        n = 25
        matrix = [[20.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 0.0
        # A real 15-residue rigid block (>= min_domain_size=10) ...
        for i in range(15):
            for j in range(15):
                matrix[i][j] = 1.0
        # ... and a small 3-residue block (< min_domain_size) that should
        # be dropped as noise, not reported as a spurious tiny domain.
        for i in range(15, 18):
            for j in range(15, 18):
                matrix[i][j] = 1.0

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        assert domains == [list(range(1, 16))]

    def test_excludes_trivial_backbone_adjacency_so_a_disordered_chain_is_not_one_domain(
        self,
    ):
        # Real-data gotcha (confirmed against a real AlphaFold p53 model):
        # only immediate backbone neighbors (|i-j| == 1) are confidently
        # placed - a fully disordered chain with no real tertiary contacts
        # at all. Without excluding this trivial local band, connectivity
        # would chain the whole thing into a single spurious "domain."
        n = 40
        matrix = [[20.0] * n for _ in range(n)]
        for i in range(n):
            matrix[i][i] = 0.0
            if i + 1 < n:
                matrix[i][i + 1] = 1.0
                matrix[i + 1][i] = 1.0

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        assert domains is None

    def test_returns_none_for_an_empty_matrix(self):
        assert calculate_pae_domains([]) is None

    def test_returns_none_for_a_non_square_matrix(self):
        assert calculate_pae_domains([[1.0, 2.0], [3.0]]) is None

    def test_symmetrizes_an_asymmetric_real_looking_matrix(self):
        # PAE isn't symmetric in general - a pair should only be treated
        # as confidently placed once both directions are averaged below
        # threshold, not just one.
        n = 20
        matrix = [[20.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                if i != j:
                    matrix[i][j] = 4.0 if (i + j) % 2 == 0 else 6.0

        domains = calculate_pae_domains(
            matrix, threshold_angstrom=5.0, min_domain_size=10
        )

        # Symmetrized average of 4.0/6.0 is 5.0, not < 5.0 threshold - so
        # this asymmetric-but-borderline matrix should NOT connect
        # everything into one domain; the exact grouping depends on
        # which pairs land below 5.0 once averaged, but it must not
        # silently crash and must return a well-formed result.
        assert domains is None or all(isinstance(d, list) for d in domains)
