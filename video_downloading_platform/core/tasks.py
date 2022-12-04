import glob
import json
from urllib.parse import urlparse
import tempfile
import traceback
import zipfile
from os import path
import logging
import hashlib
import magic
from tempfile import NamedTemporaryFile
from dateutil.parser import parse

import exiftool
import yt_dlp as youtube_dl
from django.core.files import File
from django.urls import reverse_lazy
from elasticsearch_dsl import Index
from notifications.signals import notify

from video_downloading_platform.core.indexing import Entity
from video_downloading_platform.core.models import (
    DownloadRequest,
    DownloadReport,
    DownloadedContent, Batch,
)

logger = logging.getLogger(__name__)

def hash_file(filename):
    if path.isfile(filename) is False:
        raise Exception("File not found for hash operation")
    h_sha256 = hashlib.sha256()
    h_md5 = hashlib.md5()
    with open(filename, 'rb') as file:
        chunk = 0
        while chunk != b'':
            chunk = file.read(4096)
            h_sha256.update(chunk)
            h_md5.update(chunk)
    return h_sha256.hexdigest(), h_md5.hexdigest()


# def get_mimetype(filename):
#     mime_type = mimetypes.MimeTypes().guess_type(filename)[0]
#     if not mime_type:
#         mime_type = 'application/octet-stream'
#     if filename.endswith('.webp'):
#         mime_type = 'image/webp'
#     if filename.endswith('.jpeg'):
#         mime_type = 'image/jpeg'
#     if filename.endswith('.png'):
#         mime_type = 'image/png'
#     return mime_type


def _get_file_metadata(directory, filename):
    if filename.endswith('.json') or filename.endswith('.description') or not filename:
        return {}
    filename_without_extension = ''.join(filename.split('.')[:-1])

    for f in glob.glob(f'{directory}/{filename_without_extension}*.json', recursive=True):
        try:
            with open(f, mode='r') as json_file:
                metadata = json.load(json_file)
                return metadata
        except Exception as e:
            logger.error(e)
    return {}


def _get_exif_data_for_file(file_path):
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(file_path)[0]
            return metadata
    except Exception as e:
        logger.error(e)
    return {}

def compute_downloaded_content_metadata(downloaded_content_id, download_request_id, create_archive=False):
    logger.info(f'Compute downloaded content metadata {downloaded_content_id}')
    h_sha256 = hashlib.sha256()
    h_sha1 = hashlib.sha1()
    h_md5 = hashlib.md5()
    try:
        downloaded_content: DownloadedContent = DownloadedContent.objects.get(id=downloaded_content_id)
    except Exception as e:
        logger.error(e)
        return

    with NamedTemporaryFile() as tmp:
        for chunk in downloaded_content.content.chunks():
            tmp.write(chunk)
            h_sha256.update(chunk)
            h_sha1.update(chunk)
            h_md5.update(chunk)
        tmp.seek(0)
        mime_type = magic.from_buffer(tmp.read(2048), mime=True)
        tmp.seek(0)
        exif = _get_exif_data_for_file(tmp.name)

    downloaded_content.md5 = h_md5.hexdigest()
    downloaded_content.sha256 = h_sha256.hexdigest()
    downloaded_content.mime_type = mime_type
    downloaded_content.exif_data = exif
    downloaded_content.metadata['md5'] = h_md5.hexdigest()
    downloaded_content.metadata['sha1'] = h_sha1.hexdigest()
    downloaded_content.metadata['sha256'] = h_sha256.hexdigest()
    downloaded_content.metadata['mime_type'] = mime_type
    downloaded_content.save()
    index_download_request_by_id(download_request_id)
    if create_archive:
        create_zip_archive(downloaded_content.download_report.id)


