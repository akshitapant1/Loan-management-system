from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth import logout, authenticate, login
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count, Q
from .models import Member, Loan, Payment 
from .forms import LoanApplicationForm, PaymentForm, ProfileUpdateForm, MemberUpdateForm, MemberForm
from datetime import datetime, date
from decimal import Decimal
import re
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from datetime import date, timedelta
from .models import EMI, Notification
from datetime import datetime, date, time
from django.utils import timezone
from .models import Loan, EMI
from decimal import Decimal
from .models import EMI

def generate_user_notifications(user):
    notifications = []

    # 1. Account creation (user.date_joined is aware)
    notifications.append({
        'message': f'Account created on {user.date_joined.strftime("%b %d, %Y")}',
        'created_at': user.date_joined
    })

    # 2. Loan applications
    loans = Loan.objects.filter(member__user=user).order_by('-issued_date')
    for loan in loans:
        # Loan applied
        issued_datetime = timezone.make_aware(
            datetime.combine(loan.issued_date, time.min)
        ) if isinstance(loan.issued_date, date) else loan.issued_date

        notifications.append({
            'message': f'Loan #{loan.id:04d} applied ({loan.loan_type or "General"})',
            'created_at': issued_datetime
        })

        # Loan approved/closed
        if loan.status == 'approved':
            notifications.append({
                'message': f'Loan #{loan.id:04d} approved',
                'created_at': issued_datetime
            })
        elif loan.status == 'closed':
            due_datetime = timezone.make_aware(
                datetime.combine(loan.due_date, time.min)
            ) if isinstance(loan.due_date, date) else loan.due_date

            notifications.append({
                'message': f'Loan #{loan.id:04d} closed',
                'created_at': due_datetime
            })

    # 3. EMI payments
    emis = EMI.objects.filter(loan__member__user=user).order_by('-due_date')
    for emi in emis:
        emi_datetime = timezone.make_aware(
            datetime.combine(emi.due_date, time.min)
        ) if isinstance(emi.due_date, date) else emi.due_date

        if emi.is_paid:
            notifications.append({
                'message': f'EMI of ₹{emi.amount} for Loan #{emi.loan.id:04d} paid',
                'created_at': emi_datetime
            })
        else:
            if emi.due_date < date.today():
                notifications.append({
                    'message': f'EMI of ₹{emi.amount} for Loan #{emi.loan.id:04d} overdue',
                    'created_at': emi_datetime
                })

    # Sort all notifications by created_at (descending)
    notifications = sorted(notifications, key=lambda x: x['created_at'], reverse=True)

    return notifications[:10]  # latest 10 notifications

@login_required
def user_dashboard(request):
    member = Member.objects.filter(user=request.user).first()

    if not member:
        return render(request, 'core/userdash.html', {
            'member': None,
            'notifications': []
        })

    active_loans = Loan.objects.filter(member=member, status='approved')
    pending_loans = Loan.objects.filter(member=member, status='pending')
    all_loans = Loan.objects.filter(member=member)

    # Outstanding
    total_outstanding = Decimal('0')
    for loan in active_loans:
        paid = Payment.objects.filter(loan=loan).aggregate(
            total=Sum('amount_paid')
        )['total'] or Decimal('0')
        total_outstanding += (loan.amount - paid)

    # Next EMI
    next_emi = EMI.objects.filter(
        loan__member=member,
        is_paid=False,
        due_date__gte=date.today()
    ).order_by('due_date').first()

    next_emi_due = next_emi.amount if next_emi else Decimal('0')
    next_due_date = next_emi.due_date if next_emi else None

    # Recent activity
    recent_activity = []

    for loan in all_loans[:5]:
        recent_activity.append({
            'date': loan.issued_date,
            'transaction': 'Loan Application',
            'loan_id': f'#LN{loan.id:04d}',
            'amount': loan.amount,
            'status': loan.status
        })

    for payment in Payment.objects.filter(loan__member=member).order_by('-payment_date')[:5]:
        recent_activity.append({
            'date': payment.payment_date,
            'transaction': 'EMI Payment',
            'loan_id': f'#LN{payment.loan.id:04d}',
            'amount': payment.amount_paid,
            'status': 'paid'
        })

    recent_activity.sort(key=lambda x: x['date'], reverse=True)

    context = {
        'member': member,
        'active_loans': active_loans,
        'pending_loans': pending_loans,
        'active_loans_count': active_loans.count(),
        'pending_loans_count': pending_loans.count(),
        'total_outstanding': total_outstanding,
        'next_emi_due': next_emi_due,
        'next_due_date': next_due_date,
        'credit_score': 742,  # mock
        'recent_activity': recent_activity[:10],
        'notifications': generate_user_notifications(request.user),
        'emis': EMI.objects.filter(loan__member=member)
    }

    return render(request, 'core/userdash.html', context)

   

