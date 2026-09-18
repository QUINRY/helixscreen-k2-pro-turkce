"""K2 Turkish catalogue, selector and bundled font consistency checks."""
# SPDX-License-Identifier: GPL-3.0-or-later
from collections import Counter
from pathlib import Path
import re
import unicodedata
import xml.etree.ElementTree as ET
import yaml

ROOT = Path(__file__).resolve().parents[2]
PACKS = ROOT / 'ui_xml/translations'
TOKENS = re.compile(r'%(?:\d+\$)?[-+0 #]*\d*(?:\.\d+)?(?:hh|h|ll|l|z|t|j)?[diuoxXfFeEgGaAcspn%]|\{[^{}]*\}')


def pack(locale):
    rows = ET.parse(PACKS / (locale + '.xml')).getroot()
    result = {row.attrib['tag']: row.attrib[locale] for row in rows}
    assert len(rows) == len(result), 'Duplicate translation keys'
    return result


def test_turkish_covers_exact_current_english():
    en, tr = pack('en'), pack('tr')
    assert len(en) == 2868
    assert en.keys() == tr.keys()
    for key, value in tr.items():
        assert value.strip(), key
        assert unicodedata.normalize('NFC', value) == value, key
        assert Counter(TOKENS.findall(en[key])) == Counter(TOKENS.findall(value)), key
    assert set('çğıöşüÇĞİÖŞÜ') <= set(''.join(tr.values()))
    assert yaml.safe_load((ROOT / 'translations/tr.yml').read_text('utf-8'))['translations'] == tr


def test_combined_pack_matches_all_ten_locales():
    root = ET.parse(PACKS / 'translations.xml').getroot()
    assert set(root.attrib['languages'].split()) == {'en','de','fr','es','ru','pt','it','zh','ja','tr'}
    for locale in root.attrib['languages'].split():
        assert {row.attrib['tag']:row.attrib[locale] for row in root} == pack(locale)


def test_wizard_keeps_all_existing_indices_and_appends_turkish():
    root = ET.parse(ROOT / 'ui_xml/wizard_language_chooser.xml').getroot()
    for index, locale in enumerate(('en','de','fr','es','ru','pt','it','zh','ja','tr')):
        button = root.find('.//lv_button[@name="lang_item_' + locale + '"]')
        assert button is not None
        assert button.find('event_cb').attrib['user_data'] == str(index)
        assert button.find('lv_image').attrib['src'] == 'flag_' + locale
    assert root.find('.//lv_button[@name="lang_item_tr"]/text_body').attrib['text'] == 'Türkçe'


def test_bundled_noto_fonts_cover_turkish_glyphs():
    fonts = list((ROOT / 'assets/fonts').glob('noto_sans*.c'))
    assert len(fonts) >= 20
    for font in fonts:
        text = font.read_text('utf-8')
        ranges = re.findall(r'\.range_start = (\d+), \.range_length = (\d+),[^\n]+\n\s*\.unicode_list = NULL', text)
        for char in 'çğıöşüÇĞİÖŞÜ':
            assert any(int(start) <= ord(char) < int(start)+int(length) for start,length in ranges), (font.name,char)
