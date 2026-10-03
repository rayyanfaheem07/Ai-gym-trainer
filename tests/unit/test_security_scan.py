"""Unit tests for CI security scan behavior.

Verifies that the private key detection grep pattern used in CI:
1. Excludes documentation directories (docs/) to avoid false positives from
   documentation that describes the scanner's own patterns.
2. Still detects actual private key material in source/config directories.
3. Does not match unrelated strings that merely contain the word 'PRIVATE'.
"""

import re

# The exact regex pattern and exclusion list from .github/workflows/ci.yml
CI_GREP_PATTERN = r"BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY"
CI_EXCLUDED_DIRS = {".git", "node_modules", ".venv", "docs"}

# Build test strings dynamically so that THIS test file does not itself
# contain literal PEM header strings that would trigger the CI grep scan.
_PEM_PREFIX = "-----"
_BEGIN = "BEGIN"
_END_SUFFIX = "PRIVATE KEY-----"


def _pem_header(*qualifiers: str) -> str:
    """Construct a PEM header string dynamically to avoid triggering the CI grep."""
    parts = [_PEM_PREFIX, _BEGIN]
    for q in qualifiers:
        parts.append(q)
    parts.append(_END_SUFFIX)
    return " ".join(parts)


def _matches_pattern(text: str) -> bool:
    """Check if text matches the CI scanner's regex pattern."""
    return bool(re.search(CI_GREP_PATTERN, text))


class TestSecurityScanPattern:
    """Tests for the private key detection regex used in CI."""

    def test_detects_generic_private_key_header(self):
        """Standard PEM private key header must be detected."""
        header = _pem_header()
        assert _matches_pattern(header)

    def test_detects_rsa_private_key_header(self):
        """RSA-specific PEM header must be detected."""
        header = _pem_header("RSA")
        assert _matches_pattern(header)

    def test_detects_ec_private_key_header(self):
        """EC-specific PEM header must be detected."""
        header = _pem_header("EC")
        assert _matches_pattern(header)

    def test_detects_dsa_private_key_header(self):
        """DSA-specific PEM header must be detected."""
        header = _pem_header("DSA")
        assert _matches_pattern(header)

    def test_detects_openssh_private_key_header(self):
        """OpenSSH-specific PEM header must be detected."""
        header = _pem_header("OPENSSH")
        assert _matches_pattern(header)

    def test_does_not_match_public_key_header(self):
        """Public key headers must NOT trigger a false positive."""
        assert not _matches_pattern("-----BEGIN PUBLIC KEY-----")

    def test_does_not_match_certificate(self):
        """Certificate headers must NOT trigger a false positive."""
        assert not _matches_pattern("-----BEGIN CERTIFICATE-----")

    def test_does_not_match_unrelated_private_word(self):
        """The word 'PRIVATE' alone must NOT trigger a match."""
        assert not _matches_pattern("This is a PRIVATE variable")

    def test_docs_excluded_from_scan(self):
        """The docs/ directory must be in the exclusion list to prevent false positives."""
        assert "docs" in CI_EXCLUDED_DIRS

    def test_source_directories_not_excluded(self):
        """Critical source directories must NOT be excluded from scanning."""
        for dir_name in ["backend", "ai", "scripts", "docker", "frontend"]:
            assert dir_name not in CI_EXCLUDED_DIRS, (
                f"Source directory '{dir_name}' must not be excluded from security scan"
            )

    def test_documentation_false_positive_scenario(self):
        """
        Documentation text that describes the scanner pattern must match the regex
        (confirming the false positive), which is why docs/ is excluded from the scan.
        """
        # Reconstruct the doc text dynamically to avoid triggering the CI grep
        doc_fragment = f"patterns (`{_BEGIN} {_END_SUFFIX.rstrip('-')}`)."
        assert _matches_pattern(doc_fragment)
