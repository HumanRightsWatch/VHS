from django.core.management import BaseCommand

from video_downloading_platform.core.models import DownloadRequest
from video_downloading_platform.core.tasks import index_download_request


class Command(BaseCommand):
    help = 'Index the given download request'

    def add_arguments(self, parser):
        parser.add_argument('request_ids', nargs='+', type=str)

    def handle(self, *args, **options):
        for request_id in options['request_ids']:
            if request_id == '*':
                for request in DownloadRequest.objects.all():
                    index_download_request(request)
                    self.stdout.write(self.style.SUCCESS(f'Successfully indexed the download request {request.id}'))

            else:
                index_download_request(request)
                self.stdout.write(self.style.SUCCESS(f'Successfully indexed the download request {request_id}'))

#http://localhost:8000/request/03e2c835-6183-4ff7-970b-58dad8b72b9e/hide
