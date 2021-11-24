import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _


class Batch(models.Model):
    """
    Model representing a download batch. Users can request the download of multiple URLs under the same batch.
    It is useful for both both experience and traceability.
    """

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
    name = models.TextField(
        max_length=512,
        help_text=_('Give a meaningful name to your download batch. (Optional)'),
        null=True,
        blank=True
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current download batch.'),
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
        editable=False,
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
    in_error = models.BooleanField(
        default=False,
        editable=False
    )
    content = models.FileField(
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
