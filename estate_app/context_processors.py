def user_context(request):
    """Add user-related context to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        context['user_profile'] = getattr(request.user, 'profile', None)
        context['user_type'] = request.user.user_type
        context['is_verified'] = request.user.is_verified
        
        # Add seller-specific counts for seller users (seller, agent, builder)
        if hasattr(request.user, 'user_type') and request.user.user_type in ['seller', 'agent', 'builder']:
            from .models import Property, PropertyInquiry
            
            # Get total properties count for this user (all statuses)
            try:
                properties_count = Property.objects.filter(owner=request.user).count()
                # Use actual count or 0 if empty/None
                properties_count_value = properties_count if properties_count else 0
            except Exception:
                properties_count_value = 0
            
            # Get new leads count (inquiries with status='new') for user's properties  
            try:
                new_leads_qs = PropertyInquiry.objects.filter(
                    property__owner=request.user,
                    status='new'
                )
                new_leads_value = new_leads_qs.count() if new_leads_qs else 0
            except Exception:
                new_leads_value = 0
            
            # Add to context
            context['user_properties_count'] = properties_count_value
            context['new_leads_count'] = new_leads_value
    
    return context
