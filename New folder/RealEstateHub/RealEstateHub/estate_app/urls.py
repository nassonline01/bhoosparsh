from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.views.generic import TemplateView

from . import (
    property_views,
    views,
    membership_views,
    dashboard_views,
)
from .views import change_password_view

from .seller_dashboard import (
    seller_dashboard_overview, seller_dashboard_properties,
    seller_dashboard_property_detail, seller_dashboard_leads,
    seller_dashboard_lead_detail, seller_dashboard_analytics,
    seller_dashboard_packages, seller_dashboard_settings,
    seller_dashboard_help, ajax_dashboard_stats, ajax_bulk_action,
    ajax_boost_listing, ajax_update_lead_status, ajax_log_interaction,
    ajax_update_notifications, ajax_update_privacy, ajax_update_profile, export_leads_csv
)

from .property_views import (
    
    seller_delete_property, seller_toggle_featured,
    seller_publish_property, seller_pause_property,
    seller_unpause_property, seller_property_quick_actions,
    ajax_get_subcategories, ajax_delete_property_image,
    ajax_set_primary_image, ajax_check_listing_limit
)

from . import property_view
    
    
urlpatterns = [
    
    path("buyer/", TemplateView.as_view(template_name="demo/buyer/dashboard.html"), name="buyer_dashboard"),
    path("price_trends/", TemplateView.as_view(template_name="demo/buyer/price_trends.html"), name="price_trends"),
    path("saved_properties/", TemplateView.as_view(template_name="demo/buyer/saved_properties.html"), name="saved_properties"),
    path("buyer_search/", TemplateView.as_view(template_name="demo/buyer/buyer_search.html"), name="buyer_search"),
    path("compare_properties/", TemplateView.as_view(template_name="demo/buyer/compare_properties.html"), name="compare_properties"),
    path("settings/", TemplateView.as_view(template_name="demo/buyer/settings.html"), name="buyer_settings"),
    path("recent_views/", TemplateView.as_view(template_name="demo/buyer/recent_views.html"), name="recent_views"),
    
    
    
    # ======================================================
    # SELLER DASHBOARD VIEWS
    # ======================================================
    
     # Property creation wizard
    # path('create/', property_view.create_property_wizard, name='create_property_wizard'),
    
    # AJAX endpoints
    path('api/get-subcategories/',property_view.get_subcategories, name='get_subcategories'),
    path('api/get-category-fields/', property_view.get_category_fields, name='get_category_fields'),
    path('api/get-price-suggestions/', property_view.get_price_suggestions, name='get_price_suggestions'),
    # path('api/get-localities/', property_view.get_localities, name='get_localities'),
    path('api/save-property-step/', property_view.save_property_step, name='save_property_step'),
    path('api/upload-images/', property_view.upload_property_images, name='upload_property_images'),
    path('api/delete-image/', property_view.delete_property_image, name='delete_property_image'),
    path('api/set-primary-image/', property_view.set_primary_image, name='set_primary_image'),
    
    path('property/wizard/save-ajax/', property_view.save_property_ajax, name='save_property_ajax'),
    path('property/wizard/', property_view.create_property_wizard, name='create_property_wizard'),
    # path('api/get-subcategories/', property_view.get_subcategories, name='get_subcategories'),
    # path('api/get-category-fields/', property_view.get_category_fields, name='get_category_fields')

    # Property preview
    path('preview/<int:property_id>/', property_view.property_preview, name='property_preview'),

    # ======================================================
    # SELLER DASHBOARD
    # ======================================================
    path("seller/", seller_dashboard_overview, name="seller_dashboard"),
    path("seller/overview/", seller_dashboard_overview, name="seller_overview"),
    path("seller/properties/", seller_dashboard_properties, name="seller_properties"),
    # path("seller/properties/create/", SellerPropertyCreateView.as_view(), name="seller_property_create"),
    path("seller/properties/<slug:slug>/", seller_dashboard_property_detail, name="seller_property_detail"),
    # path("seller/properties/<slug:slug>/edit/", SellerPropertyUpdateView.as_view(), name="seller_property_edit"),
    path("seller/properties/<slug:slug>/delete/", seller_delete_property, name="seller_property_delete"),
    path("seller/properties/<slug:slug>/feature/", seller_toggle_featured, name="seller_property_feature"),
    path("seller/properties/<slug:slug>/publish/", seller_publish_property, name="seller_property_publish"),
    path("seller/properties/<slug:slug>/pause/", seller_pause_property, name="seller_property_pause"),
    path("seller/properties/<slug:slug>/activate/", seller_unpause_property, name="seller_property_activate"),
    path("seller/properties/<slug:slug>/action/<str:action>/", seller_property_quick_actions, name="seller_property_action"),
    
    path("seller/leads/", seller_dashboard_leads, name="seller_leads"),
    path("seller/leads/<int:lead_id>/", seller_dashboard_lead_detail, name="seller_lead_detail"),
    path("seller/analytics/", seller_dashboard_analytics, name="seller_analytics"),
    path("seller/packages/", seller_dashboard_packages, name="seller_packages"),
    # path("seller/settings/", seller_dashboard_settings, name="seller_settings"),
    path("seller/help/", seller_dashboard_help, name="seller_help"),
    
    # ======================================================
    # SELLER DASHBOARD SETTINGS PAGES
    # ======================================================
    path('dashboard/settings/', views.seller_settings, name='seller_settings'),
    path('dashboard/settings/update-profile/', views.update_profile, name='update_profile'),
    path('dashboard/settings/update-privacy/', views.update_privacy, name='update_privacy'),
    path('dashboard/settings/update-notifications/', views.update_notifications, name='update_notifications'),
    path('dashboard/settings/update-password/', views.update_password, name='update_password'),
    
    # ======================================================
    # SELLER DASHBOARD AJAX ENDPOINTS
    # ======================================================
    path("seller/ajax/stats/", ajax_dashboard_stats, name="seller_ajax_stats"),
    path("seller/ajax/bulk-action/", ajax_bulk_action, name="seller_ajax_bulk_action"),
    path("seller/ajax/boost/<int:property_id>/", ajax_boost_listing, name="seller_ajax_boost"),
    path("seller/ajax/leads/<int:lead_id>/update/", ajax_update_lead_status, name="seller_ajax_update_lead"),
    path("seller/ajax/leads/<int:lead_id>/interaction/", ajax_log_interaction, name="seller_ajax_log_interaction"),
    path("seller/ajax/notifications/update/", ajax_update_notifications, name="seller_ajax_update_notifications"),
    path("seller/ajax/privacy/update/", ajax_update_privacy, name="seller_ajax_update_privacy"),
    path("seller/ajax/profile/update/", ajax_update_profile, name="seller_ajax_update_profile"),
    
    # Property AJAX endpoints
    path("seller/ajax/subcategories/", ajax_get_subcategories, name="ajax_get_subcategories"),
    path("ajax/check-listing-limit/", ajax_check_listing_limit, name="ajax_check_listing_limit"),
    path("seller/ajax/image/<int:image_id>/delete/", ajax_delete_property_image, name="ajax_delete_property_image"),
    path("seller/ajax/image/<int:image_id>/primary/", ajax_set_primary_image, name="ajax_set_primary_image"), 
    path('ajax/get-average-price/', property_views.ajax_get_average_price, name='ajax_get_average_price'),
    
    # ======================================================
    # DATA EXPORT
    # ======================================================
    path("seller/export/leads/", export_leads_csv, name="export_leads"),
        
    # ======================================================
    # PROPERTY MANAGEMENT (Legacy routes for compatibility)
    # ======================================================
    # path("create/", SellerPropertyCreateView.as_view(), name="create"),
    path("my-properties/", seller_dashboard_properties, name="my_properties"),
    # path("<slug:slug>/edit/", SellerPropertyUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", seller_delete_property, name="delete"),
    path("<slug:slug>/feature/", seller_toggle_featured, name="toggle_featured"),
    
    # Property Detail & List (Public)
    # path("search/", views.PropertyListView.as_view(), name="search"),
    # path("<slug:slug>/stats/", views.property_stats_view, name="property_stats"),
    # path("<slug:slug>/", views.PropertyDetailView.as_view(), name="detail"),
    # path("properties/", views.PropertyListView.as_view(), name="list"),
    
    # ======================================================
    # PROPERTY AJAX (Legacy)
    # ======================================================
    path("ajax/get-subcategories/", ajax_get_subcategories, name="get_subcategories"),
    path("ajax/search-suggestions/", views.search_suggestions_view, name="search_suggestions"),
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
    path("dashboard/", dashboard_views.dashboard_view, name="dashboard"),
    # path("dashboard/seller/", dashboard_views.seller_dashboard_view, name="seller_dashboard"),
    # path("dashboard/buyer/", dashboard_views.buyer_dashboard_view, name="buyer_dashboard"),
    path("dashboard/admin/", dashboard_views.admin_dashboard_view, name="admin_dashboard"),

    # Dashboard AJAX
    path("dashboard/ajax/stats/", dashboard_views.ajax_dashboard_stats_view, name="ajax_dashboard_stats"),
    path("dashboard/ajax/activities/", dashboard_views.ajax_recent_activity_view, name="ajax_recent_activity"),
    path(
        "dashboard/ajax/property-analytics/<int:property_id>/",
        dashboard_views.ajax_property_analytics_view,
        name="ajax_property_analytics",
    ),
    path(
        "dashboard/ajax/update-preferences/",
        dashboard_views.ajax_update_dashboard_preferences_view,
        name="ajax_update_dashboard_preferences",
    ),

    # Dashboard Widgets
    path("dashboard/widget/quick-stats/", dashboard_views.widget_quick_stats_view, name="widget_quick_stats"),
    path("dashboard/widget/revenue-chart/", dashboard_views.widget_revenue_chart_view, name="widget_revenue_chart"),

    # ======================================================
    # MEMBERSHIP / PRICING / PLANS
    # ======================================================
    path("pricing/", membership_views.MembershipPricingView.as_view(), name="pricing"),
    path("plans/", membership_views.PlanSelectionView.as_view(), name="plan_selection"),
    path("checkout/", membership_views.CheckoutView.as_view(), name="checkout"),

    # Subscription Management
    path("subscription/dashboard/", membership_views.SubscriptionDashboardView.as_view(), name="subscription_dashboard"),
    path("subscription/upgrade/", membership_views.SubscriptionUpgradeView.as_view(), name="upgrade"),
    path("subscription/upgrade/payment/", membership_views.UpgradePaymentView.as_view(), name="upgrade_payment"),
    path("subscription/cancel/", membership_views.SubscriptionCancelView.as_view(), name="cancel"),
    path("subscription/billing-history/", membership_views.BillingHistoryView.as_view(), name="billing_history"),

    # Credits
    path("credits/", membership_views.CreditPurchaseView.as_view(), name="credit_purchase"),
    path("credits/payment/", membership_views.CreditPurchasePaymentView.as_view(), name="credit_payment"),

    # Razorpay Webhook
    path("webhook/razorpay/", membership_views.razorpay_webhook_view, name="razorpay_webhook"),

    # Membership AJAX
    path(
        "ajax/subscription-details/",
        membership_views.get_subscription_details_view,
        name="ajax_subscription_details",
    ),
    # path(
    #     "ajax/check-listing-limit/",
    #     membership_views.check_listing_limit_view,
    #     name="ajax_check_listing_limit",
    # ),
    path(
        "ajax/activate-trial/<slug:plan_slug>/",
        membership_views.activate_trial_view,
        name="ajax_activate_trial",
    ),

    # Membership Static Pages
    path("features/", TemplateView.as_view(template_name="membership/features.html"), name="features"),
    path("faq/", TemplateView.as_view(template_name="membership/faq.html"), name="faq"),

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
    path("how-to-list/", TemplateView.as_view(template_name="properties/how_to_list.html"), name="how_to_list"),
    path("pricing-guide/", TemplateView.as_view(template_name="properties/pricing_guide.html"), name="pricing_guide"),

      
]
