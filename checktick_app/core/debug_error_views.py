"""Debug views for testing error pages locally."""

from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods


def trigger_403(request: HttpRequest) -> HttpResponse:
    """Trigger a 403 Forbidden error."""
    # Use the custom handler directly
    from checktick_app.core.error_handlers import custom_permission_denied_view

    return custom_permission_denied_view(request)


def trigger_404(request: HttpRequest) -> HttpResponse:
    """Trigger a 404 Not Found error."""
    # Use the custom handler directly
    from checktick_app.core.error_handlers import custom_page_not_found_view

    return custom_page_not_found_view(request)


@require_http_methods(["GET"])
def trigger_405(request: HttpRequest) -> HttpResponse:
    """Trigger a 405 Method Not Allowed error by rendering the template."""
    # Render the 405 template directly since Django doesn't have a built-in handler
    return render(request, "405.html", status=405)


def trigger_500(request: HttpRequest) -> HttpResponse:
    """Trigger a 500 Internal Server Error."""
    # Use the custom handler directly
    from checktick_app.core.error_handlers import custom_server_error_view

    return custom_server_error_view(request)


def trigger_lockout(request: HttpRequest) -> HttpResponse:
    """Preview the lockout page (requires manual testing via failed login attempts)."""
    return render(request, "403_lockout.html")


def error_test_menu(request: HttpRequest) -> HttpResponse:
    """Show a menu of error pages to test."""
    return HttpResponse("""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error Page Testing</title>
            <style>
                body { font-family: system-ui; max-width: 600px; margin: 50px auto; padding: 20px; }
                h1 { color: #333; }
                ul { list-style: none; padding: 0; }
                li { margin: 15px 0; }
                a {
                    display: inline-block;
                    padding: 10px 20px;
                    background: #007bff;
                    color: white;
                    text-decoration: none;
                    border-radius: 4px;
                }
                a:hover { background: #0056b3; }
                .note {
                    background: #f8f9fa;
                    padding: 15px;
                    border-left: 4px solid #007bff;
                    margin-top: 30px;
                }
            </style>
        </head>
        <body>
            <h1>🔧 Error Page Testing</h1>
            <p>Click the links below to view different error pages:</p>
            <ul>
                <li><a href="/debug/errors/403">403 - Access Denied</a></li>
                <li><a href="/debug/errors/404">404 - Not Found</a></li>
                <li><a href="/debug/errors/405">405 - Method Not Allowed</a></li>
                <li><a href="/debug/errors/500">500 - Server Error</a></li>
                <li><a href="/debug/errors/lockout">Account Lockout (Preview)</a></li>
            </ul>
            <div class="note">
                <strong>Note:</strong> These are real error handlers, so you'll see the actual error pages
                as they would appear in production. To test the lockout page realistically,
                try logging in with wrong credentials 5 times in a row.
            </div>
        </body>
        </html>
        """)
