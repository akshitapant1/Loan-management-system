from django import forms
from .models import Loan, Payment, Member
from django.contrib.auth.models import User

class MemberForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['phone', 'address']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
        }

class LoanApplicationForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['amount', 'interest_rate', 'due_date', 'loan_type', 'duration_months', 'purpose', 'monthly_income', 'employment_type']
        widgets = {
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'purpose': forms.Textarea(attrs={'rows': 3}),
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ['amount_paid']
        widgets = {
            'amount_paid': forms.NumberInput(attrs={'step': '0.01'}),
        }

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

class MemberUpdateForm(forms.ModelForm):
    class Meta:
        model = Member
        fields = ['phone', 'address']