import glob
import hashlib
import json
import mimetypes
import tempfile
import traceback
from os import path

import youtube_dl
from django.core.files import File

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
                'outtmpl': f'{tmp_dir}/%(title)s-%(id)s.%(ext)s',
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
                print(mime_type)
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