def _manage_downloaded_files(directory, owner, download_report, cw, request_type=None):
    for downloaded_file in glob.glob(f'{directory}/*', recursive=True):
        sha256, md5 = hash_file(downloaded_file)
        cleaned_name = downloaded_file.replace(directory, '')
        if cleaned_name.startswith('/'):
            cleaned_name = cleaned_name[1:]
        mime_type = magic.from_file(downloaded_file, mime=True)
        mime_prefix = ''
        if request_type == DownloadRequest.VIDEO:
            mime_prefix = 'video'
        elif request_type == DownloadRequest.GALLERY:
            mime_prefix = 'image'
        metadata = {}
        exif_data = {}
        is_target = False
        if mime_type.startswith(mime_prefix):
            is_target = True
            metadata = _get_file_metadata(directory, cleaned_name)
            exif_data = _get_exif_data_for_file(downloaded_file)
        downloaded_content = DownloadedContent(
            download_report=download_report,
            owner=owner,
            md5=md5,
            sha256=sha256,
            name=cleaned_name,
            metadata=metadata,
            target_file=is_target,
            exif_data=exif_data,
            mime_type=mime_type,
        )
        downloaded_content.save()
        mode = 'rb'
        with open(downloaded_file, mode=mode) as content:
            content_file = File(content)
            downloaded_content.content.save(cleaned_name, content_file)
        downloaded_content.save()


def run_download_video_request(download_request_id):
    download_request = DownloadRequest.objects.get(id=download_request_id)
    download_request.status = DownloadRequest.Status.PROCESSING
    download_request.save()
    owner = download_request.owner
    download_report = DownloadReport(
        download_request=download_request,
        owner=owner
    )
    download_report.save()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            options = {
                'outtmpl': f'{tmp_dir}/%(id)s.%(ext)s',
                'format': 'best',
                'writedescription': True,
                'writeinfojson': True,
                'writeannotations': True,
                'writethumbnail': True,
                'noplaylist': False,
            }
            with youtube_dl.YoutubeDL(options) as ydl:
                print('downloading video', download_request.url)
                ydl.download([download_request.url])

            _manage_downloaded_files(tmp_dir, owner, download_report, download_request.content_warning,
                                     download_request.type)

            download_request.status = DownloadRequest.Status.SUCCEEDED
            download_request.save()

            create_zip_archive(download_report.id)
            index_download_request(download_request)

            actions = [
                {
                    'url': reverse_lazy('batch_details', args=[download_request.batch.id]) + '#' + str(
                        download_request.id),
                    'title': 'View files'}
            ]
            notify.send(owner, recipient=owner, verb='',
                        description='Your files have been successfully downloaded',
                        public=False,
                        actions=actions)
    except Exception as e:
        logger.error(e)
        download_report.in_error = True
        error_message = download_report.error_message
        if not error_message:
            error_message = ''
        error_message += '\n' + traceback.format_exc()
        download_report.error_message = error_message
        download_report.save()
        download_request.status = DownloadRequest.Status.FAILED
        download_request.save()
        actions = [
            {
                'url': reverse_lazy('batch_details', args=[download_request.batch.id]) + '#' + str(download_request.id),
                'title': 'View details'}
        ]
        notify.send(owner, recipient=owner, verb='',
                    level='error',
                    description='Your request has failed',
                    public=False,
                    actions=actions)


