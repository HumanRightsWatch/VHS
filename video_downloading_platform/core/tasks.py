import glob
import hashlib
import json
import mimetypes
import tempfile
import traceback
import zipfile
from os import path

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
    with open(filename, 'rb') as file:
        chunk = 0
        while chunk != b'':
            chunk = file.read(4096)
            h_sha256.update(chunk)
    return h_sha256.hexdigest()


def run_download_request(download_request_id):
    try:
        download_request = DownloadRequest.objects.get(id=download_request_id)
        download_request.status = DownloadRequest.Status.PROCESSING
        download_request.save()
        owner = download_request.owner
        download_report = DownloadReport(
            download_request=download_request,
            owner=owner
        )
        download_report.save()
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
                print('downloading video')
                ydl.download([download_request.url])
            for f in glob.glob(f'{tmp_dir}/*', recursive=True):
                sha256 = hash_file(f)
                cleaned_name = f.replace(tmp_dir, '')
                if cleaned_name.startswith('/'):
                    cleaned_name = cleaned_name[1:]
                mime_type = mimetypes.MimeTypes().guess_type(f)[0]
                metadata = {}
                if cleaned_name.endswith('.info.json'):
                    metadata = json.load(open(f, mode='r'))
                if not mime_type:
                    mime_type = 'application/octet-stream'
                    if cleaned_name.endswith('.webp'):
                        mime_type = 'image/webp'

                downloaded_content = DownloadedContent(
                    download_report=download_report,
                    owner=owner,
                    sha256=sha256,
                    name=cleaned_name,
                    metadata=metadata,
                    mime_type=mime_type
                )
                downloaded_content.save()
                mode = 'rb'
                with open(f, mode=mode) as content:
                    content_file = File(content)
                    downloaded_content.content.save(cleaned_name, content_file)
                downloaded_content.save()
            download_request.status = DownloadRequest.Status.SUCCEEDED
            download_request.save()
            create_zip_archive(download_report.id)
            actions = [
                {
                    'url': reverse_lazy('batch_details', args=[download_request.batch.id])+'#'+str(download_request.id),
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
                'url': reverse_lazy('batch_details', args=[download_request.batch.id])+'#'+str(download_request.id),
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