@login_required
def admin_dashboard(request):
    if not request.user.is_staff:
        return redirect('login')
    
    # Statistics for admin
    total_members = Member.objects.count()
    total_loans = Loan.objects.count()
    pending_loans = Loan.objects.filter(status='pending').count()
    approved_loans = Loan.objects.filter(status='approved').count()
    
    total_disbursed = Loan.objects.filter(status__in=['approved', 'closed']).aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    total_collected = Payment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # Recent activities
    recent_loans = Loan.objects.all().order_by('-issued_date')[:5]
    recent_payments = Payment.objects.all().order_by('-payment_date')[:5]
    
    context = {
        'total_members': total_members,
        'total_loans': total_loans,
        'pending_loans': pending_loans,
        'approved_loans': approved_loans,
        'total_disbursed': total_disbursed,
        'total_collected': total_collected,
        'recent_loans': recent_loans,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'core/admin_dashboard.html', context)


def logout_view(request):
    logout(request)
    return redirect('login')


NEPAL_LOCATIONS = {
    'Koshi Pradesh': {
        'Jhapa': ['Bhadrapur', 'Mechinagar', 'Damak', 'Birtamod'],
        'Morang': ['Biratnagar', 'Urlabari', 'Rangeli', 'Letang'],
        'Sunsari': ['Dharan', 'Inaruwa', 'Itahari'],
        'Ilam': ['Ilam', 'Phidim', 'Fikkal'],
    },
    'Madhesh Pradesh': {
        'Saptari': ['Rajbiraj', 'Bodebarsain', 'Kanchanrup'],
        'Siraha': ['Siraha', 'Lahan', 'Dhangadhimai'],
        'Dhanusha': ['Janakpur', 'Chhireshwarnath', 'Dhanushadham'],
        'Mahottari': ['Jaleshwar', 'Bardibas', 'Gaushala'],
        'Sarlahi': ['Malangwa', 'Ishworpur', 'Lalbandi'],
    },
    'Bagmati Pradesh': {
        'Kathmandu': ['Kathmandu', 'Kirtipur', 'Budhanilkantha', 'Tokha', 'Chandragiri'],
        'Lalitpur': ['Lalitpur', 'Mahalaxmi', 'Godawari'],
        'Bhaktapur': ['Bhaktapur', 'Suryabinayak', 'Madhyapur Thimi'],
        'Kavrepalanchok': ['Dhulikhel', 'Banepa', 'Panauti'],
        'Makwanpur': ['Hetauda', 'Thaha', 'Bhimphedi'],
    },
    'Gandaki Pradesh': {
        'Kaski': ['Pokhara', 'Annapurna', 'Machhapuchchhre'],
        'Gorkha': ['Gorkha', 'Palungtar', 'Siranchowk'],
        'Lamjung': ['Besisahar', 'Dordi', 'Kwholasothar'],
        'Tanahu': ['Damauli', 'Byas', 'Myagde'],
    },
    'Lumbini Pradesh': {
        'Rupandehi': ['Butwal', 'Bhairahawa', 'Tilottama', 'Siddharthanagar'],
        'Kapilvastu': ['Kapilvastu', 'Banganga', 'Krishnanagar'],
        'Nawalparasi West': ['Ramgram', 'Sunwal', 'Pratappur'],
        'Dang': ['Ghorahi', 'Tulsipur', 'Lamahi'],
        'Banke': ['Nepalgunj', 'Kohalpur', 'Rapti Sonari'],
    },
    'Karnali Pradesh': {
        'Surkhet': ['Birendranagar', 'Bheriganga', 'Gurbhakot'],
        'Dailekh': ['Narayan', 'Dullu', 'Chamunda Bindrasaini'],
        'Jajarkot': ['Khalanga', 'Bheri', 'Chhedagad'],
        'Jumla': ['Chandannath', 'Kankasundari', 'Sinja'],
    },
    'Sudurpashchim Pradesh': {
        'Kailali': ['Dhangadhi', 'Tikapur', 'Lamkichuha', 'Bhajani'],
        'Kanchanpur': ['Mahendranagar', 'Bedkot', 'Belauri'],
        'Doti': ['Dipayal Silgadhi', 'Shikhar', 'Purbichauki'],
        'Dadeldhura': ['Amargadhi', 'Parshuram', 'Aalitaal'],
    }
}

import re
import socket
from django.core.exceptions import ValidationError
from django.core.validators import validate_email as django_validate_email
from django.contrib import messages
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.contrib.auth.models import User


