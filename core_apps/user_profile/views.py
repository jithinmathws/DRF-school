from typing import Any, List

from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import status, filters, generics
from rest_framework import serializers
from rest_framework.pagination import PageNumberPagination
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.request import Request

from core_apps.common.models import ContentView
from core_apps.common.permissions import *
from core_apps.student import utils as StudentUtils
from core_apps.student import models as StudentModel
from core_apps.common.renderers import GenericJSONRenderer
from .models import Profile
from .serializers import ProfileListSerializer, ProfileSerializer


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100


class ProfileListAPIView(generics.ListAPIView):
    serializer_class = ProfileListSerializer
    renderer_classes = [GenericJSONRenderer]
    pagination_class = StandardResultsSetPagination
    object_label = "profiles"
    permission_classes = [IsOfficeStaff]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["user__first_name", "user__last_name", "user__id_no"]
    filterset_fields = ["user__first_name", "user__last_name", "user__id_no"]

    def get_queryset(self) -> List[Profile]:
        return Profile.objects.exclude(user__is_staff=True).exclude(
            user__is_superuser=True
        )


class ProfileDetailAPIView(generics.RetrieveUpdateAPIView):
    serializer_class = ProfileSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    renderer_classes = [GenericJSONRenderer]
    object_label = "profile"

    def get_object(self) -> Profile:
        try:
            profile = Profile.objects.get(user=self.request.user)
            self.record_profile_view(profile)
            return profile
        except Profile.DoesNotExist:
            raise Http404("Profile does not exist")

    def record_profile_view(self, profile: Profile) -> None:
        content_type = ContentType.objects.get_for_model(profile)
        viewer_ip = self.get_client_ip()
        user = self.request.user

        obj, created = ContentView.objects.update_or_create(
            content_type=content_type,
            object_id=profile.id,
            user=user,
            viewer_ip=viewer_ip,
            defaults={
                "last_viewed": timezone.now(),
            },
        )

    def get_client_ip(self) -> str:
        x_forwarded_for = self.request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip = x_forwarded_for.split(",")[0]
        else:
            ip = self.request.META.get("REMOTE_ADDR")
        return ip

    def retrieve(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)

        try:
            serializer.is_valid(raise_exception=True)
            with transaction.atomic():
                updated_instance = serializer.save()

                # create a student when explicitly requested with child payload
                create_student = bool(request.data.get("create_student", False))
                student_payload = request.data.get("student", {}) or {}

                if create_student:
                    # Let utils apply sensible defaults for missing child fields
                    first_name = student_payload.get("first_name")
                    last_name = student_payload.get("last_name")
                    gender = student_payload.get("gender")

                    student_account = StudentUtils.create_student_account(
                        user=updated_instance.user,
                        first_name=first_name,
                        last_name=last_name,
                        gender=gender,
                    )
                    # After creation, mark all students for this parent as having siblings (only if > 1)
                    qs = StudentModel.Student.objects.filter(parent=updated_instance.user)
                    if qs.count() > 1:
                        qs.update(has_sibling=True)
                    message = (
                        "Profile updated and new student created successfully. "
                        "An email has been sent to your account."
                    )
                else:
                    message = "Profile updated successfully."
                return Response(
                    {
                        "message": message,
                        "data": serializer.data,
                    },
                    status=status.HTTP_200_OK,
                )

        except serializers.ValidationError as e:
            return Response({"errors": e.detail}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    def partial_update(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_update(self, serializer: ProfileSerializer) -> None:
        serializer.save()