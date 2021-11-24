from django import forms
from django.utils.translation import gettext as _

from video_downloading_platform.core.models import Batch, BatchRequest


class BatchRequestForm(forms.ModelForm):
    class Meta:
        model = BatchRequest
        fields = [
            'batch',
            'urls'
        ]

class BatchForm(forms.ModelForm):
    class Meta:
        model = Batch
        fields = [
            'name',
            'description'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 2, 'cols': 20}),
        }
