from django.contrib import admin
from .models import Member, Loan, Payment

# My MOdels
admin.site.register(Member)
admin.site.register(Loan)
admin.site.register(Payment)

