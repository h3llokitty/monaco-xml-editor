"""Namespace-aware Monaco XML model; no network or external entity access."""
import re
from dataclasses import dataclass
from xml.dom import Node
from defusedxml.minidom import parseString


def name(node):
    return node.localName or node.nodeName.split(':')[-1]


def children(node):
    return [n for n in node.childNodes if n.nodeType == Node.ELEMENT_NODE]


def owned(root, target):
    result = []
    for node in children(root):
        if name(node) == 'DataItemParameter':
            continue
        if name(node) == target:
            result.append(node)
        result.extend(owned(node, target))
    return result


def label(node):
    if node is None:
        return 'ECU Exchange'
    for key in ('DisplayName', 'ServiceName', 'Name', 'ShortName', 'Id'):
        if node.getAttribute(key):
            return node.getAttribute(key)
    return name(node)


def text(node):
    return '' if node is None else ''.join(n.data for n in node.childNodes if n.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE))


def set_text(node, value):
    for child in list(node.childNodes):
        node.removeChild(child)
    node.appendChild(node.ownerDocument.createTextNode(value))


def natural(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.casefold(), part) for part in re.split(r'(\d+)', value))


@dataclass
class Record:
    destination: object
    fields: dict
    originals: dict
    ecu: object
    group: object

    @property
    def changed(self):
        return any(self.fields[k] is not None and text(self.fields[k]) != self.originals[k] for k in ('Value', 'DisplayValue'))

    def edit(self, key, value, sync=True):
        if self.fields[key] is None:
            return
        set_text(self.fields[key], value)
        if key == 'Value' and sync and self.fields['DisplayValue'] is not None:
            set_text(self.fields['DisplayValue'], value)


class Document:
    def __init__(self, data):
        self.dom = parseString(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        self.records, self.skipped = [], 0
        for item in self.dom.getElementsByTagName('*'):
            if name(item) != 'DataItemParameter':
                continue
            destinations = [n for n in owned(item, 'DestinationParameter') if n.hasAttribute('Name')]
            values = owned(item, 'DataValue')
            if len(destinations) != 1 or len(values) != 1:
                self.skipped += 1
                continue
            found = {k: owned(values[0], k) for k in ('Value', 'DisplayValue', 'Unit')}
            if any(len(v) > 1 or any(children(n) for n in v) for v in found.values()) or not (found['Value'] or found['DisplayValue']):
                self.skipped += 1
                continue
            fields = {k: v[0] if v else None for k, v in found.items()}
            ecu, group = None, None
            parent = item.parentNode
            while parent and parent.nodeType == Node.ELEMENT_NODE:
                kind = name(parent)
                if ecu is None and kind == 'ECU':
                    ecu = parent
                if group is None and kind != 'DataItemParameter' and (kind.endswith('Service') or kind in ('SubElement', 'RootNode', 'ECU') or any(parent.hasAttribute(k) for k in ('Name', 'ServiceName', 'DisplayName', 'Id'))):
                    group = parent
                parent = parent.parentNode
            self.records.append(Record(destinations[0], fields, {k: text(fields[k]) for k in ('Value', 'DisplayValue')}, ecu, group or item.parentNode))

    def export(self):
        data = self.dom.toxml(encoding='utf-8')
        parseString(data, forbid_dtd=True, forbid_entities=True, forbid_external=True)
        return data

    def reset(self):
        for row in self.records:
            for key in ('Value', 'DisplayValue'):
                if row.fields[key] is not None:
                    set_text(row.fields[key], row.originals[key])

    @property
    def changed(self):
        return sum(row.changed for row in self.records)
