from django.conf import settings
from django.forms import model_to_dict
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext as _

from django.http import HttpResponse, JsonResponse
from notifications.utils import id2slug

from video_downloading_platform.core.forms import BatchForm, BatchRequestForm
from video_downloading_platform.core.models import Batch, DownloadRequest, DownloadedContent, DownloadReport


def home_view(request):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))

    dl_request_form = BatchRequestForm()
    dl_request_form.set_user(user)
    batch_form = BatchForm()

    if request.method == 'POST':
        if 'save_batch' in request.POST:
            f = BatchForm(request.POST)
            if f.is_valid():
                batch = Batch(
                    name=f.cleaned_data.get('name'),
                    description=f.cleaned_data.get('description'),
                    owner=user,
                )
                batch.save()
                messages.success(request, _(f'Your batch {batch.name} have been created.'))
            else:
                batch_form = f
        elif 'close_batch' in request.POST:
            batch_id = request.POST.dict().get('batch_id')
            if batch_id:
                batch = Batch.objects.get(id=batch_id)
                batch.close()
                messages.success(request, _(f'Your batch {batch.name} have been closed.'))
        elif 'request_download' in request.POST:
            f = BatchRequestForm(request.POST)
            f.set_user(user)
            if f.is_valid():
                batch = f.cleaned_data.get('batch')
                urls = f.cleaned_data.get('urls').splitlines()
                for url in urls:
                    striped_url = url.strip()
                    if len(striped_url) > 0:
                        dl_request = DownloadRequest(
                            batch=batch,
                            url=striped_url,
                            owner=user
                        )
                        dl_request.save()
                        dl_request.start()
                messages.success(request, _('Your request has been successfully submitted.'))
            else:
                dl_request_form = f
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
            'batch_form': batch_form,
            'users_batches': users_batches,
        })


def my_batches_view(request):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
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


def close_batch_view(request, batch_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.close()
        messages.success(request, _(f'Your batch {batch.name} have been closed.'))
    return redirect(request.META.get('HTTP_REFERER'))


def archive_batch_view(request, batch_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.archive()
        messages.success(request, _(f'Your batch {batch.name} have been archived.'))
    return redirect(request.META.get('HTTP_REFERER'))


def batch_details_view(request, batch_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
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


def get_downloaded_content_view(request, content_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    content = DownloadedContent.objects.get(id=content_id)
    response = HttpResponse(content.content, content_type=content.mime_type)
    response['Content-Disposition'] = 'inline; filename=' + content.name
    return response


def get_downloaded_file_view(request, content_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    content = DownloadedContent.objects.get(id=content_id)
    try:
        return HttpResponse(content.content, content_type=content.mime_type)
    except Exception:
        return HttpResponse('')


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


def get_batch_status_view(request):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    user_groups = user.groups.values_list('name', flat=True)
    admin = 'admin' in user_groups
    if admin:
        batches = Batch.objects.filter(status=Batch.OPEN).all()
    else:
        batches = Batch.objects.filter(owner=user, status=Batch.OPEN).all()
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


def get_report_archive_view(request, report_id):
    user = request.user
    if not user.is_authenticated:
        return redirect(reverse_lazy(settings.LOGIN_URL))
    report = DownloadReport.objects.get(id=report_id)
    response = HttpResponse(report.archive, content_type='application/zip')
    response['Content-Disposition'] = 'inline; filename=' + report.archive.name
    return response
