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
    
    path("buyer/", TemplateView.as_view(template_name="dashboard/buyer/dashboard.html"), name="dashboard"),
    path("price_trends/", TemplateView.as_view(template_name="dashboard/buyer/price_trends.html"), name="trends"),
    path("saved_properties/", TemplateView.as_view(template_name="dashboard/buyer/saved_properties.html"), name="saved"),
    path("buyer_search/", TemplateView.as_view(template_name="dashboard/buyer/buyer_search.html"), name="search"),
    path("compare_properties/", TemplateView.as_view(template_name="dashboard/buyer/compare_properties.html"), name="compare"),
    path("settings/", TemplateView.as_view(template_name="dashboard/buyer/settings.html"), name="buyer_settings"),
    path("recent_views/", TemplateView.as_view(template_name="dashboard/buyer/recent_views.html"), name="recent_views"),
    
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
    path('buyer/inquiries/', buyer_views.buyer_inquiries, name='buyer_inquiries'),
    path('buyer/profile/', buyer_views.buyer_profile, name='buyer_profile'),
    
    path('visits/<int:visit_id>/confirm/', buyer_views.confirm_visit, name='confirm_visit'),
    path('visits/<int:visit_id>/reschedule/', buyer_views.reschedule_visit, name='reschedule_visit'),
    path('visits/<int:visit_id>/cancel/', buyer_views.cancel_visit, name='cancel_visit'),
    
    # Buyer AJAX URLs
    path('buyer/ajax/toggle-favorite/', buyer_views.ajax_toggle_favorite, name='ajax_toggle_favorite'),
    path('buyer/ajax/send-inquiry/', buyer_views.ajax_send_inquiry, name='ajax_send_inquiry'),
    path('buyer/ajax/update-favorite-status/', buyer_views.ajax_update_favorite_status, name='ajax_update_favorite_status'),
    
    # AJAX URLs for favorites
    
    path('ajax/remove-favorite/', buyer_views.ajax_remove_favorite, name='ajax_remove_favorite'),
    
    # Comparison URLs
    path('comparisons/json/', buyer_views.comparison_lists_json, name='comparison_lists_json'),
    path('comparison/<int:pk>/add/', buyer_views.add_to_comparison, name='add_to_comparison'),
    path('comparisons/create/', buyer_views.create_comparison, name='create_comparison'),
    
    
    # ======================================================
    # SELLER DASHBOARD VIEWS
    # ======================================================
    path('seller/dashboard/', seller_views.seller_dashboard, name='seller_dashboard'),
    path('seller/profile/', seller_views.seller_profile, name='seller_profile'),
    path('seller/packages/', seller_views.seller_packages, name='seller_packages'),
    path('seller/properties/', seller_views.seller_properties, name='seller_properties'),
    path('seller/properties/', seller_views.seller_properties, name='seller_property'),
    path('seller/properties/create/', seller_views.seller_property_create, name='seller_property_create'),
    path('seller/properties/<int:pk>/edit/', seller_views.seller_property_edit, name='seller_property_edit'),
    path('seller/properties/<int:pk>/delete/', seller_views.seller_property_delete, name='seller_property_delete'),
    path('seller/leads/', seller_views.seller_leads, name='seller_leads'),
    path('seller/leads/<int:pk>/', seller_views.seller_lead_detail, name='seller_lead_detail'),
    path('seller/leads/export/', seller_views.seller_lead_export, name='seller_lead_export'),
    path('seller/analytics/', seller_views.seller_analytics, name='seller_analytics'),
    path('seller/settingss/', seller_views.seller_settings, name='seller_settings'),
    # path('seller/settings/', seller_views.seller_settings, name='seller_settings'),

    # ======================================================
    # SELLER DASHBOARD
    # ======================================================
    # path("seller/", seller_dashboard_overview, name="seller_dashboard"),
    # path("seller/overview/", seller_dashboard_overview, name="seller_overview"),
    # path("seller/properties/", seller_dashboard_properties, name="seller_properties"),
    # # path("seller/properties/create/", SellerPropertyCreateView.as_view(), name="seller_property_create"),
    # path("seller/properties/<slug:slug>/", seller_dashboard_property_detail, name="seller_property_detail"),
    # # path("seller/properties/<slug:slug>/edit/", SellerPropertyUpdateView.as_view(), name="seller_property_edit"),
    # path("seller/properties/<slug:slug>/delete/", seller_delete_property, name="seller_property_delete"),
    # path("seller/properties/<slug:slug>/feature/", seller_toggle_featured, name="seller_property_feature"),
    # path("seller/properties/<slug:slug>/publish/", seller_publish_property, name="seller_property_publish"),
    # path("seller/properties/<slug:slug>/pause/", seller_pause_property, name="seller_property_pause"),
    # path("seller/properties/<slug:slug>/activate/", seller_unpause_property, name="seller_property_activate"),
    # path("seller/properties/<slug:slug>/action/<str:action>/", seller_property_quick_actions, name="seller_property_action"),
    
    # path("seller/leads/", seller_dashboard_leads, name="seller_leads"),
    # path("seller/leads/<int:lead_id>/", seller_dashboard_lead_detail, name="seller_lead_detail"),
    # path("seller/analytics/", seller_dashboard_analytics, name="seller_analytics"),
    # path("seller/packages/", seller_dashboard_packages, name="seller_packages"),
    # # path("seller/settings/", seller_dashboard_settings, name="seller_settings"),
    # path("seller/help/", seller_dashboard_help, name="seller_help"),
    
    # ======================================================
    # SELLER DASHBOARD SETTINGS PAGES
    # ======================================================
    # path('dashboard/settings/', views.seller_settings, name='seller_settings'),
    # path('dashboard/settings/update-profile/', views.update_profile, name='update_profile'),
    # path('dashboard/settings/update-privacy/', views.update_privacy, name='update_privacy'),
    # path('dashboard/settings/update-notifications/', views.update_notifications, name='update_notifications'),
    # path('dashboard/settings/update-password/', views.update_password, name='update_password'),
    
    # ======================================================
    # SELLER DASHBOARD AJAX ENDPOINTS
    # ======================================================
    # path("seller/ajax/stats/", ajax_dashboard_stats, name="seller_ajax_stats"),
    # path("seller/ajax/bulk-action/", ajax_bulk_action, name="seller_ajax_bulk_action"),
    # path("seller/ajax/boost/<int:property_id>/", ajax_boost_listing, name="seller_ajax_boost"),
    # path("seller/ajax/leads/<int:lead_id>/update/", ajax_update_lead_status, name="seller_ajax_update_lead"),
    # path("seller/ajax/leads/<int:lead_id>/interaction/", ajax_log_interaction, name="seller_ajax_log_interaction"),
    # path("seller/ajax/notifications/update/", ajax_update_notifications, name="seller_ajax_update_notifications"),
    # path("seller/ajax/privacy/update/", ajax_update_privacy, name="seller_ajax_update_privacy"),
    # path("seller/ajax/profile/update/", ajax_update_profile, name="seller_ajax_update_profile"),
    
    # # Property AJAX endpoints
    # path("seller/ajax/subcategories/", ajax_get_subcategories, name="ajax_get_subcategories"),
    # path("ajax/check-listing-limit/", ajax_check_listing_limit, name="ajax_check_listing_limit"),
    # path("seller/ajax/image/<int:image_id>/delete/", ajax_delete_property_image, name="ajax_delete_property_image"),
    # path("seller/ajax/image/<int:image_id>/primary/", ajax_set_primary_image, name="ajax_set_primary_image"), 
    # path('ajax/get-average-price/', property_views.ajax_get_average_price, name='ajax_get_average_price'),
    
    # ======================================================
    # DATA EXPORT
    # ======================================================
    # path("seller/export/leads/", export_leads_csv, name="export_leads"),
        
    # ======================================================
    # PROPERTY MANAGEMENT (Legacy routes for compatibility)
    # ======================================================
    # path("create/", SellerPropertyCreateView.as_view(), name="create"),
    # path("my-properties/", seller_dashboard_properties, name="my_properties"),
    # # path("<slug:slug>/edit/", SellerPropertyUpdateView.as_view(), name="edit"),
    # path("<slug:slug>/delete/", seller_delete_property, name="delete"),
    # path("<slug:slug>/feature/", seller_toggle_featured, name="toggle_featured"),
    
    # Property Detail & List (Public)
    # path("search/", views.PropertyListView.as_view(), name="search"),
    # path("<slug:slug>/stats/", views.property_stats_view, name="property_stats"),
    # path("<slug:slug>/", views.PropertyDetailView.as_view(), name="detail"),
    # path("properties/", views.PropertyListView.as_view(), name="list"),
    
    # ======================================================
    # PROPERTY AJAX (Legacy)
    # ======================================================
    # path("ajax/get-subcategories/", ajax_get_subcategories, name="get_subcategories"),
    # path("ajax/search-suggestions/", views.search_suggestions_view, name="search_suggestions"),
    # path("ajax/toggle-favorite/<int:property_id>/", views.toggle_favorite_view, name="toggle_favorite"),
    
    

    # ======================================================
    # HOME & CORE PAGES
    # ======================================================
    path("", views.home_view, name="home"),
    path("about/", TemplateView.as_view(template_name="core/about.html"), name="about"),
    path("contact/", TemplateView.as_view(template_name="core/contact.html"), name="contact"),
    path("privacy/", TemplateView.as_view(template_name="core/privacy.html"), name="privacy"),
    path("terms/", TemplateView.as_view(template_name="core/terms.html"), name="terms"),
    path("properties_list/", TemplateView.as_view(template_name="core/properties_list.html"), name="properties_list"),

    # ======================================================
    # AUTHENTICATION
    # ======================================================
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    # Allauth (Social Login)
    path("accounts/", include("allauth.urls")),

    # ======================================================
    # PASSWORD RESET
    # ======================================================
    path(
        "password-reset/",
        auth_views.PasswordResetView.as_view(
            template_name="auth/email/password_reset.html",
            email_template_name="auth/email/password_reset_email.html",
            subject_template_name="auth/email/password_reset_subject.txt",
        ),
        name="password_reset",
    ),
    path(
        "password-reset/done/",
        auth_views.PasswordResetDoneView.as_view(
            template_name="auth/email/password_reset_done.html"
        ),
        name="password_reset_done",
    ),
    path(
        "password-reset-confirm/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(
            template_name="auth/email/password_reset_confirm.html"
        ),
        name="password_reset_confirm",
    ),
    path(
        "password-reset-complete/",
        auth_views.PasswordResetCompleteView.as_view(
            template_name="auth/email/password_reset_complete.html"
        ),
        name="password_reset_complete",
    ),

    # ======================================================
    # EMAIL VERIFICATION
    # ======================================================
    path("verify-email/<uidb64>/<token>/", views.verify_email_view, name="verify_email"),
    path("verification-sent/", views.verification_sent_view, name="verification_sent"),
    path("resend-verification/", views.resend_verification_view, name="resend_verification"),

    # ======================================================
    # USER PROFILE
    # ======================================================
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.edit_profile_view, name="edit_profile"),
    path("change-password/", change_password_view, name="change_password"),

    # ======================================================
    # DASHBOARD
    # ======================================================
    # path("dashboard/", dashboard_views.dashboard_view, name="dashboard"),
    # path("dashboard/seller/", dashboard_views.seller_dashboard_view, name="seller_dashboard"),
    # path("dashboard/buyer/", dashboard_views.buyer_dashboard_view, name="buyer_dashboard"),
    # path("dashboard/admin/", dashboard_views.admin_dashboard_view, name="admin_dashboard"),

    # # Dashboard AJAX
    # path("dashboard/ajax/stats/", dashboard_views.ajax_dashboard_stats_view, name="ajax_dashboard_stats"),
    # path("dashboard/ajax/activities/", dashboard_views.ajax_recent_activity_view, name="ajax_recent_activity"),
    # path(
    #     "dashboard/ajax/property-analytics/<int:property_id>/",
    #     dashboard_views.ajax_property_analytics_view,
    #     name="ajax_property_analytics",
    # ),
    # path(
    #     "dashboard/ajax/update-preferences/",
    #     dashboard_views.ajax_update_dashboard_preferences_view,
    #     name="ajax_update_dashboard_preferences",
    # ),

    # # # Dashboard Widgets
    # path("dashboard/widget/quick-stats/", dashboard_views.widget_quick_stats_view, name="widget_quick_stats"),
    # path("dashboard/widget/revenue-chart/", dashboard_views.widget_revenue_chart_view, name="widget_revenue_chart"),

    
    # # Membership Static Pages
    # path("features/", TemplateView.as_view(template_name="membership/features.html"), name="features"),
    # path("faq/", TemplateView.as_view(template_name="membership/faq.html"), name="faq"),

    # ======================================================
    # PROPERTY MANAGEMENT
    # ======================================================
    # path("create/", property_views.PropertyCreateView.as_view(), name="create"),
    # path("my-properties/", property_views.MyPropertiesView.as_view(), name="my_properties"),

    # path("<slug:slug>/edit/", property_views.PropertyUpdateView.as_view(), name="edit"),
    # path("<slug:slug>/delete/", property_views.delete_property_view, name="delete"),
    # path("<slug:slug>/feature/", property_views.toggle_featured_view, name="toggle_featured"),

    # # Property Detail & List (KEEP AT BOTTOM)
    # path("search/", property_views.PropertyListView.as_view(), name="search"),
    # path("<slug:slug>/stats/", property_views.property_stats_view, name="property_stats"),
    # path("<slug:slug>/", property_views.PropertyDetailView.as_view(), name="detail"),
    # path("", property_views.PropertyListView.as_view(), name="list"),

    # ======================================================
    # PROPERTY AJAX
    # ======================================================
    # path("ajax/get-subcategories/", property_views.get_subcategories_view, name="get_subcategories"),
    # path("ajax/search-suggestions/", property_views.search_suggestions_view, name="search_suggestions"),
    # path(
    #     "ajax/toggle-favorite/<int:property_id>/",
    #     property_views.toggle_favorite_view,
    #     name="toggle_favorite",
    # ),

    # ======================================================
    # PROPERTY STATIC PAGES
    # ======================================================
    # path("how-to-list/", TemplateView.as_view(template_name="properties/how_to_list.html"), name="how_to_list"),
    # path("pricing-guide/", TemplateView.as_view(template_name="properties/pricing_guide.html"), name="pricing_guide"),

      
]
