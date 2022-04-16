import glob
import hashlib
import json
import mimetypes
import tempfile
import traceback
import zipfile
from os import path

import exiftool
import youtube_dl
from django.core.files import File
from django.urls import reverse_lazy
from notifications.signals import notify

from video_downloading_platform.core.models import (
    DownloadRequest,
    DownloadReport,
    DownloadedContent,
)


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


def get_mimetype(filename):
    mime_type = mimetypes.MimeTypes().guess_type(filename)[0]
    if not mime_type:
        mime_type = 'application/octet-stream'
    if filename.endswith('.webp'):
        mime_type = 'image/webp'
    if filename.endswith('.jpeg'):
        mime_type = 'image/jpeg'
    if filename.endswith('.png'):
        mime_type = 'image/png'
    return mime_type


def _get_file_metadata(directory, filename):
    if filename.endswith('.json') or filename.endswith('.description') or not filename:
        return {}
    filename_without_extension = ''.join(filename.split('.')[:-1])

    for f in glob.glob(f'{directory}/{filename_without_extension}*.json', recursive=True):
        try:
            with open(f, mode='r') as json_file:
                metadata = json.load(json_file)
                return metadata
        except Exception:
            pass
    return {}


def _get_exif_data_for_file(file_path):
    try:
        with exiftool.ExifToolHelper() as et:
            metadata = et.get_metadata(file_path)[0]
            return metadata
    except Exception:
        pass
    return {}


def _manage_downloaded_files(directory, owner, download_report, request_type=None):
    for downloaded_file in glob.glob(f'{directory}/*', recursive=True):
        sha256, md5 = hash_file(downloaded_file)
        cleaned_name = downloaded_file.replace(directory, '')
        if cleaned_name.startswith('/'):
            cleaned_name = cleaned_name[1:]
        mime_type = get_mimetype(downloaded_file)
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
            mime_type=mime_type
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
            }
            with youtube_dl.YoutubeDL(options) as ydl:
                print('downloading video', download_request.url)
                ydl.download([download_request.url])

            _manage_downloaded_files(tmp_dir, owner, download_report, download_request.type)

            download_request.status = DownloadRequest.Status.SUCCEEDED
            download_request.save()
            create_zip_archive(download_report.id)
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
        print(e)
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

            _manage_downloaded_files(tmp_dir, owner, download_report, download_request.type)

            download_request.status = DownloadRequest.Status.SUCCEEDED
            download_request.save()

            create_zip_archive(download_report.id)

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
        print(e)
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

            with open(f'{tmp_dir}/archive.zip', mode='wb') as tmp:
                zf = zipfile.ZipFile(tmp, "w")
                for file in files_to_archive:
                    zf.write(file.get('path'), file.get('name'))
                zf.close()
            with open(f'{tmp_dir}/archive.zip', mode='rb') as tmp:
                download_report.archive.save('archive.zip', tmp)
    except Exception as e:
        print(e)
