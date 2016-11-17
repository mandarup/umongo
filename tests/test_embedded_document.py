import pytest
from marshmallow import ValidationError

from umongo.data_proxy import data_proxy_factory
from umongo import Document, EmbeddedDocument, fields

from .common import BaseTest


class TestEmbeddedDocument(BaseTest):

    def test_embedded_document(self):

        @self.instance.register
        class MyEmbeddedDocument(EmbeddedDocument):
            a = fields.IntField(attribute='in_mongo_a')
            b = fields.IntField()

        embedded = MyEmbeddedDocument()
        assert embedded.to_mongo(update=True) is None
        assert not embedded.is_modified()

        @self.instance.register
        class MyDoc(Document):
            embedded = fields.EmbeddedField(MyEmbeddedDocument, attribute='in_mongo_embedded')

        MySchema = MyDoc.Schema

        # Make sure embedded document doesn't have implicit _id field
        assert '_id' not in MyEmbeddedDocument.Schema().fields
        assert 'id' not in MyEmbeddedDocument.Schema().fields

        MyDataProxy = data_proxy_factory('My', MySchema())
        d = MyDataProxy()
        d.from_mongo(data={'in_mongo_embedded': {'in_mongo_a': 1, 'b': 2}})
        assert d.dump() == {'embedded': {'a': 1, 'b': 2}}
        embedded = d.get('embedded')
        assert type(embedded) == MyEmbeddedDocument
        assert embedded.a == 1
        assert embedded.b == 2
        assert embedded.dump() == {'a': 1, 'b': 2}
        assert embedded.to_mongo() == {'in_mongo_a': 1, 'b': 2}
        assert d.to_mongo() == {'in_mongo_embedded': {'in_mongo_a': 1, 'b': 2}}

        d2 = MyDataProxy()
        d2.from_mongo(data={'in_mongo_embedded': {'in_mongo_a': 1, 'b': 2}})
        assert d == d2

        embedded.a = 3
        assert embedded.is_modified()
        assert embedded.to_mongo(update=True) == {'$set': {'in_mongo_a': 3}}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'in_mongo_a': 3, 'b': 2}}}
        embedded.clear_modified()
        assert embedded.to_mongo(update=True) is None
        assert d.to_mongo(update=True) is None

        del embedded.a
        assert embedded.to_mongo(update=True) == {'$unset': {'in_mongo_a': ''}}
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'b': 2}}}

        d.set('embedded', MyEmbeddedDocument(a=4))
        assert d.get('embedded').to_mongo(update=True) == {'$set': {'in_mongo_a': 4}}
        d.get('embedded').clear_modified()
        assert d.get('embedded').to_mongo(update=True) is None
        assert d.to_mongo(update=True) == {'$set': {'in_mongo_embedded': {'in_mongo_a': 4}}}

        embedded_doc = MyEmbeddedDocument(a=1, b=2)
        assert embedded_doc.a == 1
        assert embedded_doc.b == 2
        assert embedded_doc == {'in_mongo_a': 1, 'b': 2}
        assert embedded_doc == MyEmbeddedDocument(a=1, b=2)
        assert embedded_doc['a'] == 1
        assert embedded_doc['b'] == 2

        embedded_doc.clear_modified()
        embedded_doc.update({'b': 42})
        assert embedded_doc.is_modified()
        assert embedded_doc.a == 1
        assert embedded_doc.b == 42

        with pytest.raises(ValidationError):
            MyEmbeddedDocument(in_mongo_a=1, b=2)

        embedded_doc['a'] = 1
        assert embedded_doc.a == embedded_doc['a'] == 1
        del embedded_doc['a']
        assert embedded_doc.a is embedded_doc['a'] is None

        # Test repr readability
        repr_d = repr(MyEmbeddedDocument(a=1, b=2))
        assert 'tests.test_embedded_document.MyEmbeddedDocument' in repr_d
        assert "'in_mongo_a'" not in repr_d
        assert "'a': 1" in repr_d
        assert "'b': 2" in repr_d

        # Test unknown fields
        with pytest.raises(AttributeError):
            embedded_doc.dummy
        with pytest.raises(AttributeError):
            embedded_doc.dummy = None
        with pytest.raises(AttributeError):
            del embedded_doc.dummy
        with pytest.raises(KeyError):
            embedded_doc['dummy']
        with pytest.raises(KeyError):
            embedded_doc['dummy'] = None
        with pytest.raises(KeyError):
            del embedded_doc['dummy']

    def test_bad_embedded_document(self):

        @self.instance.register
        class MyEmbeddedDocument(EmbeddedDocument):
            a = fields.IntField()

        @self.instance.register
        class MyDoc(Document):
            e = fields.EmbeddedField(MyEmbeddedDocument)
            l = fields.ListField(fields.EmbeddedField(MyEmbeddedDocument))
            b = fields.IntField(required=True)

        with pytest.raises(ValidationError) as exc:
            MyDoc(l={})
        assert exc.value.args[0] == {'l': ['Not a valid list.']}

        with pytest.raises(ValidationError) as exc:
            MyDoc(l=True)
        assert exc.value.args[0] == {'l': ['Not a valid list.']}

        with pytest.raises(ValidationError) as exc:
            MyDoc(l="string is not a list")
        assert exc.value.args[0] == {'l': ['Not a valid list.']}

        with pytest.raises(ValidationError) as exc:
            MyDoc(l=[42])
        assert exc.value.args[0] == {'l': {0: {'_schema': ['Invalid input type.']}}}

        with pytest.raises(ValidationError) as exc:
            MyDoc(l=[{}, 42])
        assert exc.value.args[0] == {'l': {1: {'_schema': ['Invalid input type.']}}}

        with pytest.raises(ValidationError) as exc:
            k = MyDoc(b=[{}])
        assert exc.value.args[0] == {'b': ['Not a valid integer.']}

        with pytest.raises(ValidationError) as exc:
            k = MyDoc(e=[{}])
        assert exc.value.args[0] == {'e': {'_schema': ['Invalid input type.']}}

    def test_embedded_inheritance(self):
        @self.instance.register
        class EmbeddedParent(EmbeddedDocument):
            a = fields.IntField(attribute='in_mongo_a_parent')
            b = fields.IntField()

        @self.instance.register
        class EmbeddedChild(EmbeddedParent):
            a = fields.IntField(attribute='in_mongo_a_child')
            c = fields.IntField()

        @self.instance.register
        class GrandChild(EmbeddedChild):
            d = fields.IntField()

        @self.instance.register
        class OtherEmbedded(EmbeddedDocument):
            pass

        @self.instance.register
        class MyDoc(Document):
            parent = fields.EmbeddedField(EmbeddedParent)
            child = fields.EmbeddedField(EmbeddedChild)

        assert EmbeddedParent.opts.offspring == {EmbeddedChild, GrandChild}
        assert EmbeddedChild.opts.offspring == {GrandChild}
        assert GrandChild.opts.offspring == set()
        assert OtherEmbedded.opts.offspring == set()

        parent = EmbeddedParent(a=1)
        child = EmbeddedChild(a=1, b=2, c=3)
        grandchild = GrandChild(d=4)

        assert parent.to_mongo() == {'in_mongo_a_parent': 1}
        assert child.to_mongo() == {'in_mongo_a_child': 1, 'b': 2, 'c': 3, '_cls': 'EmbeddedChild'}
        assert grandchild.to_mongo() == {'d': 4, '_cls': 'GrandChild'}

        with pytest.raises(ValidationError):
            ret = MyDoc(parent=OtherEmbedded())
        with pytest.raises(ValidationError):
            ret = MyDoc(child=parent)
        doc = MyDoc(parent=child, child=child)
        assert doc.child == doc.parent

        doc = MyDoc(child={'a': 1, 'cls': 'GrandChild'},
                    parent={'cls': 'EmbeddedChild', 'a': 1})
        assert doc.child.to_mongo() == {'in_mongo_a_child': 1, '_cls': 'GrandChild'}
        assert doc.parent.to_mongo() == {'in_mongo_a_child': 1, '_cls': 'EmbeddedChild'}

        with pytest.raises(ValidationError) as exc:
            MyDoc(child={'a': 1, '_cls': 'GrandChild'})
        assert exc.value.messages == {'child': {'_schema': ['Unknown field name _cls.']}}

        # Try to build a non-child document
        with pytest.raises(ValidationError) as exc:
            MyDoc(child={'cls': 'OtherEmbedded'})
        assert exc.value.messages == {'child': ['Unknown document `OtherEmbedded`.']}

        # Test embedded child deserialization from mongo
        child = EmbeddedChild(c=69)
        doc = MyDoc(parent=child)
        mongo_data = doc.to_mongo()
        doc2 = MyDoc.build_from_mongo(mongo_data)
        assert isinstance(doc2.parent, EmbeddedChild)
        assert doc._data == doc2._data

        # Test grandchild can be passed as parent
        doc = MyDoc(parent={'cls': 'GrandChild', 'd': 2})
        assert doc.parent.to_mongo() == {'d': 2, '_cls': 'GrandChild'}