def is_valid_domain(domain):
    """
    Check if domain is valid and likely to be a real email provider.
    Returns: (is_valid, error_message)
    """
    # Check domain format
    if not domain or len(domain) < 4:
        return False, "Email domain is too short!"
    
    # Domain must have at least one dot
    if '.' not in domain:
        return False, "Email domain is invalid!"
    
    # Get the top-level domain (TLD)
    parts = domain.split('.')
    tld = parts[-1].lower()
    
    # Check if TLD is valid (common TLDs)
    valid_tlds = [
        'com', 'org', 'net', 'edu', 'gov', 'mil', 'int',
        'co', 'io', 'ai', 'app', 'dev', 'tech', 'online',
        'np', 'in', 'uk', 'us', 'au', 'ca', 'de', 'fr', 'jp',
        'info', 'biz', 'name', 'pro', 'asia', 'tel', 'mobi'
    ]
    
    if tld not in valid_tlds:
        return False, f"Email domain extension '.{tld}' is not recognized!"
    
    # Check if domain name (before TLD) contains only numbers
    domain_name = parts[-2] if len(parts) >= 2 else ""
    if domain_name.isdigit():
        return False, "Email domain cannot be only numbers (e.g., 123.com is invalid)!"
    
    # Domain should have valid characters
    if not re.match(r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?)*$', domain):
        return False, "Email domain contains invalid characters!"
    
    return True, None


def verify_email_domain_advanced(email):
    """
    Advanced domain verification using DNS and socket checks
    Returns: (is_valid, error_message)
    """
    try:
        domain = email.split('@')[1]
        
        # First check if domain format is valid
        is_valid, error_msg = is_valid_domain(domain)
        if not is_valid:
            return False, error_msg
        
        # Try to resolve the domain using socket
        try:
            # Try to get address info for the domain
            socket.getaddrinfo(domain, 'smtp', socket.AF_UNSPEC, socket.SOCK_STREAM)
            
            # Additional check: try to get MX records indirectly
            # by attempting to resolve mail server hostnames
            try:
                socket.gethostbyname(domain)
                return True, None
            except socket.gaierror:
                # Domain doesn't resolve
                return False, "Email domain does not exist or cannot receive emails!"
                
        except socket.gaierror:
            # Domain doesn't exist
            return False, "Email domain does not exist!"
        except Exception as e:
            # If we can't verify due to network issues, allow it through
            # but only if the domain passed format checks
            return True, None
            
    except Exception as e:
        return True, None


def validate_email_comprehensive(email):
    """
    Comprehensive email validation with enhanced checks
    Returns: (is_valid, error_message)
    """
    print(f"\n{'='*60}")
    print(f"🔍 VALIDATING EMAIL: {email}")
    print(f"{'='*60}")
    
    # Step 1: Basic format validation
    try:
        django_validate_email(email)
        print("✅ Step 1: Django format validation passed")
    except ValidationError:
        print("❌ Step 1: Invalid email format")
        return False, "Please enter a valid email format!"
    
    # Step 2: Check minimum length and basic structure
    if len(email) < 5 or email.count('@') != 1:
        print("❌ Step 2: Invalid email structure")
        return False, "Please enter a valid email address!"
    
    local_part, domain = email.rsplit('@', 1)
    print(f"📧 Local part: '{local_part}', Domain: '{domain}'")
    
    # Check local part (before @)
    if len(local_part) < 1 or len(local_part) > 64:
        print("❌ Step 2: Invalid local part length")
        return False, "Email address is invalid!"
    
    # Local part should not be all numbers
    if local_part.replace('.', '').replace('_', '').replace('-', '').isdigit():
        print("❌ Step 2: Local part cannot be only numbers")
        return False, "Email username cannot be only numbers!"
    
    # Check domain part (after @)
    if len(domain) < 3 or '.' not in domain:
        print("❌ Step 2: Invalid domain structure")
        return False, "Email domain is invalid!"
    
    print("✅ Step 2: Structure validation passed")
    
    # Step 3: Domain format validation
    is_valid, error_msg = is_valid_domain(domain)
    if not is_valid:
        print(f"❌ Step 3: {error_msg}")
        return False, error_msg
    
    print("✅ Step 3: Domain format is valid")
    
    # Step 4: Check for common email typos
    common_typos = {
        'gmial.com': 'gmail.com',
        'gmai.com': 'gmail.com',
        'gmil.com': 'gmail.com',
        'gmailc.om': 'gmail.com',
        'gmall.com': 'gmail.com',
        'yahooo.com': 'yahoo.com',
        'yaho.com': 'yahoo.com',
        'yahoomail.com': 'yahoo.com',
        'hotmial.com': 'hotmail.com',
        'hotmil.com': 'hotmail.com',
        'hotmai.com': 'hotmail.com',
        'outlok.com': 'outlook.com',
        'outloo.com': 'outlook.com',
        'outlok.com': 'outlook.com',
    }
    
    domain_lower = domain.lower()
    if domain_lower in common_typos:
        suggested = local_part + '@' + common_typos[domain_lower]
        print(f"❌ Step 4: Typo detected - suggesting {suggested}")
        return False, f"Did you mean {suggested}?"
    
    print("✅ Step 4: No common typos detected")
    
    # Step 5: Block disposable/temporary email providers
    disposable_domains = [
        'tempmail.com', 'guerrillamail.com', '10minutemail.com',
        'throwaway.email', 'mailinator.com', 'trashmail.com',
        'fakeinbox.com', 'temp-mail.org', 'getnada.com',
        'maildrop.cc', 'yopmail.com', 'emailondeck.com',
        'sharklasers.com', 'guerrillamail.info', 'grr.la',
        'spam4.me', 'tempinbox.com', 'mohmal.com',
        'throwaway.com', 'spamgourmet.com', 'incognitomail.com'
    ]
    
    if domain_lower in disposable_domains:
        print(f"❌ Step 5: Disposable email detected")
        return False, "Temporary/disposable email addresses are not allowed!"
    
    print("✅ Step 5: Not a disposable email")
    
    # Step 6: Verify domain exists (DNS check)
    is_valid, error_msg = verify_email_domain_advanced(email)
    if not is_valid:
        print(f"❌ Step 6: Domain verification failed - {error_msg}")
        return False, error_msg
    
    print("✅ Step 6: Domain verification passed")
    
    # Step 7: Additional pattern checks
    if '..' in email or email.startswith('.') or email.endswith('.'):
        print("❌ Step 7: Invalid dot pattern")
        return False, "Email address contains invalid characters!"
    
    # Check for suspicious patterns in local part
    if re.search(r'^[0-9]+@', email):
        print("❌ Step 7: Email starts with only numbers")
        return False, "Email address cannot start with only numbers!"
    
    print("✅ Step 7: Pattern validation passed")
    
    # Step 8: Check for known valid email providers (common ones)
    known_providers = [
        'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com',
        'icloud.com', 'protonmail.com', 'mail.com', 'aol.com',
        'live.com', 'msn.com', 'ymail.com', 'zoho.com',
        'proton.me', 'hey.com', 'fastmail.com'
    ]
    
    # If it's a known provider, we're good
    if domain_lower in known_providers:
        print(f"✅ Step 8: Known email provider ({domain_lower})")
        print(f"{'='*60}")
        print(f"✅ EMAIL VALIDATION SUCCESSFUL!")
        print(f"{'='*60}\n")
        return True, None
    
    # For unknown providers, domain must have resolved in step 6
    print(f"ℹ️ Step 8: Unknown provider but domain verified")
    print(f"{'='*60}")
    print(f"✅ EMAIL VALIDATION SUCCESSFUL!")
    print(f"{'='*60}\n")
    
    return True, None


