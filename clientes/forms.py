from django import forms

from .models import CSVFile

class CSVUploadForm(forms.ModelForm):
    class Meta:
        model = CSVFile
        fields = ['file']

class CPFForm(forms.Form):
    cpf = forms.CharField(max_length=11, label='Digite seu CPF')