def run_download_gallery_request(download_request_id):
    from gallery_dl import config, job
    config.set((), "filename", "{id}.{extension}")
    config.set((), "directory", "")
    config.set(
        ('extractor',),
        'postprocessors',
        [
            {
                "name": "metadata",
                "mode": "json",
            }
        ]
    )
    download_request = DownloadRequest.objects.get(id=download_request_id)
    download_request.status = DownloadRequest.Status.PROCESSING
    download_request.save()
    owner = download_request.owner
    download_report = DownloadReport(
        download_request=download_request,
        owner=owner
    )
    download_report.save()
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            config.set((), "base-directory", tmp_dir)
            job.DownloadJob(download_request.url).run()

            _manage_downloaded_files(tmp_dir, owner, download_report, download_request.content_warning,
                                     download_request.type)

            download_request.status = DownloadRequest.Status.SUCCEEDED
            download_request.save()

            create_zip_archive(download_report.id)
            index_download_request(download_request)

            actions = [
                {
                    'url': reverse_lazy('batch_details', args=[download_request.batch.id]) + '#' + str(
                        download_request.id),
                    'title': 'View files'}
            ]
            notify.send(owner, recipient=owner, verb='',
                        description='Your files have been successfully downloaded',
                        public=False,
                        actions=actions)
    except Exception as e:
        logger.error(e)
        download_report.in_error = True
        error_message = download_report.error_message
        if not error_message:
            error_message = ''
        error_message += '\n' + traceback.format_exc()
        download_report.error_message = error_message
        download_report.save()
        download_request.status = DownloadRequest.Status.FAILED
        download_request.save()
        actions = [
            {
                'url': reverse_lazy('batch_details', args=[download_request.batch.id]) + '#' + str(download_request.id),
                'title': 'View details'}
        ]
        notify.send(owner, recipient=owner, verb='',
                    level='error',
                    description='Your request has failed',
                    public=False,
                    actions=actions)


def create_zip_archive(report_id):
    logger.info(f'Create archive for download report {report_id}')
    download_report = DownloadReport.objects.get(id=report_id)
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            files_to_archive = []
            for downloaded_content in download_report.downloadedcontent_set.all():
                if downloaded_content.content:
                    with open(f'{tmp_dir}/{downloaded_content.name}', mode='wb') as out:
                        for chunk in downloaded_content.content.chunks():
                            out.write(chunk)
                        out.seek(0)
                        files_to_archive.append({
                            'path': out.name,
                            'name': downloaded_content.name,
                        })
                    if downloaded_content.exif_data:
                        with open(f'{tmp_dir}/{downloaded_content.name}-exif.json', mode='w') as out:
                            out.write(json.dumps(downloaded_content.exif_data, indent=2))
                        files_to_archive.append({
                            'path': out.name,
                            'name': f'{downloaded_content.name}-exif.json',
                        })
                    if downloaded_content.metadata:
                        with open(f'{tmp_dir}/{downloaded_content.name}-metadata.json', mode='w') as out:
                            out.write(json.dumps(downloaded_content.metadata, indent=2))
                        files_to_archive.append({
                            'path': out.name,
                            'name': f'{downloaded_content.name}-metadata.json',
                        })

            with open(f'{tmp_dir}/archive.zip', mode='wb') as tmp:
                zf = zipfile.ZipFile(tmp, "w")
                for file in files_to_archive:
                    zf.write(file.get('path'), file.get('name'))
                zf.close()
            with open(f'{tmp_dir}/archive.zip', mode='rb') as tmp:
                download_report.archive.save('archive.zip', tmp)
    except Exception as e:
        logger.error(e)


def __try_recovering_date(d):
    try:
        return parse(d)
    except:
        return d


def __parse_exif(exif):
    ignore = [
        'ICC_Profile',
        'Composite',
        'Photoshop',
        'JFIF',
        'MakerNotes',
        'APP14',
    ]
    data = {}

    if not exif or type(exif) is list:
        return data

    def should_ignore(key: str):
        if ':' in key:
            key = key.split(':')[0]
        return bool(key in ignore)

    for k, v in exif.items():
        if should_ignore(k):
            continue
        k = k.replace(':', '_')
        if 'date' in k.lower():
            data[k] = __try_recovering_date(v)
        elif type(v) is set:
            data[k] = list(v)
        else:
            data[k] = v
    return data


def get_in_dict(keys, obj, default=''):
    for k in keys:
        if k in obj:
            return obj.get(k)
    return default

