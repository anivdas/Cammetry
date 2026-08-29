import string
import unittest

from tts_locales import EN, LANGUAGES, TRANSLATIONS, translation_coverage, translation_missing_keys


class LocaleTests(unittest.TestCase):
    def test_all_language_packs_have_every_standard_key(self):
        missing = translation_missing_keys()
        self.assertEqual({lang: keys for lang, keys in missing.items() if keys}, {})
        self.assertTrue(all(value == 1.0 for value in translation_coverage().values()))

    def test_format_placeholders_match_english(self):
        formatter = string.Formatter()
        for language in LANGUAGES:
            for key, english in EN.items():
                translated = TRANSLATIONS[language][key]
                english_fields = {field for _, field, _, _ in formatter.parse(english) if field}
                translated_fields = {field for _, field, _, _ in formatter.parse(translated) if field}
                self.assertEqual(
                    english_fields,
                    translated_fields,
                    f"Placeholder mismatch for {language}:{key}",
                )


if __name__ == "__main__":
    unittest.main()
