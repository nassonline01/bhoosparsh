def user_context(request):
    """Add user-related context to all templates"""
    context = {}
    
    if request.user.is_authenticated:
        context['user_profile'] = getattr(request.user, 'profile', None)
        context['user_type'] = request.user.user_type
        context['is_verified'] = request.user.is_verified
    
    return context