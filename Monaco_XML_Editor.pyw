"""Offline Monaco DataHandling XML editor."""
import os
from pathlib import Path
import sys
import tempfile
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from monaco_xml import Document, label, natural, text


class Editor:
    def __init__(self, root):
        self.root, self.document, self.path = root, None, None
        root.title('Monaco DataHandling XML Editor')
        root.geometry('1150x740')
        root.minsize(750, 480)
        self.sync = tk.BooleanVar(value=True)
        self.order = tk.StringVar(value='А → Я / A → Z')
        bar = ttk.Frame(root, padding=10)
        bar.pack(fill='x')
        ttk.Button(bar, text='Открыть XML', command=self.open).pack(side='left', padx=3)
        self.save_button = ttk.Button(bar, text='Сохранить как…', command=self.save, state='disabled')
        self.save_button.pack(side='left', padx=3)
        self.reset_button = ttk.Button(bar, text='Отменить изменения', command=self.reset, state='disabled')
        self.reset_button.pack(side='left', padx=3)
        order = ttk.Combobox(bar, textvariable=self.order, values=('А → Я / A → Z', 'Я → А / Z → A', 'Как в XML'), state='readonly', width=18)
        order.pack(side='left', padx=8)
        order.bind('<<ComboboxSelected>>', lambda e: self.render())
        ttk.Checkbutton(bar, text='Value → DisplayValue', variable=self.sync).pack(side='left')
        self.filename = ttk.Label(root, text='Откройте Monaco ECU Exchange XML.', padding=(12, 4))
        self.filename.pack(fill='x')
        self.status = ttk.Label(root, padding=10)
        self.status.pack(side='bottom', fill='x')
        frame = ttk.Frame(root)
        frame.pack(fill='both', expand=True)
        self.tree = ttk.Treeview(frame, columns=('value', 'display', 'unit'), selectmode='browse')
        self.tree.heading('#0', text='ECU / группа / DestinationParameter')
        self.tree.column('#0', width=510, minwidth=260)
        for key, title in [('value', 'Value'), ('display', 'DisplayValue'), ('unit', 'Unit')]:
            self.tree.heading(key, text=title)
            self.tree.column(key, width=160 if key != 'unit' else 90)
        scroll = ttk.Scrollbar(frame, orient='vertical', command=self.tree.yview)
        horizontal = ttk.Scrollbar(frame, orient='horizontal', command=self.tree.xview)
        self.tree.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tree.grid(row=0, column=0, sticky='nsew')
        scroll.grid(row=0, column=1, sticky='ns')
        horizontal.grid(row=1, column=0, sticky='ew')
        self.tree.tag_configure('changed', background='#fff0bc', foreground='#222222')
        self.tree.bind('<Double-1>', self.edit)
        self.tree.bind('<Return>', self.edit)
        root.protocol('WM_DELETE_WINDOW', self.close)
        root.bind('<Control-o>', lambda e: self.open())
        root.bind('<Control-s>', lambda e: self.save())
        self.rows = {}

    def discard(self):
        return not self.document or not self.document.changed or messagebox.askyesno('Несохранённые изменения', 'Продолжить и отменить несохранённые изменения?', parent=self.root)

    def open(self):
        if not self.discard():
            return
        path = filedialog.askopenfilename(filetypes=[('XML', '*.xml'), ('Все файлы', '*.*')])
        if not path:
            return
        try:
            document = Document(Path(path).read_bytes())
        except Exception as exc:
            messagebox.showerror('Не удалось открыть XML', str(exc))
            return
        self.document, self.path = document, Path(path)
        self.filename.config(text=str(self.path))
        self.render()
        if document.skipped:
            messagebox.showwarning('Пропущенные записи', f'Неоднозначных или неподдерживаемых записей: {document.skipped}. Они сохраняются без изменений.')

    def render(self):
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        if not self.document:
            return
        groups = {}
        for row in self.document.records:
            groups.setdefault(row.ecu, {}).setdefault(row.group, []).append(row)
        for ecu, blocks in groups.items():
            title = (ecu.getAttribute('ECUBaseVariant') or ecu.getAttribute('LogicalLinkName') or label(ecu)) if ecu else label(None)
            eid = self.tree.insert('', 'end', text=title, open=True)
            for group, rows in blocks.items():
                path, current = [], group
                while current is not None and current is not ecu and current.nodeType == current.ELEMENT_NODE:
                    path.insert(0, label(current))
                    current = current.parentNode
                gid = self.tree.insert(eid, 'end', text=' / '.join(path) or label(group), open=True)
                if self.order.get() != 'Как в XML':
                    rows = sorted(rows, key=lambda r: (natural(r.destination.getAttribute('Name')), natural(r.destination.getAttribute('Index'))), reverse=self.order.get().startswith('Я'))
                for row in rows:
                    title = row.destination.getAttribute('Name')
                    if row.destination.hasAttribute('Index'):
                        title += ' [Index: ' + row.destination.getAttribute('Index') + ']'
                    iid = self.tree.insert(gid, 'end', text=title)
                    self.rows[iid] = row
                    self.refresh(iid)
        self.update_status()

    def refresh(self, iid):
        row = self.rows[iid]
        self.tree.item(iid, values=[text(row.fields[k]) if row.fields[k] is not None else '—' for k in ('Value', 'DisplayValue', 'Unit')], tags=('changed',) if row.changed else ())

    def update_status(self):
        doc = self.document
        self.status.config(text=f'{len(doc.records)} параметров • изменено: {doc.changed} • пропущено: {doc.skipped}   |   Двойной щелчок или Enter — редактировать')
        self.save_button.config(state='normal' if doc.records else 'disabled')
        self.reset_button.config(state='normal' if doc.changed else 'disabled')

    def edit(self, event=None):
        iid = self.tree.identify_row(event.y) if event and event.keysym != 'Return' else self.tree.focus()
        if iid not in self.rows:
            return
        row = self.rows[iid]
        dialog = tk.Toplevel(self.root)
        dialog.title(row.destination.getAttribute('Name'))
        dialog.transient(self.root)
        dialog.resizable(True, False)
        variables, entries = {}, {}
        for index, key in enumerate(('Value', 'DisplayValue')):
            ttk.Label(dialog, text=key).grid(row=index, column=0, padx=12, pady=12)
            variables[key] = tk.StringVar(value=text(row.fields[key]))
            entries[key] = ttk.Entry(dialog, textvariable=variables[key], width=55, state='normal' if row.fields[key] is not None else 'disabled')
            entries[key].grid(row=index, column=1, padx=12, pady=12, sticky='ew')
        def synchronize(*args):
            if self.sync.get() and row.fields['DisplayValue'] is not None:
                variables['DisplayValue'].set(variables['Value'].get())
        variables['Value'].trace_add('write', synchronize)
        def apply():
            for key in variables:
                row.edit(key, variables[key].get(), sync=False)
            self.refresh(iid)
            self.update_status()
            dialog.destroy()
        buttons = ttk.Frame(dialog)
        buttons.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(buttons, text='Применить', command=apply).pack(side='left', padx=6)
        ttk.Button(buttons, text='Отмена', command=dialog.destroy).pack(side='left', padx=6)
        dialog.columnconfigure(1, weight=1)
        dialog.bind('<Return>', lambda e: apply())
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.grab_set()
        entries['Value' if row.fields['Value'] is not None else 'DisplayValue'].focus_set()

    def reset(self):
        if self.document and messagebox.askyesno('Отменить изменения', 'Восстановить значения на момент открытия или последнего сохранения?'):
            self.document.reset()
            self.render()

    def save(self):
        if not self.document or not self.document.records:
            return
        path = filedialog.asksaveasfilename(defaultextension='.xml', initialfile=self.path.stem + '_edited.xml', filetypes=[('XML', '*.xml')])
        if not path:
            return
        temporary = None
        try:
            data = self.document.export()
            with tempfile.NamedTemporaryFile(dir=Path(path).parent, prefix='.monaco-', suffix='.tmp', delete=False) as output:
                temporary = output.name
                output.write(data)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, path)
            temporary = None
            for row in self.document.records:
                row.originals = {k: text(row.fields[k]) for k in ('Value', 'DisplayValue')}
            self.path = Path(path)
            self.filename.config(text=str(self.path))
            self.render()
            messagebox.showinfo('Сохранено', f'XML сохранён:\n{path}')
        except Exception as exc:
            messagebox.showerror('Не удалось сохранить XML', str(exc))
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def close(self):
        if self.discard():
            self.root.destroy()


def main():
    root = tk.Tk()
    Editor(root)
    if '--smoke-test' in sys.argv:
        root.update()
        root.destroy()
    else:
        root.mainloop()


if __name__ == '__main__':
    main()
