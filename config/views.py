# This module handles web requests and prepares responses or pages.

# `render` loads a template and wraps the resulting HTML in an HTTP response.
from django.shortcuts import render


# A URL route can call this view and pass the incoming request object to it.
def home(request):
    # Render templates/home.html without any extra context variables.
    return render(request, "home.html")