def index_download_request(request: DownloadRequest):
    from elasticsearch_dsl import connections
    connections.create_connection(hosts=['elasticsearch'], timeout=20)

    index_name = request.get_es_index()
    try:
        index = Index(index_name)
        if not index.exists():
            index.create()
    except Exception as e:
        logger.error(e)
        return

    Entity.init(index=index_name)

    if request.is_hidden:
        return

    for report in request.report.all():
        for content in report.downloadedcontent_set.all():
            if content.name.endswith('.json') or content.name.endswith('.description'):
                continue
            # if not content.target_file:
            #     continue
            entity = Entity()
            entity.meta.id = str(content.id)
            entity.created_at = request.created_at
            entity.content_id = str(content.id)
            entity.owner = str(request.owner.username)
            entity.owner_id = str(request.owner.id)
            entity.tags = [str(t) for t in request.tags.all()]
            entity.request_id = str(request.id)
            entity.collection_id = str(request.batch.id)
            entity.collection_name = str(request.batch.name)
            entity.collection_description = str(request.batch.description)
            entity.origin = request.url
            entity.mimetype = content.mime_type
            entity.md5 = content.md5
            entity.sha256 = content.sha256
            entity.status = request.get_status_display()
            entity.thumbnail_content_id = report.get_thumbnail_id()
            entity.exif = '\n'.join([f'{k}: {v}' for k, v in __parse_exif(content.exif_data).items()])
            entity.content_warning = request.content_warning

            if request.type == DownloadRequest.VIDEO:
                entity.type = DownloadRequest.VIDEO.lower()
                entity.stats = {
                    'view_count': content.metadata.get('view_count', -1),
                    'like_count': content.metadata.get('like_count', -1),
                    'comment_count': content.metadata.get('comment_count', -1),
                }
                entity.post = {
                    'uploader': content.metadata.get('uploader', ''),
                    'uploader_url': content.metadata.get('uploader_url', ''),
                    'uploader_id': str(content.metadata.get('uploader_id', '')),
                    'title': content.metadata.get('title', content.name),
                    'description': content.metadata.get('fulltitle', ''),
                    'upload_date': __try_recovering_date(content.metadata.get('upload_date', '1970-01-01')),
                }
                entity.webpage_url = content.metadata.get('webpage_url', '')
                entity.platform = content.metadata.get('extractor_key', '')

            elif request.type == DownloadRequest.GALLERY:
                entity.type = DownloadRequest.GALLERY.lower()
                entity.platform = urlparse(request.url).netloc
                entity.stats = {
                    'view_count': get_in_dict(['view_count'], content.metadata, -1),
                    'like_count': get_in_dict(['like_count', 'fav_count', 'favourites_count', 'favorite_count'], content.metadata, -1),
                    'comment_count': get_in_dict(['comment_count', 'replies_count', 'reply_count'], content.metadata, -1),
                }
                entity.post = {
                    'uploader': content.metadata.get('uploader', ''),
                    'uploader_url': content.metadata.get('uploader_url', ''),
                    'uploader_id': str(get_in_dict(['uploader_id'], content.metadata, -1),),
                    'title': content.metadata.get('title', content.name),
                    'description': get_in_dict(['fulltitle', 'description', 'content', 'tag_string'], content.metadata),
                    'upload_date': __try_recovering_date(get_in_dict(['date', 'created_at'], content.metadata, '1970-01-01')),
                }

            if request.url == 'http://dummy.url.local':
                entity.origin = 'User upload'
                entity.platform = 'VHS'
                entity.post = {
                    'title': content.name,
                    'description': content.metadata.get('description'),
                }

            entity.save(index=index_name)

    request.batch.indexed = True
    request.batch.save()

def index_download_request_by_id(request_id: str):
    request: DownloadRequest = DownloadRequest.objects.get(id=request_id)
    if not request:
        return
    index_download_request(request)

def index_collection_by_id(batch_id: str):
    batch: Batch = Batch.objects.get(id=batch_id)
    if not batch:
        return
    for dr in batch.download_requests.all():
        index_download_request(dr)
