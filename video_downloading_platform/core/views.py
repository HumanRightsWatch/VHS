from django.conf import settings
from django.shortcuts import render, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils.translation import gettext as _

from django.http import HttpResponse
from video_downloading_platform.core.forms import BatchForm, BatchRequestForm
from video_downloading_platform.core.models import Batch, DownloadRequest, DownloadedContent


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
    return render(
        request,
        'pages/batch_list.html',
        {
            'opened': Batch.get_users_open_batches(user),
            'closed': Batch.get_users_closed_batches(user),
            'archived': Batch.get_users_archived_batches(user),
        })


def close_batch_view(request, batch_id):
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.close()
        messages.success(request, _(f'Your batch {batch.name} have been closed.'))
    return redirect(request.META.get('HTTP_REFERER'))


def archive_batch_view(request, batch_id):
    if batch_id:
        batch = Batch.objects.get(id=batch_id)
        batch.archive()
        messages.success(request, _(f'Your batch {batch.name} have been archived.'))
    return redirect(request.META.get('HTTP_REFERER'))


def batch_details_view(request, batch_id):
    batch = Batch.objects.get(id=batch_id)
    return render(
        request,
        'pages/batch_details.html',
        {
            'batch': batch,
        })


def get_downloaded_content_view(request, content_id):
    content = DownloadedContent.objects.get(id=content_id)
    response = HttpResponse(content.content, content_type=content.mime_type)
    response['Content-Disposition'] = 'inline; filename=' + content.name
    return response


def get_downloaded_file_view(request, content_id):
    content = DownloadedContent.objects.get(id=content_id)
    try:
        return HttpResponse(content.content, content_type=content.mime_type)
    except Exception:
        return HttpResponse('')
