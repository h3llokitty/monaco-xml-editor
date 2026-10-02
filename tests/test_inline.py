import runpy
from pathlib import Path
import sys
import unittest
from monaco_xml import Document, text


@unittest.skipUnless(sys.platform == 'win32', 'GUI integration runs on Windows')
class InlineTests(unittest.TestCase):
    def setUp(self):
        import tkinter as tk
        editor = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'Monaco_XML_Editor.pyw'))['Editor']
        self.root = tk.Tk()
        self.app = editor(self.root)
        self.app.document = Document('<ECU><DataItemParameter><DestinationParameter Name="x"/><DataValue><Value>1</Value><DisplayValue>one</DisplayValue></DataValue></DataItemParameter></ECU>')
        self.app.render()
        self.root.update()
        self.iid = next(iter(self.app.rows))
        self.row = self.app.rows[self.iid]

    def tearDown(self):
        self.root.destroy()

    def enter(self, value):
        entry = self.app.cell_editor[0]
        entry.delete(0, 'end')
        entry.insert(0, value)

    def test_commit_cancel_and_tab(self):
        self.app.start_edit(self.iid, '#1')
        self.enter('25')
        self.app.next_cell(1)
        self.assertEqual(text(self.row.fields['Value']), '25')
        self.assertEqual(text(self.row.fields['DisplayValue']), '25')
        self.assertEqual(self.app.cell_editor[2], 'DisplayValue')
        self.enter('cancelled')
        self.app.finish_edit(commit=False)
        self.assertEqual(text(self.row.fields['DisplayValue']), '25')
        self.app.start_edit(self.iid, '#2')
        self.enter('formatted')
        self.app.finish_edit()
        self.assertEqual(text(self.row.fields['Value']), '25')
        self.assertEqual(text(self.row.fields['DisplayValue']), 'formatted')

    def test_unchanged_and_sync_off(self):
        self.app.start_edit(self.iid, '#1')
        self.app.finish_edit()
        self.assertEqual(text(self.row.fields['DisplayValue']), 'one')
        self.app.sync.set(False)
        self.app.start_edit(self.iid, '#1')
        self.enter('2')
        self.app.finish_edit()
        self.assertEqual(text(self.row.fields['Value']), '2')
        self.assertEqual(text(self.row.fields['DisplayValue']), 'one')
