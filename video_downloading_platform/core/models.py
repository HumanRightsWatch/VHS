import uuid

from django.conf import settings
from django.db import models
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django_q.humanhash import HumanHasher
from django.core.validators import URLValidator
from django_q.tasks import async_task


def _generate_random_name():
    hh = HumanHasher()
    name, _ = hh.uuid()
    return str(name)


def _validate_urls(value):
    urls = value.splitlines()
    uv = URLValidator()
    for url in urls:
        striped_url = url.strip()
        if len(striped_url) > 0:
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
    ARCHIVED = 'ARCHIVED'
    BATCH_STATUS = [
        (OPEN, _('Open')),
        (CLOSED, _('Closed')),
        (ARCHIVED, _('Archived')),
    ]

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        help_text=_('Unique identifier of your collection.'),
        editable=False
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text=_('Creation date of your collection.'),
        editable=False
    )
    updated_at = models.DateTimeField(
        help_text=_('Latest modification of your collection.'),
        auto_now=True
    )
    status = models.CharField(
        max_length=16,
        choices=BATCH_STATUS,
        default=OPEN,
    )
    name = models.CharField(
        max_length=512,
        help_text=_('Give a meaningful name to your collection.'),
        default=_generate_random_name
    )
    description = models.TextField(
        help_text=_('Say a bit more about it. (Optional)'),
        default=_('No description')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current collection.'),
        related_name='my_batches',
        editable=False
    )

    def close(self):
        self.status = Batch.CLOSED
        self.save()

    def archive(self):
        self.status = Batch.ARCHIVED
        for download_request in self.download_requests.all():
            for report in download_request.report.all():
                if report.archive:
                    report.archive.delete()
                for downloaded_content in report.downloadedcontent_set.all():
                    if downloaded_content.content:
                        downloaded_content.content.delete()
        self.save()

    def start(self):
        for download_request in self.download_requests.filter(status=DownloadRequest.Status.CREATED):
            download_request.start()

    def start_and_close(self):
        self.start()
        self.close()

    @staticmethod
    def get_users_batches(user):
        try:
            user_groups = user.groups.values_list('name', flat=True)
            print(user_groups)
            if 'admin' in user_groups:
                return Batch.objects.all()
            else:
                return Batch.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return None

    @staticmethod
    def get_users_open_batches(user):
        return Batch._get_users_batches(user, Batch.OPEN)

    @staticmethod
    def get_users_closed_batches(user):
        return Batch._get_users_batches(user, Batch.CLOSED)

    @staticmethod
    def get_users_archived_batches(user):
        return Batch._get_users_batches(user, Batch.ARCHIVED)

    @staticmethod
    def _get_users_batches(user, status):
        try:
            user_groups = user.groups.values_list('name', flat=True)
            print(user_groups)
            if 'admin' in user_groups:
                return Batch.objects.filter(status=status)
            else:
                return Batch.objects.filter(owner=user, status=status)
        except Exception as e:
            print(e)
        return None

    @property
    def status_class(self):
        if self.status == Batch.OPEN:
            return 'success'
        if self.status == Batch.CLOSED:
            return 'primary'
        if self.status == Batch.ARCHIVED:
            return 'secondary'

    def __str__(self):
        return self.name


class BatchRequest(models.Model):
    class Meta:
        managed = False

    batch = models.ForeignKey(
        Batch,
        on_delete=models.DO_NOTHING,
        null=True,
        blank=True
    )
    urls = models.TextField(
        help_text=_('One URL per line'),
        validators=[_validate_urls]
    )


class DownloadRequest(models.Model):
    class Status(models.TextChoices):
        CREATED = 'CREATED', _('Created')
        ENQUEUED = 'ENQUEUED', _('Enqueued')
        PROCESSING = 'PROCESSING', _('Processing')
        POST_PROCESSING = 'POST_PROCESSING', _('Post processing')
        SUCCEEDED = 'SUCCEEDED', _('Succeeded')
        CANCELLED = 'CANCELLED', _('Cancelled')
        FAILED = 'FAILED', _('Failed')

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
        choices=Status.choices,
        default=Status.CREATED,
    )
    type = models.CharField(
        max_length=16,
        choices=REQUEST_TYPE,
        default=VIDEO,
        editable=False
    )
    message = models.TextField(
        null=True,
        blank=True
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
        from video_downloading_platform.core.tasks import run_download_request
        self.status = DownloadRequest.Status.ENQUEUED
        self.save()
        async_task(run_download_request, self.id)

    @staticmethod
    def get_users_requests(user):
        try:
            return DownloadRequest.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return None

    def __str__(self):
        return f'{self.owner} - {self.url}'


def _get_zip_upload_dir(instance, filename):
    owner_id = instance.owner.id
    download_request_id = instance.download_request.id
    return f'{owner_id}/{download_request_id}/{instance.id}.archive.zip'


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
    archive = models.FileField(
        upload_to=_get_zip_upload_dir,
        max_length=512,
        null=True,
        blank=True
    )

    def get_thumbnail(self):
        try:
            content = self.downloadedcontent_set.filter(mime_type__in=['image/jpeg', 'image/webp']).first()
            if content:
                url = reverse_lazy("get_downloaded_file", kwargs={'content_id': content.id})
                return url
        except Exception as e:
            print(e)
        return None


def _get_upload_dir(instance, filename):
    owner_id = instance.owner.id
    download_request_id = instance.download_report.download_request.id
    return f'{owner_id}/{download_request_id}/{instance.id}'


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
    mime_type = models.CharField(
        max_length=64,
    )
    name = models.CharField(
        max_length=512,
    )
    content = models.FileField(
        upload_to=_get_upload_dir,
        max_length=512,
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
    download_report = models.ForeignKey(
        DownloadReport,
        on_delete=models.CASCADE,
        editable=False
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
        return None
