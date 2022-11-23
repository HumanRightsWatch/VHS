from datetime import datetime

from elasticsearch_dsl import Document, Text, Keyword, Date, InnerDoc, Nested, Boolean, Object, \
    Integer, Index


class User(InnerDoc):
    uuid = Text(fields={"keyword": Keyword()})


class Attachment(InnerDoc):
    extension = Keyword(required=True)
    original_name = Text(fields={'raw': Keyword()}, required=True)
    stored_name = Text(fields={'raw': Keyword()}, required=True)
    storage_name = Text(fields={'raw': Keyword()}, required=True)
    storage_location = Text(fields={'raw': Keyword()}, required=True)
    md5 = Text(fields={'raw': Keyword()}, required=True)
    sha1 = Text(fields={'raw': Keyword()}, required=True)
    sha256 = Text(fields={'raw': Keyword()}, required=True)
    size_in_bytes = Integer(required=True)
    ssdeep = Text(fields={'raw': Keyword()})
    mimetype = Text(fields={'raw': Keyword()})
    created_at = Date(required=True)
    updated_at = Date(required=True)

    def save(self, **kwargs):
        if self.created_at is None:
            self.created_at = datetime.now()
        self.updated_at = datetime.now()
        return super().save(**kwargs)


class Entity(Document):
    owner = Keyword(required=True)
    type = Keyword()
    organization = Text(fields={'raw': Keyword()})
    query = Keyword()
    collection = Keyword()
    public = Boolean()
    created_at = Date()
    updated_at = Date()
    tags = Keyword(multi=True)
    exif = Text(analyzer='snowball')
    # exif = Nested()
    description = Text(analyzer='snowball')

    def save(self, **kwargs):
        if self.created_at is None:
            self.created_at = datetime.now()
        self.updated_at = datetime.now()
        return super().save(**kwargs)
