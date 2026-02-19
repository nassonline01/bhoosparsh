from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView
from . import (
    views,
    seller_views,
    buyer_views,  
)
from .views import change_password_view



    
urlpatterns = [
    
    
    # ======================================================
    # Buyer dashboard URLs
    # ======================================================
    path('buyer/dashboard/', buyer_views.buyer_dashboard, name='buyer_dashboard'),
    path('buyer/properties/', buyer_views.buyer_properties, name='buyer_properties'),
    path('buyer/property/<slug:slug>/', buyer_views.buyer_property_detail, name='buyer_property_detail'),
    path('buyer/favorites/', buyer_views.buyer_favorites, name='buyer_favorites'),
    path('buyer/comparisons/', buyer_views.buyer_comparisons, name='buyer_comparisons'),
    path('buyer/comparison/<int:pk>/', buyer_views.buyer_comparison_detail, name='buyer_comparison_detail'),
    path('buyer/site-visits/', buyer_views.buyer_site_visits, name='buyer_site_visits'),
    path('buyer/schedule-visit/<int:property_id>/', buyer_views.buyer_schedule_visit, name='buyer_schedule_visit'),
    path('buyer/profile/', buyer_views.buyer_profile, name='buyer_profile'),
    
    path('visits/<int:visit_id>/confirm/', buyer_views.confirm_visit, name='confirm_visit'),
    path('visits/<int:visit_id>/reschedule/', buyer_views.reschedule_visit, name='reschedule_visit'),
    path('visits/<int:visit_id>/cancel/', buyer_views.cancel_visit, name='cancel_visit'),
    
    # Buyer AJAX URLs
    path('buyer/ajax/toggle-favorite/', buyer_views.ajax_toggle_favorite, name='ajax_toggle_favorite'),
    path('buyer/ajax/send-inquiry/', buyer_views.ajax_send_inquiry, name='ajax_send_inquiry'),
    path('buyer/ajax/send-followup/', buyer_views.ajax_send_followup, name='ajax_send_followup'),
    path('buyer/ajax/delete-inquiry/<int:inquiry_id>/', buyer_views.ajax_delete_inquiry, name='ajax_delete_inquiry'),
    path('buyer/ajax/update-favorite-status/', buyer_views.ajax_update_favorite_status, name='ajax_update_favorite_status'),
    
    # AJAX URLs for favorites
    path('ajax/remove-favorite/', buyer_views.ajax_remove_favorite, name='ajax_remove_favorite'),
    
    # Comparison URLs
    path('comparisons/json/', buyer_views.comparison_lists_json, name='comparison_lists_json'),
    path('comparison/<int:pk>/add/', buyer_views.add_to_comparison, name='add_to_comparison'),
    path('comparisons/create/', buyer_views.create_comparison, name='create_comparison'),
    
    # Buyer Inquiries URLs
    path('buyer/inquiries/', buyer_views.buyer_inquiries, name='buyer_inquiries'),
    path('buyer/inquiry/<int:pk>/', buyer_views.buyer_inquiry_detail, name='buyer_inquiry_detail'),
    path('buyer/inquiry/<int:inquiry_id>/followup/', buyer_views.ajax_send_followup, name='ajax_send_followup'),
    path('buyer/inquiry/<int:inquiry_id>/delete/', buyer_views.ajax_delete_inquiry, name='ajax_delete_inquiry'),
    path('buyer/inquiry/<int:inquiry_id>/details/', buyer_views.ajax_get_inquiry_details, name='ajax_get_inquiry_details'),
    path('buyer/inquiry/export/', buyer_views.ajax_export_inquiries, name='buyer_inquiry_export'),

    # AJAX endpoints
    path('buyer/ajax/update-inquiry-status/', buyer_views.ajax_update_inquiry_status, name='ajax_update_inquiry_status'),
        
    # ======================================================
    # SELLER DASHBOARD VIEWS
    # ======================================================
    path('seller/dashboard/', seller_views.seller_dashboard, name='seller_dashboard'),
    path('seller/profile/', seller_views.seller_profile, name='seller_profile'),
    path('seller/packages/', seller_views.seller_packages, name='seller_packages'),
    # path('seller/leads/', seller_views.seller_leads, name='seller_leads'),
    # path('seller/leads/<int:pk>/', seller_views.seller_lead_detail, name='seller_lead_detail'),
    # path('seller/leads/export/', seller_views.seller_lead_export, name='seller_lead_export'),
    path('seller/analytics/', seller_views.seller_analytics, name='seller_analytics'),
    path('seller/settingss/', seller_views.seller_settings, name='seller_settings'),
    
    # Property management URLs
    path('seller/properties/', seller_views.seller_properties, name='seller_properties'),
    path('seller/properties/create/', seller_views.seller_property_create, name='seller_property_create'),
    path('seller/properties/<int:pk>/edit/', seller_views.seller_property_edit, name='seller_property_edit'),
    path('seller/properties/<int:pk>/delete/', seller_views.seller_property_delete, name='seller_property_delete'),
    path('property/<int:pk>/', seller_views.seller_property_detail, name='seller_property_detail'),
    path('property/<int:pk>/duplicate/', seller_views.seller_property_duplicate, name='seller_property_duplicate'),
    path('property/<int:pk>/report/', seller_views.seller_property_report, name='seller_property_report'),

    # AJAX URLs
    path('seller/ajax/update-lead-status/', seller_views.ajax_update_lead_status, name='ajax_update_lead_status'),
    path('ajax/update-property-status/', seller_views.ajax_update_property_status, name='ajax_update_property_status'),
    path('ajax/apply-boost/', seller_views.ajax_apply_boost, name='ajax_apply_boost'),
    path('ajax/property-details/<int:pk>/', seller_views.ajax_property_details, name='ajax_property_details'),

    
     # Seller Leads URLs
    path('seller/leads/', seller_views.seller_leads, name='seller_leads'),
    path('seller/lead/<int:pk>/', seller_views.seller_lead_detail, name='seller_lead_detail'),
    path('seller/lead/<int:lead_id>/followup/', seller_views.ajax_send_followup, name='ajax_send_followup'),
    path('seller/lead/<int:lead_id>/delete/', seller_views.ajax_delete_lead, name='ajax_delete_lead'),
    path('seller/lead/export/', seller_views.ajax_export_leads, name='seller_lead_export'),
    path('seller/lead/stats/', seller_views.ajax_lead_stats, name='ajax_lead_stats'),
    
    # AJAX endpoints
    path('seller/ajax/update-lead-status/', seller_views.ajax_update_lead_status, name='ajax_update_lead_status'),

    # ======================================================
    # HOME & CORE PAGES
    # ======================================================
    # Home page
    path('', views.home_view, name='home'),
    
    # API endpoints
    path('api/filter-properties/', views.api_filter_properties, name='api_filter_properties'),
    path('api/property-details/<int:property_id>/', views.api_property_details, name='api_property_details'),
    path('api/send-contact/', views.api_send_contact, name='api_send_contact'),
    
    # Premier properties (login required)
    path('premier-properties/', views.premier_properties_view, name='premier_properties'),
    
    path("about/", TemplateView.as_view(template_name="core/about.html"), name="about"),
    path("contact/", TemplateView.as_view(template_name="core/contact.html"), name="contact"),
    path("privacy/", TemplateView.as_view(template_name="core/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="core/terms.html"), name="terms"),
    path("properties_list/", views.properties_list_view, name="properties_list"),
    path('api/featured-properties/', views.api_featured_properties, name='api_featured_properties'),
    path('api/property-types/', views.api_property_types, name='api_property_types'),
    path('api/property-details/<int:id>/', views.api_property_details, name='api_property_details'),


    # ======================================================
    # AUTHENTICATION
    # ======================================================
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Allauth (Social Login)
    path("accounts/", include("allauth.urls")),
    
    # ======================================================
    # EMAIL VERIFICATION
    # ======================================================
    path("verify-email/<uidb64>/<token>/", views.verify_email_view, name="verify_email"),
    path("verification-sent/", views.verification_sent_view, name="verification_sent"),
    path("resend-verification/", views.resend_verification_view, name="resend_verification"),

    # ======================================================
    # PASSWORD RESET
    # ======================================================
    path("change-password/", change_password_view, name="change_password"),
    path("password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/email/password_reset.html",
            email_template_name="auth/email/password_reset_email.html",
            subject_template_name="auth/email/password_reset_subject.txt",
        ),name="password_reset",),
    path("password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(template_name="auth/email/password_reset_done.html"),
        name="password_reset_done",),
    path("password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(template_name="auth/email/password_reset_confirm.html"),
        name="password_reset_confirm",),
    path("password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(template_name="auth/email/password_reset_complete.html"),
        name="password_reset_complete",),
   
      
]
