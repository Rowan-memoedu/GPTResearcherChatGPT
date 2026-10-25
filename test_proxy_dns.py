import os
import socket
import unittest
from unittest.mock import Mock, patch

import proxy_dns
from gpt_researcher.utils import url_security


def answer(ip):
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, 0))]


class ProxyDNSTests(unittest.TestCase):
    def setUp(self):
        self.original = url_security.socket
        proxy_dns.install_proxy_dns_validation()
        self.environment = patch.dict(os.environ, {"ALLOW_PRIVATE_URLS": "false"})
        self.environment.start()
        proxy_dns.public_addresses.cache_clear()

    def tearDown(self):
        url_security.socket = self.original
        self.environment.stop()
        proxy_dns.public_addresses.cache_clear()

    def test_fake_dns_public_domain_gets_public_verification(self):
        with patch("proxy_dns.SYSTEM_RESOLVER", return_value=answer("198.18.0.9")), patch("proxy_dns.public_addresses", return_value=("93.184.215.14",)) as public:
            self.assertEqual(url_security.validate_url("https://example.org/article"), "https://example.org/article")
            public.assert_called_once()

    def test_private_and_literal_addresses_stay_blocked(self):
        for host, ip in [("127.0.0.1", "127.0.0.1"), ("private.example", "10.0.0.1"), ("169.254.169.254", "169.254.169.254"), ("198.18.0.9", "198.18.0.9"), ("router.local", "198.18.0.9")]:
            with self.subTest(host=host), patch("proxy_dns.SYSTEM_RESOLVER", return_value=answer(ip)), patch("proxy_dns.public_addresses") as public:
                with self.assertRaises(url_security.UnsafeURLError):
                    url_security.validate_url("http://" + host)
                public.assert_not_called()

    def test_mixed_private_resolution_stays_blocked(self):
        with patch("proxy_dns.SYSTEM_RESOLVER", return_value=answer("198.18.0.9") + answer("10.0.0.1")), patch("proxy_dns.public_addresses") as public:
            with self.assertRaises(url_security.UnsafeURLError):
                url_security.validate_url("https://example.org")
            public.assert_not_called()

    def test_doh_failure_does_not_disable_url_guard(self):
        with patch("proxy_dns.SYSTEM_RESOLVER", return_value=answer("198.18.0.9")), patch("proxy_dns.public_addresses", side_effect=socket.gaierror("failed")):
            with self.assertRaises(url_security.UnsafeURLError):
                url_security.validate_url("https://example.org")

    def test_non_public_doh_answer_is_rejected(self):
        reply = Mock()
        reply.json.return_value = {"Status": 0, "Answer": [{"type": 1, "data": "10.0.0.1"}]}
        with patch("proxy_dns.requests.get", return_value=reply), self.assertRaises(socket.gaierror):
            proxy_dns.public_addresses("example.org", 1)

    def test_file_scheme_and_system_resolver_unchanged(self):
        with self.assertRaises(url_security.UnsafeURLError):
            url_security.validate_url("file:///C:/Windows/win.ini")
        self.assertIs(socket.getaddrinfo, proxy_dns.SYSTEM_RESOLVER)


if __name__ == "__main__":
    unittest.main()
