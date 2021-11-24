from django.shortcuts import render
from django.contrib import messages
from django.utils.translation import gettext as _

from video_downloading_platform.core.forms import BatchForm, BatchRequestForm
from video_downloading_platform.core.models import Batch, DownloadRequest


def home_view(request):
    user = request.user
    dl_request_form = BatchRequestForm()
    batch_form = BatchForm()
    users_batches = Batch.get_users_open_batches(user).all()

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
            if f.is_valid():
                batch = f.cleaned_data.get('batch')
                urls = f.cleaned_data.get('urls').splitlines()
                for url in urls:
                    dl_request = DownloadRequest(
                        batch=batch,
                        url=url.strip(),
                        owner=user
                    )
                    dl_request.save()
                    dl_request.start()
                messages.success(request, _(f'Your request has been successfully submitted.'))
            else:
                dl_request_form = f
    else:
        pass

    return render(
        request,
        'pages/home.html',
        {
            'dl_request_form': dl_request_form,
            'batch_form': batch_form,
            'users_batches': users_batches,
        })

