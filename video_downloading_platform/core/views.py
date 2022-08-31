import os.path
import traceback
import zipfile
from io import BytesIO
from tempfile import NamedTemporaryFile
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.files import File
from django.db import transaction
from django.forms import model_to_dict
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.translation import gettext as _
from django.views.generic import UpdateView
from django.utils import timezone
from notifications.signals import notify
from notifications.utils import id2slug

from video_downloading_platform.core.forms import BatchForm, BatchRequestForm, UploadForm, BatchTeamForm, \
    DownloadRequestLightForm
from video_downloading_platform.core.models import Batch, DownloadRequest, DownloadedContent, DownloadReport, \
    _get_request_types_to_run, BatchTeam
from video_downloading_platform.core.tasks import hash_file, create_zip_archive, _get_exif_data_for_file, get_mimetype
from video_downloading_platform.users.admin import User


def handle_file_upload(request, upload_form):
    filename = str(request.FILES['file'])
    original_basename = os.path.basename(filename)
    user = request.user
    batch = upload_form.cleaned_data.get('batch')
    download_request = DownloadRequest(
        batch=batch,
        status=DownloadRequest.Status.PROCESSING,
        url='http://dummy.url.local',
        owner=user,
        content_warning=upload_form.cleaned_data.get('content_warning')
    )
    download_request.save()
    download_report = DownloadReport(
        download_request=download_request,
        owner=user
    )
    download_report.save()
    file = request.FILES['file']
    try:
        with NamedTemporaryFile(suffix=original_basename) as tmp:
            for chunk in file.chunks():
                tmp.write(chunk)
            tmp.seek(0)
            sha256, md5 = hash_file(tmp.name)
            mime_type = get_mimetype(tmp.name)
            if not mime_type:
                mime_type = 'application/octet-stream'
            exif_data = _get_exif_data_for_file(tmp.name)
            metadata = {
                'original_name': filename,
                'preferred_name': upload_form.cleaned_data['name'],
                'sha256': sha256,
                'md5': md5,
                'mime_type': mime_type,
                'description': upload_form.cleaned_data['description'],
            }
            downloaded_content = DownloadedContent(
                download_report=download_report,
                owner=user,
                md5=md5,
                sha256=sha256,
                name=filename,
                metadata=metadata,
                exif_data=exif_data,
                mime_type=mime_type,
                target_file=True,
                description=upload_form.cleaned_data['description']
            )
            downloaded_content.save()
            content_file = File(tmp)
            downloaded_content.content.save(filename, content_file)
            downloaded_content.save()
        download_request.status = DownloadRequest.Status.SUCCEEDED
        download_request.save()
        create_zip_archive(download_report.id)
        actions = [
            {
                'url': reverse_lazy('batch_details', args=[download_request.batch.id]) + '#' + str(
                    download_request.id),
                'title': 'View files'}
        ]
        notify.send(user, recipient=user, verb='',
                    description='Your files have been successfully uploaded',
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
        notify.send(user, recipient=user, verb='',
                    level='error',
                    description='Your request has failed',
                    public=False,
                    actions=actions)


def _start_pending_requests(requests):
    for dl_request in requests:
        dl_request.start()


@login_required
def home_view(request):
    user = request.user

    dl_request_form = BatchRequestForm()
    dl_request_form.set_user(user)

    batch_form = BatchForm()

    ul_request_form = UploadForm()
    ul_request_form.set_user(user)

    if request.method == 'POST':
        if 'save_batch' in request.POST:
            f = BatchForm(request.POST)
            if f.is_valid():
                team = BatchTeam(
                    owner=user
                )
                team.save()
                batch = f.save(commit=False)
                batch.owner = user
                batch.team = team
                batch.save()
                f.save_m2m()
                # batch = Batch(
                #     name=f.cleaned_data.get('name'),
                #     description=f.cleaned_data.get('description'),
                #     tags=f.cleaned_data.get('tags'),
                #     owner=user,
                #     team=team
                # )
                # batch.save()
                messages.success(request, _(f'Your batch {batch.name} have been created.'))
                return redirect(request.META.get('HTTP_REFERER'))
            else:
                batch_form = f
        elif 'close_batch' in request.POST:
            batch_id = request.POST.dict().get('batch_id')
            if batch_id:
                batch = Batch.objects.get(id=batch_id)
                batch.close()
                messages.success(request, _(f'Your batch {batch.name} have been closed.'))
                return redirect(request.META.get('HTTP_REFERER'))
        elif 'request_download' in request.POST:
            f = BatchRequestForm(request.POST)
            f.set_user(user)
            if f.is_valid():
                request_type = f.cleaned_data.get('type')
                batch = f.cleaned_data.get('batch')
                urls = f.cleaned_data.get('urls').splitlines()
                batch.updated_at = timezone.now()
                batch.save()
                tasks_to_start = []
                for url in urls:
                    striped_url = url.strip()
                    if len(striped_url) > 0:
                        tasks_to_run = _get_request_types_to_run(url, request_type)
                        for request_type in tasks_to_run:
                            dl_request = DownloadRequest.objects.create(
                                batch=batch,
                                url=striped_url,
                                owner=user,
                                type=request_type,
                                content_warning=f.cleaned_data.get('content_warning')
                            )
                            dl_request.save()
                            tasks_to_start.append(dl_request)
                transaction.on_commit(lambda: _start_pending_requests(tasks_to_start))
                messages.success(request, _('Your request has been successfully submitted.'))
                return redirect(request.META.get('HTTP_REFERER'))
            else:
                dl_request_form = f
        elif 'request_upload' in request.POST:
            f = UploadForm(request.POST, request.FILES)
            f.set_user(user)
            if f.is_valid():
                handle_file_upload(request, f)
                return redirect(request.META.get('HTTP_REFERER'))
            else:
                ul_request_form = f
    else:
        pass

    users_batches = Batch.get_users_open_batches(user)
    if users_batches:
        users_batches = users_batches.all()

    return render(
        request,
        'pages/home.html',
        {
            'dl_request_form': dl_request_form,
            'ul_request_form': ul_request_form,
            'batch_form': batch_form,
            'users_batches': users_batches,
        })


@login_required
def my_batches_view(request):
    user = request.user
    user_groups = user.groups.values_list('name', flat=True)
    admin = 'admin' in user_groups
    batches = []
    batches.extend(Batch.get_users_open_batches(user).all())
    batches.extend(Batch.get_users_closed_batches(user).all())
    batches.extend(Batch.get_users_archived_batches(user).all())
    return render(
        request,
        'pages/batch_list.html',
        {
            'admin': admin,
            'batches': batches
        })


class BatchTeamUpdateView(UpdateView, LoginRequiredMixin):
    model = BatchTeam
    form_class = BatchTeamForm


@login_required
def close_batch_view(request, batch_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.close()
        messages.success(request, _(f'Your batch {batch.name} have been closed.'))
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def reopen_batch_view(request, batch_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.reopen()
        messages.success(request, _(f'Your batch {batch.name} have been closed.'))
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def archive_batch_view(request, batch_id):
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.archive()
        messages.success(request, _(f'Your batch {batch.name} have been archived.'))
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def batch_details_view(request, batch_id):
    user = request.user
    user_groups = user.groups.values_list('name', flat=True)
    admin = 'admin' in user_groups
    batch = Batch.objects.get(id=batch_id)
    return render(
        request,
        'pages/batch_details.html',
        {
            'admin': admin,
            'batch': batch,
        })


@login_required
def get_downloaded_content_view(request, content_id):
    content = DownloadedContent.objects.get(id=content_id)
    response = HttpResponse(content.content, content_type=content.mime_type)
    response['Content-Disposition'] = 'inline; filename=' + content.name
    return response


@login_required
def get_downloaded_file_view(request, content_id):
    content = DownloadedContent.objects.get(id=content_id)
    try:
        return HttpResponse(content.content, content_type=content.mime_type)
    except Exception:
        return HttpResponse('')


@login_required
def get_unread_notifications_view(request):
    try:
        user_is_authenticated = request.user.is_authenticated()
    except TypeError:  # Django >= 1.11
        user_is_authenticated = request.user.is_authenticated

    if not user_is_authenticated:
        data = {
            'unread_count': 0,
            'unread_list': []
        }
        return JsonResponse(data)

    num_to_fetch = 10
    unread_list = []
    for notification in request.user.notifications.unread()[0:num_to_fetch]:
        struct = model_to_dict(notification)
        struct['slug'] = id2slug(notification.id)
        if notification.actor:
            struct['actor'] = str(notification.actor)
        if notification.target:
            struct['target'] = str(notification.target)
        if notification.action_object:
            struct['action_object'] = str(notification.action_object)
        if notification.data:
            struct['data'] = notification.data
        unread_list.append(struct)
        if request.GET.get('mark_as_read'):
            notification.mark_as_read()

    return render(
        request,
        "notifications/toaster.html",
        {
            'notifications': unread_list
        }
    )


@login_required
def get_batch_status_view(request):
    user = request.user
    user_groups = user.groups.values_list('name', flat=True)
    admin = 'admin' in user_groups
    if admin:
        batches = Batch.objects.filter(status=Batch.OPEN).all()
    else:
        batches = Batch.get_users_open_batches(user).all()
    statuses = []
    for batch in batches:
        status_obj = {
            'id': batch.id,
            'submitted': 0,
            'succeeded': 0,
            'failed': 0,
        }
        for download_request in batch.download_requests.all():
            status = download_request.status
            if status == DownloadRequest.Status.CREATED:
                status_obj['submitted'] += 1
            elif status == DownloadRequest.Status.ENQUEUED:
                status_obj['submitted'] += 1
            elif status == DownloadRequest.Status.PROCESSING:
                status_obj['submitted'] += 1
            elif status == DownloadRequest.Status.POST_PROCESSING:
                status_obj['submitted'] += 1
            elif status == DownloadRequest.Status.SUCCEEDED:
                status_obj['succeeded'] += 1
            elif status == DownloadRequest.Status.CANCELLED:
                status_obj['failed'] += 1
            elif status == DownloadRequest.Status.FAILED:
                status_obj['failed'] += 1
        statuses.append(status_obj)
    return JsonResponse(statuses, safe=False)


@login_required
def get_report_archive_view(request, report_id):
    report = DownloadReport.objects.get(id=report_id)
    response = HttpResponse(report.archive, content_type='application/zip')
    response['Content-Disposition'] = 'inline; filename=' + report.archive.name
    return response


@login_required
def download_collection_zip_view(request, batch_id):
    collection = Batch.objects.get(id=batch_id)
    tmp = BytesIO()
    with zipfile.ZipFile(tmp, 'w') as zip_file:
        for download_request in collection.download_requests.all():
            for download_report in download_request.report.all():
                if download_report.archive:
                    filename = f'{download_report.id}.zip'
                    data = download_report.archive.file.read()
                    zip_file.writestr(filename, data)
        zip_file.close()
        tmp.flush()
    tmp.seek(0)
    response = HttpResponse(tmp, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename=VHS-{collection.owner}-{collection.name}.zip'
    return response


@login_required
def hide_download_request_view(request, request_id):
    try:
        download_request = DownloadRequest.objects.get(id=request_id)
        download_request.is_hidden = True
        download_request.save()
    except Exception:
        pass
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def show_download_request_view(request, request_id):
    try:
        download_request = DownloadRequest.objects.get(id=request_id)
        download_request.is_hidden = False
        download_request.save()
    except Exception:
        pass
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def mark_all_notification_read_view(request):
    request.user.notifications.mark_all_as_read()
    return redirect(request.META.get('HTTP_REFERER'))


@login_required
def batch_edit_view(request, batch_id):
    batch = get_object_or_404(Batch, id=batch_id)
    form = BatchForm(request.POST or None, instance=batch)
    if form.is_valid():
        form.save()
        return redirect(request.META.get('HTTP_REFERER'))
    return render(
        request,
        'partials/m_modal_form.html',
        {
            'form': form,
            'action': reverse_lazy('batch_edit', args=[batch.id]),
            'title': _('Edit collection')
        }
    )


@login_required
def edit_download_request_view(request, request_id):
    request_obj = get_object_or_404(DownloadRequest, id=request_id)
    form = DownloadRequestLightForm(request.POST or None, instance=request_obj)
    if form.is_valid():
        form.save()
        return redirect(request.META.get('HTTP_REFERER'))
    return render(
        request,
        'partials/m_modal_form.html',
        {
            'form': form,
            'action': reverse_lazy('edit_download_request', args=[request_obj.id]),
            'title': _('Edit tags and content warning')
        }
    )


@login_required
def statistics_view(request):
    import psutil
    disk_usage = psutil.disk_usage('/')
    mem_usage = psutil.virtual_memory()
    request_total = DownloadRequest.objects.all().count()
    request_succeeded = DownloadRequest.objects.filter(status=DownloadRequest.Status.SUCCEEDED).count()
    request_failed = DownloadRequest.objects.filter(status=DownloadRequest.Status.FAILED).count()
    stats = {
            'disk': {
                'total': disk_usage[0],
                'used': disk_usage[1],
                'free': disk_usage[2],
                'percent': disk_usage[3],
                'chart': '',
            },
            'mem': {
                'total': mem_usage[0],
                'free': mem_usage[1],
                'percent': mem_usage[2],
            },
            'collections': Batch.objects.all().count(),
            'requests': {
                'total': request_total,
                'succeeded': request_succeeded,
                'failed': request_failed,
                'percent': 100*request_succeeded/(1.0*request_total)
            },
            'files': DownloadedContent.objects.all().count(),
            'users': User.objects.all().count(),
        }
    return render(
        request,
        'pages/statistics.html',
        {
            'stats': stats,
        }
    )
    # return JsonResponse(
    #     {
    #         'disk': {
    #             'total': disk_usage[0],
    #             'used': disk_usage[1],
    #             'free': disk_usage[2],
    #             'percent': disk_usage[3],
    #             'chart': '',
    #         },
    #         'mem': {
    #             'total': mem_usage[0],
    #             'available': mem_usage[1],
    #             'percent': mem_usage[2],
    #         },
    #         'collections': Batch.objects.all().count(),
    #         'requests': {
    #             'total': DownloadRequest.objects.all().count(),
    #             'succeeded': DownloadRequest.objects.filter(status=DownloadRequest.Status.SUCCEEDED).count(),
    #             'failed': DownloadRequest.objects.filter(status=DownloadRequest.Status.FAILED).count(),
    #         },
    #         'files': DownloadedContent.objects.all().count(),
    #         'users': User.objects.all().count(),
    #     }
    # )
