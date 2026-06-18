import unittest

from url_validate import SSRFBlockedError, assert_fetch_url_allowed, validate_fetch_url


class UrlValidateAllowTests(unittest.TestCase):
    def test_public_https(self) -> None:
        self.assertIsNone(validate_fetch_url("https://example.com/article"))
        self.assertIsNone(validate_fetch_url("http://www.polytropolis.com/p/foo"))

    def test_assert_does_not_raise(self) -> None:
        assert_fetch_url_allowed("https://example.com/")


class UrlValidateBlockTests(unittest.TestCase):
    def test_localhost(self) -> None:
        for url in (
            "http://localhost/admin",
            "http://127.0.0.1/",
            "http://[::1]/",
        ):
            self.assertIsNotNone(validate_fetch_url(url), url)

    def test_private_ranges(self) -> None:
        for url in (
            "http://10.0.0.1/",
            "http://192.168.0.1/",
            "http://172.16.0.1/",
        ):
            self.assertIsNotNone(validate_fetch_url(url), url)

    def test_metadata_endpoint(self) -> None:
        self.assertIsNotNone(validate_fetch_url("http://169.254.169.254/latest/meta-data/"))

    def test_numeric_localhost_alias(self) -> None:
        self.assertIsNotNone(validate_fetch_url("http://2130706433/"))

    def test_file_scheme(self) -> None:
        self.assertIsNotNone(validate_fetch_url("file:///etc/passwd"))

    def test_credentials(self) -> None:
        self.assertIsNotNone(validate_fetch_url("http://user:pass@example.com/"))

    def test_internal_suffix(self) -> None:
        self.assertIsNotNone(validate_fetch_url("http://printer.local/status"))

    def test_assert_raises(self) -> None:
        with self.assertRaises(SSRFBlockedError):
            assert_fetch_url_allowed("http://127.0.0.1/")


if __name__ == "__main__":
    unittest.main()
