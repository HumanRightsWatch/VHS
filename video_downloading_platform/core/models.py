import logging
import tempfile
import uuid
import os
import re
from datetime import timedelta
import string
import random

import yt_dlp as youtube_dl
from django.conf import settings
from django.core.validators import URLValidator
from django.db import models
from django.db.models.signals import pre_delete
from django.dispatch import receiver
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django_q.humanhash import HumanHasher
from django_q.models import Schedule
from django_q.tasks import async_task, schedule
from elasticsearch_dsl import Index
from gallery_dl.extractor import find as gdl_find_extractors
from taggit.managers import TaggableManager
from taggit.models import GenericUUIDTaggedItemBase, TaggedItemBase

from video_downloading_platform.core.utils import transform_hl_results

logger = logging.getLogger(__name__)


class UUIDTaggedItem(GenericUUIDTaggedItemBase, TaggedItemBase):
    # If you only inherit GenericUUIDTaggedItemBase, you need to define
    # a tag field. e.g.
    # tag = models.ForeignKey(Tag, related_name="uuid_tagged_items", on_delete=models.CASCADE)

    class Meta:
        verbose_name = _("Tag")
        verbose_name_plural = _("Tags")


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


def _random_id_16():
    return ''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(16))

class BatchTeam(models.Model):
    contributors = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='teams',
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING
    )

    def get_absolute_url(self):
        return reverse('batch_details', kwargs={'batch_id': self.batch.first().id})

    @staticmethod
    def get_my_teams_as_contrib(user):
        return BatchTeam.objects.filter(contributors=user)


