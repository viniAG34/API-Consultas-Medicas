from django.urls import path

from .views import VerificarSaude

urlpatterns = [
    path("health/", VerificarSaude.as_view(), name="health"),
]
