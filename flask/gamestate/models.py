from peewee import Model, UUIDField, CharField, Proxy, IntegerField, FloatField, TextField, AutoField

database_proxy = Proxy()


class StoredGame(Model):
    uuid = UUIDField(primary_key=True)
    name = CharField()
    deck = CharField()

    class Meta:
        database = database_proxy


class StoredStory(Model):
    """A story of a game: waiting in the backlog ('queued') or already estimated ('estimated')"""
    pk = AutoField()
    game = CharField(index=True)  # StoredGame.uuid, as a string
    story_id = IntegerField()  # the id shown to the clients, unique in a game
    status = CharField()
    position = IntegerField()  # order in the backlog, or in the list of estimated stories
    name = CharField(default='')
    ref = CharField(null=True)  # key of the issue in a tracker, such as ABC-123
    url = CharField(null=True)
    estimate = FloatField(null=True)
    votes = TextField(null=True)  # JSON: [{'player': str, 'card': number}]

    class Meta:
        database = database_proxy


def create_tables():
    database_proxy.create_tables([StoredGame, StoredStory], safe=True)
