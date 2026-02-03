
from django.db import models
from django.contrib.auth.models import User


# Member table
class Member(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone = models.CharField(max_length=15)
    address = models.TextField()
    dob = models.DateField(null=True, blank=True)
    occupation = models.CharField(max_length=100, blank=True)
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    joined_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.user.get_full_name()




# Loan table
class Loan(models.Model):
    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    
    # Basic Loan Info
    loan_type = models.CharField(max_length=50, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.IntegerField(default=12)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2)
    purpose = models.TextField(blank=True)
    issued_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    
    # Financial Info
    monthly_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    employment_type = models.CharField(max_length=50, blank=True)
    existing_loans = models.CharField(max_length=10, blank=True)
    repayment_method = models.CharField(max_length=50, blank=True)
    remarks = models.TextField(blank=True)
    
    # Personal Loan Fields
    personal_reason = models.CharField(max_length=100, blank=True, null=True)
    existing_emi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Home Loan Fields
    property_type = models.CharField(max_length=50, blank=True, null=True)
    property_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    property_location = models.CharField(max_length=200, blank=True, null=True)
    construction_status = models.CharField(max_length=50, blank=True, null=True)
    property_documents = models.FileField(upload_to='loan_documents/', blank=True, null=True)
    co_applicant_name = models.CharField(max_length=100, blank=True, null=True)
    co_applicant_relation = models.CharField(max_length=50, blank=True, null=True)
    
    # Education Loan Fields
    student_name = models.CharField(max_length=100, blank=True, null=True)
    course_name = models.CharField(max_length=200, blank=True, null=True)
    institution_name = models.CharField(max_length=200, blank=True, null=True)
    institution_location = models.CharField(max_length=100, blank=True, null=True)
    course_duration = models.IntegerField(null=True, blank=True)
    admission_letter = models.FileField(upload_to='loan_documents/', blank=True, null=True)
    guardian_name = models.CharField(max_length=100, blank=True, null=True)
    guardian_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Business Loan Fields
    business_name = models.CharField(max_length=200, blank=True, null=True)
    business_type = models.CharField(max_length=100, blank=True, null=True)
    business_registration = models.CharField(max_length=100, blank=True, null=True)
    business_age = models.IntegerField(null=True, blank=True)
    annual_turnover = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    business_plan = models.FileField(upload_to='loan_documents/', blank=True, null=True)
    business_address = models.TextField(blank=True, null=True)
    
    # Agriculture Loan Fields
    farm_size = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    farming_type = models.CharField(max_length=100, blank=True, null=True)
    land_ownership = models.CharField(max_length=50, blank=True, null=True)
    crop_type = models.CharField(max_length=200, blank=True, null=True)
    land_documents = models.FileField(upload_to='loan_documents/', blank=True, null=True)
    irrigation_facility = models.CharField(max_length=20, blank=True, null=True)
    farming_experience = models.IntegerField(null=True, blank=True)
    
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('approved', 'Approved'),
            ('closed', 'Closed'),
        ],
        default='pending'
    )

    def __str__(self):
        return f"Loan {self.id} - {self.member}"

# Payment table
class Payment(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateField(auto_now_add=True)

    def __str__(self):
        return f"Payment {self.amount_paid} for Loan {self.loan.id}"


# Loan Application Details table - stores loan type specific information
class LoanApplicationDetail(models.Model):
    loan = models.OneToOneField(Loan, on_delete=models.CASCADE)

    # Personal Loan fields
    personal_reason = models.CharField(max_length=100, blank=True)
    existing_emi = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Home Loan fields
    property_type = models.CharField(max_length=50, blank=True)
    property_value = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    property_location = models.CharField(max_length=100, blank=True)
    construction_status = models.CharField(max_length=50, blank=True)
    co_applicant_name = models.CharField(max_length=100, blank=True)
    co_applicant_relation = models.CharField(max_length=50, blank=True)
    property_documents = models.TextField(blank=True)

    # Education Loan fields
    student_name = models.CharField(max_length=100, blank=True)
    course_name = models.CharField(max_length=100, blank=True)
    institution_name = models.CharField(max_length=100, blank=True)
    institution_location = models.CharField(max_length=50, blank=True)
    course_duration = models.IntegerField(null=True, blank=True)
    admission_letter = models.TextField(blank=True)
    guardian_name = models.CharField(max_length=100, blank=True)
    guardian_income = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)

    # Business Loan fields
    business_name = models.CharField(max_length=100, blank=True)
    business_type = models.CharField(max_length=50, blank=True)
    business_registration = models.CharField(max_length=50, blank=True)
    business_age = models.IntegerField(null=True, blank=True)
    annual_turnover = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    business_plan = models.TextField(blank=True)
    business_address = models.TextField(blank=True)

    # Agriculture Loan fields
    land_area_hectares = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    crop_type = models.CharField(max_length=50, blank=True)
    farming_experience_years = models.IntegerField(null=True, blank=True)
    irrigation_facility = models.BooleanField(default=False)
    previous_harvest_details = models.TextField(blank=True)
    equipment_owned = models.TextField(blank=True)

    def __str__(self):
        return f"Details for Loan #{self.loan.id}"

class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return self.message

class EMI(models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE)
    due_date = models.DateField()
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    is_paid = models.BooleanField(default=False)

    def __str__(self):
        return f"EMI for Loan {self.loan.id} - Due {self.due_date}"
    
    def mark_as_paid(self):
        self.is_paid = True
        self.save()
    def is_overdue(self):
        from datetime import date
        return not self.is_paid and date.today() > self.due_date
    def days_overdue(self):
        from datetime import date
        if self.is_overdue():
            return (date.today() - self.due_date).days
        return 0
    def calculate_late_fee(self, late_fee_rate):
        days_overdue = self.days_overdue()
        if days_overdue > 0:
            return self.amount * late_fee_rate * days_overdue / 100
        return 0
    def next_due_emi(self):
        from datetime import date
        if not self.is_paid and self.due_date >= date.today():
            return self
        return None
    
