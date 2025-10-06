from django.urls import path

from .views import (
    ProfileDetailAPIView,
    ProfileListAPIView,
)

urlpatterns = [
    path("all/", ProfileListAPIView.as_view(), name="all_profiles"),
    path("my-profile/", ProfileDetailAPIView.as_view(), name="profile_detail"),
]