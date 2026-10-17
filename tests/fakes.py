"""Minimal in-memory stand-ins for the Firestore client surface this app uses."""


def _filter_parts(field_filter):
    return field_filter.field_path, field_filter.op_string, field_filter.value


def _matches(data, field, op, value):
    actual = data.get(field)
    if op == "==":
        return actual == value
    if op == ">=":
        return actual is not None and actual >= value
    if op == "<=":
        return actual is not None and actual <= value
    raise NotImplementedError(f"op {op}")


class FakeDocRef:
    def __init__(self, collection, doc_id):
        self._collection = collection
        self.id = doc_id
        self.update_calls = []
        self.deleted = False

    def get(self):
        return FakeDocSnapshot(self, self._collection._docs.get(self.id))

    def update(self, fields):
        self.update_calls.append(dict(fields))
        stored = self._collection._docs.setdefault(self.id, {})
        stored.update(fields)

    def set(self, fields, merge=False):
        if merge:
            self._collection._docs.setdefault(self.id, {}).update(fields)
        else:
            self._collection._docs[self.id] = dict(fields)

    def delete(self):
        self.deleted = True
        self._collection._docs.pop(self.id, None)


class FakeDocSnapshot:
    def __init__(self, reference, data):
        self.reference = reference
        self.id = reference.id
        self._data = data

    @property
    def exists(self):
        return self._data is not None

    def to_dict(self):
        return dict(self._data) if self._data is not None else None


class FakeQuery:
    def __init__(self, collection, docs):
        self._collection = collection
        self._docs = docs  # list of (doc_id, data)

    def where(self, filter):
        field, op, value = _filter_parts(filter)
        kept = [(i, d) for i, d in self._docs if _matches(d, field, op, value)]
        return FakeQuery(self._collection, kept)

    def order_by(self, field, direction="ASCENDING"):
        reverse = str(direction).upper().startswith("DESC")
        kept = sorted(self._docs, key=lambda item: item[1].get(field), reverse=reverse)
        return FakeQuery(self._collection, kept)

    def limit(self, n):
        return FakeQuery(self._collection, self._docs[:n])

    def select(self, fields):
        kept = [(i, {k: d[k] for k in fields if k in d}) for i, d in self._docs]
        return FakeQuery(self._collection, kept)

    def stream(self):
        for doc_id, _ in self._docs:
            yield FakeDocSnapshot(self._collection.document(doc_id),
                                  self._collection._docs.get(doc_id))


class FakeCollection:
    def __init__(self, docs=None):
        self._docs = dict(docs or {})
        self._refs = {}
        self._auto_id = 0

    def document(self, doc_id):
        if doc_id not in self._refs:
            self._refs[doc_id] = FakeDocRef(self, doc_id)
        return self._refs[doc_id]

    def where(self, filter):
        return FakeQuery(self, list(self._docs.items())).where(filter=filter)

    def order_by(self, field, direction="ASCENDING"):
        return FakeQuery(self, list(self._docs.items())).order_by(field, direction)

    def select(self, fields):
        return FakeQuery(self, list(self._docs.items())).select(fields)

    def stream(self):
        return FakeQuery(self, list(self._docs.items())).stream()

    def add(self, data):
        self._auto_id += 1
        doc_id = f"auto-{self._auto_id}"
        self._docs[doc_id] = dict(data)
        return None, self.document(doc_id)


class FakeDB:
    def __init__(self, collections=None):
        self._collections = {name: FakeCollection(docs)
                             for name, docs in (collections or {}).items()}

    def collection(self, name):
        if name not in self._collections:
            self._collections[name] = FakeCollection()
        return self._collections[name]

    def collections(self):
        return list(self._collections.values())

    def get_all(self, refs):
        for ref in refs:
            yield ref.get()
