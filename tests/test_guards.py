"""The guards, tested against what they are supposed to catch.

An adversarial audit of the published 0.5.4 found that `check_dump` reported
success on a README, a JSON file and an empty file. Every dump-reading command
routes through it, so a file this reader cannot parse produced an empty graph
and every command downstream reported a clean library: no axiom reached, no
theorem eligible, nothing inheriting a sorry.
"""

from __future__ import annotations

import pytest

from gonzalgo import lean


def write(tmp_path, name, rows):
    p = tmp_path / name
    p.write_text("".join("\t".join(r) + "\n" for r in rows), encoding="utf-8")
    return p


class TestNotADump:
    def test_an_empty_file_is_refused(self, tmp_path):
        p = tmp_path / "empty.tsv"
        p.write_text("", encoding="utf-8")
        with pytest.raises(lean.DumpError) as caught:
            lean.check_dump(p)
        assert "not a dump" in str(caught.value)
        assert "no rows at all" in str(caught.value)

    def test_prose_is_refused(self, tmp_path):
        p = tmp_path / "README.md"
        p.write_text("# gonzalgo\n\nMeasure where a library spends its axioms.\n",
                     encoding="utf-8")
        with pytest.raises(lean.DumpError):
            lean.check_dump(p)

    def test_json_is_refused(self, tmp_path):
        p = tmp_path / "data.json"
        p.write_text('{"declarations": 795218, "axioms": 15}\n', encoding="utf-8")
        with pytest.raises(lean.DumpError):
            lean.check_dump(p)

    def test_binary_is_refused(self, tmp_path):
        p = tmp_path / "blob.bin"
        p.write_bytes(bytes(range(256)) * 4)
        with pytest.raises(lean.DumpError):
            lean.check_dump(p)

    def test_a_dump_with_declarations_and_no_theorems_still_passes(self, tmp_path):
        """The deliberate case: definitions only is a valid dump."""
        p = write(tmp_path, "defs.tsv", [("D", "f", "Nat", "Nat.succ")])
        assert lean.check_dump(p)["theorems"] == 0

    def test_a_real_dump_passes(self, tmp_path):
        p = write(tmp_path, "d.tsv", [
            ("A", "Classical.choice", "", ""),
            ("T", "thm", "Nat", "Classical.choice"),
        ])
        stats = lean.check_dump(p)
        assert stats["declarations"] == 2
        assert stats["theorems_with_proof"] == 1


class TestRealWitness:
    """The site test was `" " in w or "." in w`, which admits anything punctuated."""

    @pytest.mark.parametrize("witness", ["42 43", ".", "...", "1.5", "3 4 5"])
    def test_punctuation_alone_is_not_a_witness(self, witness):
        assert lean.real_witness(witness) is False

    @pytest.mark.parametrize("witness", [
        "instDecidableEqNat a b",
        "Nat.decEq",
        "_root_.instDecidableAnd",
        "Classical.propDecidable p",
    ])
    def test_a_library_instance_is_a_witness(self, witness):
        assert lean.real_witness(witness) is True

    @pytest.mark.parametrize("witness", ["", "   ", "inst✝", "h✝ a b"])
    def test_the_existing_exclusions_still_hold(self, witness):
        assert lean.real_witness(witness) is False

    def test_a_bare_identifier_is_still_not_a_witness(self, witness="inst"):
        """A Decidable hypothesis in scope: nothing to substitute."""
        assert lean.real_witness(witness) is False


class TestEveryCommandInheritsTheGuard:
    """_load calls check_dump, so the floor holds for every dump-reading command."""

    def test_load_through_the_cli_helper_refuses_a_non_dump(self, tmp_path):
        from gonzalgo import cli

        p = tmp_path / "README.md"
        p.write_text("not a dump\n", encoding="utf-8")
        with pytest.raises(lean.DumpError):
            cli._load(p, quiet=True)