def register_view(request):
    if request.method == 'POST':
        print("\n" + "="*60)
        print("🚀 REGISTRATION ATTEMPT STARTED")
        print("="*60)

        # -----------------------------
        # BASIC USER INFO
        # -----------------------------
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        username = request.POST.get('username', '').strip()
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm-password')
        phone = request.POST.get('phone')

        print(f"📝 Form Data Received:")
        print(f"   Name: {first_name} {last_name}")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Phone: {phone}")

        # -----------------------------
        # ADDRESS (NESTED)
        # -----------------------------
        province = request.POST.get('province')
        district = request.POST.get('district')
        city = request.POST.get('city')
        address = f"{city}, {district}, {province}"

        # -----------------------------
        # OTHER DETAILS
        # -----------------------------
        dob = request.POST.get('dob')
        occupation = request.POST.get('occupation')
        monthly_income = request.POST.get('monthly_income')
        terms = request.POST.get('terms')

        # -----------------------------
        # NAME VALIDATION
        # -----------------------------
        if not re.match(r'^[A-Za-z ]+$', first_name):
            print("❌ VALIDATION FAILED: Invalid first name")
            messages.error(request, "First name can contain letters only!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        if not re.match(r'^[A-Za-z ]+$', last_name):
            print("❌ VALIDATION FAILED: Invalid last name")
            messages.error(request, "Last name can contain letters only!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        if len(first_name) < 2 or len(last_name) < 2:
            print("❌ VALIDATION FAILED: Name too short")
            messages.error(request, "First and last name must be at least 2 characters!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # PASSWORD VALIDATION
        # -----------------------------
        if password != confirm_password:
            print("❌ VALIDATION FAILED: Passwords don't match")
            messages.error(request, "Passwords do not match!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        if len(password) < 8:
            print("❌ VALIDATION FAILED: Password too short")
            messages.error(request, "Password must be at least 8 characters long!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # TERMS VALIDATION
        # -----------------------------
        if not terms:
            print("❌ VALIDATION FAILED: Terms not accepted")
            messages.error(request, "You must agree to the Terms & Conditions!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # COMPREHENSIVE EMAIL VALIDATION
        # -----------------------------
        print("\n🔐 Starting Email Validation...")
        is_valid, error_message = validate_email_comprehensive(email)
        if not is_valid:
            print(f"❌ EMAIL VALIDATION FAILED: {error_message}")
            messages.error(request, error_message)
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # Check if email already registered
        if User.objects.filter(email=email).exists():
            print("❌ VALIDATION FAILED: Email already registered")
            messages.error(request, "Email already registered!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        print("✅ Email validation passed!")

        # -----------------------------
        # PHONE VALIDATION (NEPAL)
        # -----------------------------
        if not re.match(r'^(98|97)\d{8}$', phone):
            print("❌ VALIDATION FAILED: Invalid phone number")
            messages.error(request, "Enter a valid Nepali phone number!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # USERNAME VALIDATION
        # -----------------------------
        if not re.match(r'^[a-zA-Z0-9_]{8,}$', username):
            print("❌ VALIDATION FAILED: Invalid username format")
            messages.error(
                request,
                "Username must be at least 8 characters and contain only letters, numbers, and underscore!"
            )
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        if User.objects.filter(username=username).exists():
            print("❌ VALIDATION FAILED: Username already exists")
            messages.error(request, "Username already exists!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # ADDRESS VALIDATION
        # -----------------------------
        if not province or not district or not city:
            print("❌ VALIDATION FAILED: Incomplete address")
            messages.error(request, "Please select Province, District, and City!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # MONTHLY INCOME VALIDATION
        # -----------------------------
        try:
            income_value = float(monthly_income)
            if income_value < 10000:
                print("❌ VALIDATION FAILED: Income too low")
                messages.error(request, "Monthly income must be at least NPR 10,000!")
                return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})
        except (ValueError, TypeError):
            print("❌ VALIDATION FAILED: Invalid income value")
            messages.error(request, "Please enter a valid monthly income!")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

        # -----------------------------
        # CREATE USER & MEMBER
        # -----------------------------
        try:
            print("\n✅ All validations passed! Creating user...")
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )

            Member.objects.create(
                user=user,
                phone=phone,
                address=address,
                dob=dob if dob else None,
                occupation=occupation,
                monthly_income=monthly_income
            )

            print(f"✅ User created successfully: {username}")

            # Auto login
            user = authenticate(request, username=username, password=password)
            if user:
                login(request, user)
                messages.success(
                    request,
                    f"Welcome {first_name}! Your account has been created successfully."
                )
                print("✅ User logged in successfully")
                print("="*60 + "\n")
                return redirect('user_dashboard')

            messages.success(request, "Account created successfully. Please login.")
            print("✅ User created, redirecting to login")
            print("="*60 + "\n")
            return redirect('login')

        except Exception as e:
            print(f"❌ ERROR creating account: {str(e)}")
            messages.error(request, f"Error creating account: {str(e)}")
            return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

    return render(request, 'core/register.html', {'nepal_locations': NEPAL_LOCATIONS})

def about_view(request):
    return render(request, 'core/about.html')


def contact_view(request):
    return render(request, 'core/contact.html')


def index_view(request):
    return render(request, 'core/index.html')


def loans_view(request):
   
    loans = Loan.objects.select_related('member').order_by('-issued_date')
    
    # Calculate statistics
    total_loans = loans.count()
    total_amount = loans.aggregate(total=Sum('amount'))['total'] or 0
    
    context = {
        'loans': loans,
        'total_loans': total_loans,
        'total_amount': total_amount,
    }
    return render(request, 'core/loans.html', context)


@login_required
def apply_loan(request):
    member, created = Member.objects.get_or_create(
        user=request.user,
        defaults={'phone': '', 'address': ''}
    )
    
    if request.method == 'POST':
        try:
            # Basic Loan Info
            loan_type = request.POST.get('loan_type')
            amount = request.POST.get('amount')
            duration = request.POST.get('duration')
            purpose = request.POST.get('purpose')
            interest_rate = request.POST.get('interest_rate', '12.00')
            due_date = request.POST.get('due_date')
            
            # Financial Info
            monthly_income = request.POST.get('monthly_income')
            employment_type = request.POST.get('employment_type')
            existing_loans = request.POST.get('existing_loans')
            repayment_method = request.POST.get('repayment_method')
            remarks = request.POST.get('remarks', '')
            
            # Create the loan with basic info
            loan = Loan.objects.create(
                member=member,
                loan_type=loan_type,
                amount=amount,
                duration_months=duration,
                interest_rate=interest_rate,
                purpose=purpose,
                due_date=due_date,
                monthly_income=monthly_income,
                employment_type=employment_type,
                existing_loans=existing_loans,
                repayment_method=repayment_method,
                remarks=remarks,
                status='pending'
            )
            
            # Save loan-specific fields based on loan type
            if loan_type == 'Personal Loan':
                loan.personal_reason = request.POST.get('personal_reason')
                loan.existing_emi = request.POST.get('existing_emi') or 0
            
            elif loan_type == 'Home Loan':
                loan.property_type = request.POST.get('property_type')
                loan.property_value = request.POST.get('property_value')
                loan.property_location = request.POST.get('property_location')
                loan.construction_status = request.POST.get('construction_status')
                loan.co_applicant_name = request.POST.get('co_applicant_name')
                loan.co_applicant_relation = request.POST.get('co_applicant_relation')
                
                # Handle file upload
                if 'property_documents' in request.FILES:
                    loan.property_documents = request.FILES['property_documents']
            
            elif loan_type == 'Education Loan':
                loan.student_name = request.POST.get('student_name')
                loan.course_name = request.POST.get('course_name')
                loan.institution_name = request.POST.get('institution_name')
                loan.institution_location = request.POST.get('institution_location')
                loan.course_duration = request.POST.get('course_duration')
                loan.guardian_name = request.POST.get('guardian_name')
                loan.guardian_income = request.POST.get('guardian_income')
                
                # Handle file upload
                if 'admission_letter' in request.FILES:
                    loan.admission_letter = request.FILES['admission_letter']
            
            elif loan_type == 'Business Loan':
                loan.business_name = request.POST.get('business_name')
                loan.business_type = request.POST.get('business_type')
                loan.business_registration = request.POST.get('business_registration')
                loan.business_age = request.POST.get('business_age')
                loan.annual_turnover = request.POST.get('annual_turnover')
                loan.business_address = request.POST.get('business_address')
                
                # Handle file upload
                if 'business_plan' in request.FILES:
                    loan.business_plan = request.FILES['business_plan']
            
            elif loan_type == 'Agriculture Loan':
                loan.farm_size = request.POST.get('farm_size')
                loan.farming_type = request.POST.get('farming_type')
                loan.land_ownership = request.POST.get('land_ownership')
                loan.crop_type = request.POST.get('crop_type')
                loan.irrigation_facility = request.POST.get('irrigation_facility')
                loan.farming_experience = request.POST.get('farming_experience')
                
                # Handle file upload
                if 'land_documents' in request.FILES:
                    loan.land_documents = request.FILES['land_documents']
            
            # Save the updated loan
            loan.save()
            
            messages.success(request, f'🎉 Your {loan_type} application for NPR {amount} has been submitted successfully! Application ID: #{loan.id}. Please wait for admin approval.')
            return redirect('loan_status')
            
        except Exception as e:
            messages.error(request, f'❌ Error submitting loan application: {str(e)}')
            return render(request, 'core/apply_loan.html')
    
    return render(request, 'core/apply_loan.html')


@login_required
def loan_status(request):
    member = get_object_or_404(Member, user=request.user)
    loans = Loan.objects.filter(member=member).order_by('-issued_date')

    # Prepare total_paid for each loan
    for loan in loans:
        total = loan.payment_set.aggregate(total_paid=Sum('amount_paid'))['total_paid'] or 0
        loan.total_paid = total
        loan.remaining = loan.amount - total

    context = {
        'loans': loans,
    }
    return render(request, 'core/loan_status.html', context)


@login_required
def loan_history(request):
    member = get_object_or_404(Member, user=request.user)
    loans = Loan.objects.filter(member=member).order_by('-issued_date')
    
    # Calculate statistics
    total_borrowed = Decimal('0')
    total_paid_all = Decimal('0')
    total_outstanding = Decimal('0')
    
    # Calculate total paid for each loan
    loan_data = []
    for loan in loans:
        total_paid = Payment.objects.filter(loan=loan).aggregate(
            total=Sum('amount_paid')
        )['total']
        
        # Handle None case
        total_paid = Decimal('0') if total_paid is None else total_paid
        
        remaining = loan.amount - total_paid
        
        # Add to totals
        total_borrowed += loan.amount
        total_paid_all += total_paid
        
        # Only count as outstanding if loan is approved (active)
        if loan.status == 'approved':
            total_outstanding += remaining
        
        loan_data.append({
            'loan': loan,
            'total_paid': total_paid,
            'remaining': remaining,
            'payments': Payment.objects.filter(loan=loan).order_by('-payment_date')
        })
    
    context = {
        'loan_data': loan_data,
        'total_borrowed': total_borrowed,
        'total_paid_all': total_paid_all,
        'total_outstanding': total_outstanding,
    }
    return render(request, 'core/loan_history.html', context)

@login_required
def profile(request):
    try:
        member = Member.objects.get(user=request.user)
        loans = Loan.objects.filter(member=member).order_by('-issued_date')
        
        # Calculate total paid for each loan
        loan_data = []
        for loan in loans:
            total_paid = Payment.objects.filter(loan=loan).aggregate(
                total=Sum('amount_paid')
            )['total']
            # Handle None case
            total_paid = Decimal('0') if total_paid is None else total_paid
            
            loan_data.append({
                'loan': loan,
                'total_paid': total_paid,
            })
        
        context = {
            'member': member,
            'loan_data': loan_data,
        }
        
    except Member.DoesNotExist:
        context = {
            'member': None,
            'loan_data': [],
        }
    
    return render(request, 'core/profile.html', context)


@login_required
def emi_calculator(request):
    result = None
    
    if request.method == 'POST':
        try:
            principal = float(request.POST.get('principal', 0))
            rate = float(request.POST.get('rate', 0))
            tenure = int(request.POST.get('tenure', 0))
            
            # EMI Calculation
            monthly_rate = rate / (12 * 100)
            
            if monthly_rate > 0:
                emi = principal * monthly_rate * ((1 + monthly_rate) ** tenure) / (((1 + monthly_rate) ** tenure) - 1)
            else:
                emi = principal / tenure
            
            total_amount = emi * tenure
            total_interest = total_amount - principal
            
            result = {
                'emi': round(emi, 2),
                'total_amount': round(total_amount, 2),
                'total_interest': round(total_interest, 2),
                'principal': principal,
            }
        except (ValueError, ZeroDivisionError):
            messages.error(request, 'Invalid input values!')
    
    return render(request, 'core/emi_calculator.html', {'result': result})


# Admin Views
@login_required
def admin_loans(request):
    if not request.user.is_staff:
        return redirect('login')

    # Handle loan verify / reject
    if request.method == 'POST':
        loan_id = request.POST.get('loan_id')
        action = request.POST.get('action')

        loan = get_object_or_404(Loan, id=loan_id)

        if action == 'verify':
            loan.status = 'approved'
            loan.issued_date = date.today()
            loan.save()

            # ✅ SEND NOTIFICATION
            Notification.objects.create(
                user=loan.member.user,
                message=(
                    f"Your loan application (Loan ID #{loan.id}) has been VERIFIED. "
                    f"Please visit our office with original documents."
                )
            )

            messages.success(
                request,
                f"Loan #{loan.id} verified successfully and user notified."
            )

        elif action == 'reject':
            loan.status = 'closed'
            loan.save()

            Notification.objects.create(
                user=loan.member.user,
                message=(
                    f"Your loan application (Loan ID #{loan.id}) has been rejected."
                )
            )

            messages.warning(request, f"Loan #{loan.id} rejected.")

        return redirect('admin_loans')

    # Fetch loans
    loans = Loan.objects.select_related('member', 'member__user').order_by('-issued_date')

    # Filter
    status_filter = request.GET.get('status', '')
    if status_filter:
        loans = loans.filter(status=status_filter)

    context = {
        'loans': loans,
        'status_filter': status_filter,
    }
    return render(request, 'core/admin_loans.html', context)

@login_required
def admin_applicants(request):
    if not request.user.is_staff:
        return redirect('login')
    
    members = Member.objects.all().order_by('-joined_date')
    
    # Add loan statistics for each member
    member_data = []
    for member in members:
        total_loans = Loan.objects.filter(member=member).count()
        active_loans = Loan.objects.filter(member=member, status='approved').count()
        total_borrowed = Loan.objects.filter(
            member=member, 
            status__in=['approved', 'closed']
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        member_data.append({
            'member': member,
            'total_loans': total_loans,
            'active_loans': active_loans,
            'total_borrowed': total_borrowed,
        })
    
    context = {
        'member_data': member_data,
    }
    return render(request, 'core/admin_applicants.html', context)


@login_required
def admin_reports(request):
    if not request.user.is_staff:
        return redirect('login')
    
    # Overall statistics
    total_members = Member.objects.count()
    total_loans = Loan.objects.count()
    total_disbursed = Loan.objects.filter(status__in=['approved', 'closed']).aggregate(
        total=Sum('amount')
    )['total'] or 0
    total_collected = Payment.objects.aggregate(total=Sum('amount_paid'))['total'] or 0
    
    # Loan status breakdown
    pending_loans = Loan.objects.filter(status='pending').count()
    approved_loans = Loan.objects.filter(status='approved').count()
    closed_loans = Loan.objects.filter(status='closed').count()
    
    # Monthly data (last 6 months)
    from datetime import timedelta
    from django.utils import timezone
    
    six_months_ago = timezone.now().date() - timedelta(days=180)
    recent_loans = Loan.objects.filter(issued_date__gte=six_months_ago)
    
    context = {
        'total_members': total_members,
        'total_loans': total_loans,
        'total_disbursed': total_disbursed,
        'total_collected': total_collected,
        'outstanding': total_disbursed - total_collected,
        'pending_loans': pending_loans,
        'approved_loans': approved_loans,
        'closed_loans': closed_loans,
        'recent_loans': recent_loans,
    }
    
    return render(request, 'core/admin_reports.html', context)


@login_required
def admin_settings(request):
    if not request.user.is_staff:
        return redirect('login')
    
    if request.method == 'POST':
        # Handle settings update
        messages.success(request, 'Settings updated successfully!')
        return redirect('admin_settings')
    
    return render(request, 'core/admin_settings.html')


# Additional view for making payments
@login_required
def make_payment(request, loan_id):
    loan = get_object_or_404(Loan, id=loan_id)
    member = get_object_or_404(Member, user=request.user)
    
    # Check if loan belongs to user
    if loan.member != member:
        messages.error(request, 'Unauthorized access!')
        return redirect('loan_history')
    
    if loan.status != 'approved':
        messages.error(request, 'Can only make payments for approved loans!')
        return redirect('loan_history')
    
    if request.method == 'POST':
        form = PaymentForm(request.POST)
        if form.is_valid():
            payment = form.save(commit=False)
            payment.loan = loan
            
            # Check if payment doesn't exceed remaining amount
            total_paid = Payment.objects.filter(loan=loan).aggregate(
                total=Sum('amount_paid')
            )['total'] or 0
            
            remaining = loan.amount - total_paid
            
            if payment.amount_paid > remaining:
                messages.error(request, f'Payment amount exceeds remaining balance of Rs. {remaining}')
            else:
                payment.save()
                
                # Check if loan is fully paid
                new_total_paid = total_paid + payment.amount_paid
                if new_total_paid >= loan.amount:
                    loan.status = 'closed'
                    loan.save()
                    messages.success(request, 'Payment successful! Loan fully paid and closed.')
                else:
                    messages.success(request, 'Payment recorded successfully!')
                
                return redirect('loan_history')
    else:
        form = PaymentForm()
    
    # Calculate remaining amount
    total_paid = Payment.objects.filter(loan=loan).aggregate(
        total=Sum('amount_paid')
    )['total'] or 0
    remaining = loan.amount - total_paid
    
    context = {
        'form': form,
        'loan': loan,
        'total_paid': total_paid,
        'remaining': remaining,
    }
    
    return render(request, 'core/make_payment.html', context)



def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            
            # Redirect based on user type
            if user.is_staff or user.is_superuser:
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                return redirect('admin_dashboard')
            else:
                messages.success(request, f'Welcome back, {user.get_full_name() or user.username}!')
                return redirect('user_dashboard')
        else:
            messages.error(
    request,
    'The username or password you entered is incorrect. Please check and try again.'
)

            return render(request, 'core/login.html')
    
    return render(request, 'core/login.html')


def generate_emi_notifications():

    today = date.today()
    upcoming_date = today + timedelta(days=3)

    emis = EMI.objects.filter(status='Unpaid')

    for emi in emis:
        user = emi.loan.user

        # Upcoming EMI (3 days before)
        if emi.due_date == upcoming_date:
            Notification.objects.get_or_create(
                user=user,
                message=f"Upcoming EMI of Rs. {emi.amount} due on {emi.due_date}"
            )

        # Due today
        elif emi.due_date == today:
            Notification.objects.get_or_create(
                user=user,
                message=f"Your EMI of Rs. {emi.amount} is due today"
            )

        # Overdue EMI
        elif emi.due_date < today:
            Notification.objects.get_or_create(
                user=user,
                message=f"Your EMI of Rs. {emi.amount} is overdue"
            )

@login_required
def admin_loan_detail(request, loan_id):
    if not request.user.is_staff:
        return redirect('login')

    loan = get_object_or_404(
        Loan.objects.select_related('member', 'member__user'),
        id=loan_id
    )

    return render(request, 'core/admin_loan_detail.html', {'loan': loan})


def generate_emis_for_loan(loan):
    if EMI.objects.filter(loan=loan).exists():
        return  # avoid duplicate EMIs

    P = Decimal(loan.amount)
    R = Decimal(loan.interest_rate) / Decimal(12 * 100)
    N = loan.duration_months

    if R > 0:
        emi_amount = (P * R * (1 + R) ** N) / ((1 + R) ** N - 1)
    else:
        emi_amount = P / N

    emi_amount = emi_amount.quantize(Decimal("0.01"))

    due_date = loan.issued_date
    for _ in range(N):
        due_date = loan.issued_date + timedelta(days=30 * loan.tenure)


        EMI.objects.create(
            loan=loan,
            due_date=due_date,
            amount=emi_amount
        )

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone
from .models import EMI, Payment, Loan, Notification

@login_required
def pay_emi(request, emi_id):
    emi = get_object_or_404(EMI, id=emi_id, loan__member__user=request.user)

    if emi.is_paid:
        messages.info(request, "EMI already paid")
        return redirect('user_dashboard')

    # Mark EMI paid
    emi.is_paid = True
    emi.save()

    # Create payment record
    Payment.objects.create(
        loan=emi.loan,
        amount_paid=emi.amount
    )

    # Notification
    Notification.objects.create(
        user=request.user,
        message=f"EMI of ₹{emi.amount} paid successfully for Loan #{emi.loan.id}"
    )

    # Close loan if all EMIs paid
    if not EMI.objects.filter(loan=emi.loan, is_paid=False).exists():
        emi.loan.status = 'closed'
        emi.loan.save()

        Notification.objects.create(
            user=request.user,
            message=f"Loan #{emi.loan.id} has been fully paid and closed 🎉"
        )

    messages.success(request, "EMI paid successfully")
    return redirect('user_dashboard')

