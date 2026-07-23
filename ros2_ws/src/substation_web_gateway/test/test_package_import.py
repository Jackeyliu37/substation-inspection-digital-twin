import unittest


class TestPackageImport(unittest.TestCase):
    def test_package_root_is_importable_without_web_runtime(self) -> None:
        import substation_web_gateway

        self.assertTrue(substation_web_gateway.__doc__)
