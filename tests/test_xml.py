import unittest
from monaco_xml import Document, text


def item(body='<Value>1</Value><DisplayValue>one</DisplayValue><Unit>V</Unit>', key='p'):
    return f'<DataItemParameter><DestinationParameter Name="{key}"/><DataValue>{body}</DataValue></DataItemParameter>'


class XmlTests(unittest.TestCase):
    def test_edit_roundtrip_preserves_metadata(self):
        doc = Document(('<ECU xmlns="urn:monaco" ECUBaseVariant="Test"><!--keep--><ReadService Name="Read">' + item() + '</ReadService><Other flag="yes"/></ECU>').encode())
        row = doc.records[0]
        row.edit('Value', '<2 & 3>')
        self.assertEqual(text(row.fields['DisplayValue']), '<2 & 3>')
        result = doc.export()
        self.assertIn(b'<!--keep-->', result)
        self.assertIn(b'<Other flag="yes"/>', result)
        reread = Document(result)
        self.assertEqual(text(reread.records[0].fields['Value']), '<2 & 3>')
        self.assertEqual(reread.records[0].ecu.namespaceURI, 'urn:monaco')
        doc.reset()
        self.assertEqual(doc.changed, 0)
        self.assertEqual(text(row.fields['DisplayValue']), 'one')

    def test_nested_and_ambiguous(self):
        nested = '<DataItemParameter><DestinationParameter Name="parent"/>' + item(key='child') + '</DataItemParameter>'
        duplicate = item('<Value>1</Value><Value>2</Value>')
        complex_value = item('<Value><Part>1</Part></Value>')
        doc = Document('<Root>' + nested + duplicate + complex_value + '</Root>')
        self.assertEqual(len(doc.records), 1)
        self.assertEqual(doc.skipped, 3)
        self.assertEqual(doc.records[0].destination.getAttribute('Name'), 'child')

    def test_missing_value_no_creation(self):
        doc = Document('<Root>' + item('<DisplayValue>yes</DisplayValue>') + '</Root>')
        row = doc.records[0]
        row.edit('Value', 'bad')
        row.edit('DisplayValue', 'no')
        self.assertIsNone(row.fields['Value'])
        self.assertEqual(text(row.fields['DisplayValue']), 'no')

    def test_sync_can_be_disabled(self):
        row = Document('<Root>' + item() + '</Root>').records[0]
        row.edit('Value', '2', sync=False)
        self.assertEqual(text(row.fields['DisplayValue']), 'one')

    def test_utf16(self):
        data = ('<?xml version="1.0" encoding="utf-16"?><Root>' + item('<Value>Привет</Value>') + '</Root>').encode('utf-16')
        self.assertEqual(text(Document(data).records[0].fields['Value']), 'Привет')

    def test_reject_invalid_and_entities(self):
        for data in ('<broken>', '<!DOCTYPE x [<!ENTITY e "secret">]><x>&e;</x>'):
            with self.assertRaises(Exception):
                Document(data)


if __name__ == '__main__':
    unittest.main()
