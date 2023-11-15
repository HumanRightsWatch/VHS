from django.core.management import BaseCommand

from video_downloading_platform.core.models import Batch


class Command(BaseCommand):
    help = 'Delete the specified collection'

    def add_arguments(self, parser):
        parser.add_argument('collection_id', type=str)

    def handle(self, *args, **options):
        collection_id = options.get('collection_id', None)
        if collection_id:
            try:
                collection = Batch.objects.get(id=collection_id)
                collection.delete()
                self.stdout.write(self.style.SUCCESS(f'{collection_id} successfully deleted.'))
            except Exception as e:
                print(e)