class Batch(models.Model):
    """
    Model representing a download batch. Users can request the download of multiple URLs under the same batch.
    It is useful for both experience and traceability.
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
        verbose_name=_('name'),
        help_text=_('Give a meaningful name to your collection. We suggest the name of your project, date, your '
                    'initials separated by underscores. For example Ariha_Syria_20_Nov_2022_GI.'),
        default=''
        # default=_generate_random_name
    )
    description = models.TextField(
        help_text=_('Add more details about the project here.'),
        default=_('No description')
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        help_text=_('Who owns the current collection.'),
        related_name='my_batches',
        editable=False
    )
    tags = TaggableManager(through=UUIDTaggedItem, blank=True)
    es_index = models.CharField(
        max_length=16,
        default=_random_id_16,
        editable=False,
    )
    indexed = models.BooleanField(default=False)
    team = models.ForeignKey(
        BatchTeam,
        on_delete=models.CASCADE,
        null=True,
        related_name='batch'
    )

    def close(self):
        self.status = Batch.CLOSED
        self.save()

    def reopen(self):
        self.status = Batch.OPEN
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

    def get_es_index(self):
        return f'c.{self.es_index}'

    @property
    def indexed_data(self):
        query = {
            "query": {
                "query_string": {
                    "query": "*"
                }
            },
            "_source": [
                "collection_id", "collection_name", "created_at", "mimetype", "origin", "owner", "platform",
                "post.description", "post.title", "post.upload_date", "post.uploader", "sha256", "stats.comment_count",
                "stats.like_count", "stats.view_count", "status", "tags", "thumbnail_content_id", "type", "is_hidden",
                "request_id"
            ],
            "sort": {"created_at": "desc"},
            "size": 10000,
        }
        from elasticsearch import Elasticsearch
        es = Elasticsearch(settings.ELASTICSEARCH_HOSTS)
        try:
            print(query)
            raw_results = es.search(index=self.get_es_index(), body=query)
            results = transform_hl_results(raw_results)
            return results
        except Exception as e:
            logger.exception(e)
            return []

    @property
    def failed_download_requests(self):
        return self.download_requests.exclude(status=DownloadRequest.Status.SUCCEEDED)

    @staticmethod
    def get_users_batches(user):
        try:
            user_groups = user.groups.values_list('name', flat=True)
            if 'admin' in user_groups:
                return Batch.objects.all()
            else:
                open_batches = []
                teams = BatchTeam.get_my_teams_as_contrib(user).all()
                for team in teams:
                    batch = team.batch.first()
                    open_batches.append(batch)
                open_batches.extend(Batch.objects.filter(owner=user).all())
                return open_batches
        except Exception as e:
            print(e)
        return None

    @staticmethod
    def get_users_batch_es_indexes(user):
        try:
            user_groups = user.groups.values_list('name', flat=True)
            if 'admin' in user_groups:
                return ['c.*']
            else:
                # limit to the 100 first batches to prevent exceeding ES URL max length
                # since indexes are passed in the URL during the query
                open_batches = Batch.get_users_open_batches(user)[:100]
                return [
                    b.get_es_index() for b in open_batches if b.indexed
                ]
        except Exception as e:
            print(e)
        return []

    @staticmethod
    def get_users_open_batches(user):
        _batches = []
        teams = BatchTeam.get_my_teams_as_contrib(user).all()
        for team in teams:
            batch = team.batch.first()
            _batches.append(batch.id)
        _batches.extend([b.id for b in Batch._get_users_batches(user, Batch.OPEN).all()])
        return Batch.objects.filter(id__in=_batches)

    @staticmethod
    def get_users_closed_batches(user):
        return Batch._get_users_batches(user, Batch.CLOSED)

    @staticmethod
    def get_users_archived_batches(user):
        return Batch._get_users_batches(user, Batch.ARCHIVED)

    def is_shared_with_me(self, user):
        return user in self.team.contributors

    @staticmethod
    def _get_users_batches(user, status):
        try:
            user_groups = user.groups.values_list('name', flat=True)
            if 'admin' in user_groups:
                return Batch.objects.filter(status=status)
            else:
                _batches = []
                teams = BatchTeam.get_my_teams_as_contrib(user).all()
                for team in teams:
                    batch = team.batch.first()
                    if batch.status == status:
                        _batches.append(batch.id)
                _batches.extend([b.id for b in Batch.objects.filter(owner=user, status=status).all()])
                _batches = list(set(_batches))
                return Batch.objects.filter(id__in=_batches)
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

    @property
    def url_count(self):
        return self.download_requests.count()

    def __str__(self):
        return self.name


class DownloadRequest(models.Model):
    class Meta:
        ordering = ['-updated_at']

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
    GALLERY = 'GALLERY'
    WEB_PAGE = 'WEP_PAGE'
    AUTOMATIC = 'AUTOMATIC'
    UPLOAD = 'UPLOAD'
    REQUEST_TYPE = [
        (AUTOMATIC, _('Automatic')),
        (VIDEO, _('Video')),
        # (AUDIO, _('Audio')),
        (GALLERY, _('Gallery')),
        # (WEB_PAGE, _('Webpage')),
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
    is_hidden = models.BooleanField(
        default=False
    )
    content_warning = models.TextField(
        help_text=_('Add a content warning.'),
        null=True,
        blank=True
    )
    tags = TaggableManager(through=UUIDTaggedItem, blank=True)

    def get_es_index(self):
        return self.batch.get_es_index()

    @property
    def indexed_data(self):
        query = {
            "query": {
                "query_string": {
                    "query": f'request_id: "{self.id}"'
                }
            },
            "_source": [
                "collection_id", "collection_name", "created_at", "mimetype", "origin", "owner", "platform",
                "post.description", "post.title", "post.upload_date", "post.uploader", "sha256", "stats.comment_count",
                "stats.like_count", "stats.view_count", "status", "tags", "thumbnail_content_id", "type", "is_hidden",
                "request_id"
            ],
            "sort": {"created_at": "desc"},
            "size": 10000,
        }
        from elasticsearch import Elasticsearch
        es = Elasticsearch(settings.ELASTICSEARCH_HOSTS)
        try:
            raw_results = es.search(index=self.get_es_index(), body=query)
            results = transform_hl_results(raw_results)
            return results
        except Exception as e:
            logger.exception(e)
            return []

    def start(self):
        from video_downloading_platform.core.tasks import run_download_video_request, run_download_gallery_request, run_download_from_telegram
        self.status = DownloadRequest.Status.ENQUEUED
        self.save()

        match = re.match(r"^https:\/\/t\.me\/(?P<user_id>.*?)\/(?P<post_id>[0-9]+)", self.url, re.IGNORECASE)

        if match:
            s_id = str(self.id)
            async_task(run_download_from_telegram, s_id)
        elif self.type == DownloadRequest.VIDEO:
            # run_download_video_request(self.id)
            s_id = str(self.id)
            async_task(run_download_video_request, s_id)
        elif self.type == DownloadRequest.GALLERY:
            # run_download_gallery_request(self.id)
            s_id = str(self.id)
            async_task(run_download_gallery_request, s_id)

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


def _get_request_types_to_run(url, request_type):
    suitable_for_ydl = False
    suitable_for_gdl = False
    suitable_for_tdl = False
    if request_type == DownloadRequest.AUTOMATIC:
        # Suitable for Youtube DL?
        with tempfile.TemporaryDirectory() as tmp_dir:
            options = {
                'outtmpl': f'{tmp_dir}/%(id)s.%(ext)s',
                'format': 'best'
            }
            try:
                with youtube_dl.YoutubeDL(options) as ydl:
                    ydl.extract_info(url, download=False, process=False)
                    suitable_for_ydl = True
            except Exception:
                suitable_for_ydl = False

        # Suitable for Gallery DL?
        suitable_for_gdl = gdl_find_extractors(url) is not None

        # Suitable for Telegram downloader
        match = re.match(r"^https:\/\/t\.me\/(?P<user_id>.*?)\/(?P<post_id>[0-9]+)", url, re.IGNORECASE)
        suitable_for_tdl = bool(match)
    elif request_type == DownloadRequest.VIDEO:
        suitable_for_ydl = True
    elif request_type == DownloadRequest.GALLERY:
        suitable_for_gdl = True

    request_types = []
    if suitable_for_ydl:
        request_types.append(DownloadRequest.VIDEO)
    if suitable_for_gdl:
        request_types.append(DownloadRequest.GALLERY)

    if suitable_for_tdl:
        request_types = [DownloadRequest.VIDEO]

    if not suitable_for_ydl and not suitable_for_gdl and not suitable_for_tdl:
        request_types.append(DownloadRequest.VIDEO)
        request_types.append(DownloadRequest.GALLERY)

    return request_types


class BatchRequest(models.Model):
    class Meta:
        managed = False

    batch = models.ForeignKey(
        Batch,
        on_delete=models.DO_NOTHING
    )
    type = models.CharField(
        max_length=16,
        choices=DownloadRequest.REQUEST_TYPE,
        default=DownloadRequest.AUTOMATIC
    )
    urls = models.TextField(
        help_text=_('One URL per line'),
        validators=[_validate_urls]
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.DO_NOTHING
    )
    content_warning = models.TextField(
        help_text=_('Add a content warning.'),
        null=True,
        blank=True
    )


class DownloadReport(models.Model):
    class Meta:
        ordering = ['-updated_at']

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
            content = self.downloadedcontent_set.filter(mime_type__in=['image/jpeg', 'image/png', 'image/webp']).first()
            if content:
                url = reverse_lazy("get_downloaded_file", kwargs={'content_id': content.id})
                return url
        except Exception as e:
            print(e)
        return None

    def get_thumbnail_id(self):
        try:
            content = self.downloadedcontent_set.filter(mime_type__in=['image/jpeg', 'image/png', 'image/webp']).exclude(name='webpage_screenshot.png').first()
            if content:
                return content.id
        except Exception as e:
            print(e)
        return None

    def get_thumbnail_id_for(self, content_name):
        print(f'Search for the thumbnail of {content_name}')
        name = ''.join(content_name.split('.')[:-1])
        try:
            for c in self.downloadedcontent_set.filter(mime_type__in=['image/jpeg', 'image/png', 'image/webp'], name__icontains=name).all():
                print(f'  found {c.name}')
                return c.id
        except Exception:
            pass
        try:
            content = self.downloadedcontent_set.filter(mime_type__in=['image/jpeg', 'image/png', 'image/webp']).exclude(name='webpage_screenshot.png').first()
            if content:
                return content.id
        except Exception as e:
            print(e)
        return None


def _get_upload_dir(instance, filename):
    owner_id = instance.owner.id
    download_request_id = instance.download_report.download_request.id
    return f'{owner_id}/{download_request_id}/{instance.id}'


class DownloadedContent(models.Model):
    class Meta:
        ordering = ['name']

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
    md5 = models.CharField(
        max_length=32,
        blank=True,
        null=True
    )
    sha256 = models.CharField(
        max_length=64,
        blank=True,
        null=True
    )
    target_file = models.BooleanField(
        default=False
    )
    mime_type = models.CharField(
        max_length=64,
        blank=True,
        null=True
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
    description = models.TextField(
        help_text=_('Add more details about this file.'),
        default=_('No description'),
        null=True,
        blank=True
    )
    post_processing_result = models.JSONField(
        null=True,
        blank=True
    )
    exif_data = models.JSONField(
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

    @property
    def indexed_data(self):
        query = {
            "query": {
                "query_string": {
                    "query": f'content_id: "{self.id}"'
                }
            },
            "_source": [
                "collection_id", "collection_name", "created_at", "mimetype", "origin", "owner", "platform",
                "post.description", "post.title", "post.upload_date", "post.uploader", "sha256", "stats.comment_count",
                "stats.like_count", "stats.view_count", "status", "tags", "thumbnail_content_id", "type", "is_hidden",
                "request_id"
            ],
            "sort": {"created_at": "desc"},
            "size": 10000,
        }
        from elasticsearch import Elasticsearch
        es = Elasticsearch(settings.ELASTICSEARCH_HOSTS)
        try:
            raw_results = es.search(index='c.*', body=query)
            results = transform_hl_results(raw_results)
            return results
        except Exception as e:
            logger.exception(e)
            return []

    @staticmethod
    def get_users_downloaded_content(user):
        try:
            return DownloadedContent.objects.filter(owner=user)
        except Exception as e:
            print(e)
        return None


class UploadRequest(models.Model):
    class Status(models.TextChoices):
        CREATED = 'CREATED', _('Created')
        PROCESSING = 'PROCESSING', _('Processing')
        SUCCEEDED = 'SUCCEEDED', _('Succeeded')
        FAILED = 'FAILED', _('Failed')

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    eof = models.BooleanField(default=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        editable=False
    )
    name = models.CharField(
        max_length=512,
        blank=True,
        null=True
    )
    size = models.IntegerField(
        default=0
    )
    next_addr = models.IntegerField(
        default=0
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.CREATED,
    )
    chunks = models.JSONField(blank=True, null=True)

    @property
    def path(self):
        import pathlib
        extension = pathlib.Path(self.name).suffix
        return f'/tmp/upload.{self.id}.{extension}'

    def cleanup(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def schedule_cleanup(self):
        schedule(
            'video_downloading_platform.core.models.cleanup_upload_request',
            str(self.id),
            schedule_type=Schedule.ONCE,
            next_run=timezone.now() + timedelta(days=2)
        )


class PlatformCredentials(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    name = models.CharField(
        max_length=512,
        unique=True
    )
    credentials = models.JSONField(
        null=True,
        blank=True
    )

def cleanup_upload_request(request_id):
    try:
        upload_request = UploadRequest.objects.get(id=request_id)
        upload_request.cleanup()
    except Exception as e:
        logger.error(e)


@receiver(pre_delete, sender=DownloadedContent, dispatch_uid='delete_stored_file')
def delete_downloaded_content_stored_files(sender, instance: DownloadedContent, using, **kwargs):
    print(f'Delete downloaded content [{instance.owner}] {instance.id}')
    try:
        instance.content.delete()
    except Exception as e:
        logger.error(e)


@receiver(pre_delete, sender=DownloadReport, dispatch_uid='delete_stored_archive_file')
def delete_download_report_stored_files(sender, instance: DownloadReport, using, **kwargs):
    print(f'Delete the archive [{instance.owner}] {instance.id}')
    try:
        instance.archive.delete()
    except Exception as e:
        logger.error(e)


@receiver(pre_delete, sender=DownloadRequest, dispatch_uid='delete_stored_archive_file')
def delete_download_request(sender, instance: DownloadRequest, using, **kwargs):
    print(f'Delete the download request [{instance.owner}] {instance.id}')
    from elasticsearch_dsl import connections
    connections.create_connection(hosts=['elasticsearch'], timeout=20)
    index_name = instance.get_es_index()
    try:
        index = Index(index_name)
        if index.exists():
            index.delete()
    except Exception as e:
        logger.error(e)

@receiver(pre_delete, sender=UploadRequest, dispatch_uid='delete_upload_request_file')
def delete_upload_request_stored_files(sender, instance: UploadRequest, using, **kwargs):
    instance.cleanup()
