from src.backend.sequence_viewer import SequenceViewer


def test_identity():
    sv = SequenceViewer()

    # 1. Perfect match
    seqs1 = {"P1": "ABC", "P2": "ABC"}
    id1 = sv.calculate_identity(seqs1)
    print(f"Test 1 (Perfect Match): {id1}% (Expected: 100.0%)")

    # 2. 50% match
    seqs2 = {"P1": "ABCD", "P2": "ABEF"}
    id2 = sv.calculate_identity(seqs2)
    print(f"Test 2 (50% Match): {id2}% (Expected: 50.0%)")

    # 3. Gaps
    seqs3 = {"P1": "A-C", "P2": "A-C"}
    id3 = sv.calculate_identity(seqs3)
    # Matches: A, C (2). Length: 3. Identity: 2/3 = 66.6%
    print(f"Test 3 (Gaps Match): {id3:.1f}% (Expected: 66.7%)")

    # 4. No matches
    seqs4 = {"P1": "AAA", "P2": "BBB"}
    id4 = sv.calculate_identity(seqs4)
    print(f"Test 4 (No Match): {id4}% (Expected: 0.0%)")


if __name__ == "__main__":
    test_identity()
