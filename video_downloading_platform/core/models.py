import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _
from django_q.humanhash import HumanHasher
from django.core.validators import URLValidator


def _generate_random_name():
    hh = HumanHasher()
    name, _ = hh.uuid()
    return str(name)


def _validate_urls(value):
    urls = value.splitlines()
    uv = URLValidator()
    for url in urls:
        uv(url)


class Batch(models.Model):
    """
    Model representing a download batch. Users can request the download of multiple URLs under the same batch.
    It is useful for both both experience and traceability.
    """

    class Meta:
        ordering = ['-updated_at']

    OPEN = 'OPEN'
    CLOSED = 'CLOSED'
    BATCH_STATUS = [
        (OPEN, _('Open')),
        (CLOSED, _('Closed'))
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_('Unique identifier of your download batch.'),
        editable=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Creation date of your download batch.'),
        editable=False
    )
    updated_at = models.DateTimeField(
        help_text=_('Latest modification of your download batch.'),
        auto_now=True
    )
    status = models.CharField(
        max_length=16,
        choices=BATCH_STATUS,
        default=OPEN,
    )
    name = models.CharField(
        max_length=512,
        help_text=_('Give a meaningful name to your download batch.'),
        default=_generate_random_name
    )
    description = models.TextField(
        help_text=_('Say a bit more about it. (Optional)'),
        default=_('No description')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current download batch.'),
        related_name='my_batches',
        editable=False
    )

    def close(self):
        self.status = Batch.CLOSED
        self.save()

    def start(self):
        for download_request in self.download_requests.filter(status=DownloadRequest.CREATED):
            download_request.start()

    def start_and_close(self):
        self.start()
        self.close()

    @staticmethod
    def get_users_batches(user):
        try:
            return Batch.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return []

    @staticmethod
    def get_users_open_batches(user):
        try:
            return Batch.objects.filter(owner=user, status=Batch.OPEN)
        except Exception as e:
            print(e)
        return []

    def __str__(self):
        return self.name

class BatchRequest(models.Model):
    class Meta:
        managed = False

    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
    )
    urls = models.TextField(
        validators=[_validate_urls]
    )

class DownloadRequest(models.Model):
    CREATED = 'CREATED'
    ENQUEUED = 'ENQUEUED'
    PROCESSING = 'PROCESSING'
    POST_PROCESSING = 'POST_PROCESSING'
    SUCCEEDED = 'SUCCEEDED'
    CANCELLED = 'CANCELLED'
    FAILED = 'FAILED'
    DOWNLOAD_REQUEST_STATUS = [
        (CREATED, _('Created')),
        (ENQUEUED, _('Enqueued')),
        (PROCESSING, _('Processing')),
        (POST_PROCESSING, _('Post processing')),
        (SUCCEEDED, _('Succeeded')),
        (CANCELLED, _('Cancelled')),
        (FAILED, _('Failed')),
    ]

    VIDEO = 'VIDEO'
    AUDIO = 'AUDIO'
    WEB_PAGE = 'WEP_PAGE'
    REQUEST_TYPE = [
        (VIDEO, _('Video')),
        (AUDIO, _('Audio')),
        (WEB_PAGE, _('Web page')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_('Unique identifier of the current download request.'),
        editable=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Creation date of the current download request.'),
        editable=False
    )
    updated_at = models.DateTimeField(
        help_text=_('Latest modification of the current download request.'),
        auto_now=True
    )
    status = models.CharField(
        max_length=16,
        choices=DOWNLOAD_REQUEST_STATUS,
        default=CREATED,
    )
    type = models.CharField(
        max_length=16,
        choices=REQUEST_TYPE,
        default=VIDEO,
        editable=False
    )
    url = models.URLField(
        help_text=_('The URL of the video to download.')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current download request.'),
        editable=False
    )
    batch = models.ForeignKey(
        Batch,
        on_delete=models.CASCADE,
        related_name='download_requests'
    )

    def start(self):
        self.status = DownloadRequest.ENQUEUED
        self.save()
        # Start the downloading task
        pass

    @staticmethod
    def get_users_requests(user):
        try:
            return DownloadRequest.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return []

    def __str__(self):
        return f'{self.owner} - {self.url}'


class DownloadReport(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_('Unique identifier of the current downloaded content.'),
        editable=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Creation date of the current downloaded content.'),
        editable=False
    )
    updated_at = models.DateTimeField(
        help_text=_('Latest modification of the current downloaded content.'),
        auto_now=True
    )
    in_error = models.BooleanField(
        default=False,
        editable=False
    )
    error_message = models.TextField(
        null=True,
        blank=True
    )
    download_request = models.ForeignKey(
        DownloadRequest,
        on_delete=models.CASCADE,
        related_name='report'
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current download request.'),
        editable=False
    )


class DownloadedContent(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_('Unique identifier of the current downloaded content.'),
        editable=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Creation date of the current downloaded content.'),
        editable=False
    )
    updated_at = models.DateTimeField(
        help_text=_('Latest modification of the current downloaded content.'),
        auto_now=True
    )
    sha256 = models.CharField(
        max_length=64,
    )
    content = models.FileField(
        null=True,
        blank=True
    )
    metadata = models.JSONField(
        null=True,
        blank=True
    )
    post_processing_result = models.JSONField(
        null=True,
        blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current download request.'),
        editable=False
    )

    @staticmethod
    def get_users_downloaded_content(user):
        try:
            return DownloadedContent.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return []
