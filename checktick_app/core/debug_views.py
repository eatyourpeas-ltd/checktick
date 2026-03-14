"""
Debug views for OIDC authentication testing.
"""

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render


@login_required
def oidc_debug_view(request):
    """Debug view to check authentication status after OIDC login."""
    context = {
        "user": request.user,
        "is_authenticated": request.user.is_authenticated,
        "session_keys": list(request.session.keys()),
        "user_email": getattr(request.user, "email", "No email"),
        "user_username": getattr(request.user, "username", "No username"),
    }

    return render(request, "debug/oidc_debug.html", context)


def oidc_success_view(request):
    """Simple success page after OIDC authentication."""
    if request.user.is_authenticated:
        return HttpResponse(f"""
        <h1>OIDC Authentication Successful!</h1>
        <p>Welcome, {request.user.email}!</p>
        <p>User ID: {request.user.id}</p>
        <p>Username: {request.user.username}</p>
        <a href="/surveys/">Go to Surveys</a>
        """)
    else:
        return HttpResponse("""
        <h1>Authentication Failed</h1>
        <p>You are not logged in.</p>
        <a href="/accounts/login/">Try Again</a>
        """)
