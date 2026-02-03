from django.urls import path
from . import views

urlpatterns = [
    path('', views.index_view, name='index'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),

    path('about/', views.about_view, name='about'),
    path('contact/', views.contact_view, name='contact'),
    path('loans/', views.loans_view, name='loans'),

    path('apply-loan/', views.apply_loan, name='apply_loan'),
    path('loan-status/', views.loan_status, name='loan_status'),
    path('loan-history/', views.loan_history, name='loan_history'),
    path('profile/', views.profile, name='profile'),
    path('emi-calculator/', views.emi_calculator, name='emi_calculator'),

    path('make-payment/<int:loan_id>/', views.make_payment, name='make_payment'),

    # admin internal pages
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin_loans/', views.admin_loans, name='admin_loans'),
    path('applicants/', views.admin_applicants, name='admin_applicants'),
    path('reports/', views.admin_reports, name='admin_reports'),
    path('settings/', views.admin_settings, name='admin_settings'),
    path('pay-emi/<int:emi_id>/', views.pay_emi, name='pay_emi'),
    path('admin/loans/<int:loan_id>/', views.admin_loan_detail, name='admin_loan_detail'),

]
