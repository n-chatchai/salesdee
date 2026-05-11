from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render


@login_required
def home(request: HttpRequest) -> HttpResponse:
    """Landing / dashboard placeholder. Real dashboard comes later (REQUIREMENTS.md §4.9)."""
    return render(request, "core/home.html")
