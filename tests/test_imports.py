import unittest


class ImportTests(unittest.TestCase):
    def test_public_package_imports(self) -> None:
        import guardian
        from guardian import CCompiler, GUARDIANPipeline, RustCompiler

        self.assertIs(guardian.GUARDIANPipeline, GUARDIANPipeline)
        self.assertIsNotNone(CCompiler)
        self.assertIsNotNone(RustCompiler)

    def test_paper_cases_import_from_examples(self) -> None:
        from guardian.examples.paper_cases import ALL_TEST_CASES

        self.assertIn("scanf_two_ints", ALL_TEST_CASES)


if __name__ == "__main__":
    unittest.main()
