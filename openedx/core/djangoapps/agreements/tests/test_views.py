"""
Tests for agreements views
"""
from rest_framework.test import APITestCase
from rest_framework import status
from django.urls import reverse
from edx_toggles.toggles.testutils import override_waffle_flag

from common.djangoapps.student.tests.factories import UserFactory, AdminFactory
from common.djangoapps.student.roles import CourseStaffRole
from openedx.core.djangolib.testing.utils import skip_unless_lms
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory

from ..api import create_integrity_signature
from ..toggles import ENABLE_INTEGRITY_SIGNATURE


@skip_unless_lms
@override_waffle_flag(ENABLE_INTEGRITY_SIGNATURE, active=True)
class IntegritySignatureViewTests(APITestCase, ModuleStoreTestCase):
    """
    Tests for the Integrity Signature View
    """
    USERNAME = "Bob"
    PASSWORD = "edx"

    OTHER_USERNAME = "Jane"

    STAFF_USERNAME = "Alice"

    def setUp(self):
        super().setUp()

        self.course = CourseFactory.create()

        self.user = UserFactory.create(
            username=self.USERNAME,
            password=self.PASSWORD,
        )
        self.other_user = UserFactory.create(
            username=self.OTHER_USERNAME,
            password=self.PASSWORD,
        )

        self.instructor = AdminFactory.create(
            username=self.STAFF_USERNAME,
            password=self.PASSWORD,
        )
        self.client.login(username=self.USERNAME, password=self.PASSWORD)
        self.course_id = str(self.course.id)

    def _create_signature(self, username, course_id):
        """
        Create integrity signature for a given username and course id
        """
        create_integrity_signature(username, course_id)

    def _assert_response(self, response, expected_response, user=None, course_id=None):
        """
        Assert response is correct for the given information
        """
        assert response.status_code == expected_response
        if user and course_id:
            data = response.data
            assert data['username'] == user.username
            assert data['course_id'] == course_id

    def test_200_get_for_user_request(self):
        self._create_signature(self.user.username, self.course_id)
        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
        )
        self._assert_response(response, status.HTTP_200_OK, self.user, self.course_id)

    def test_404_get_if_no_signature(self):
        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
        )
        self._assert_response(response, status.HTTP_404_NOT_FOUND)

    def test_403_get_if_non_staff(self):
        self._create_signature(self.other_user.username, self.course_id)
        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
            + '?username={}'.format(self.other_user.username)
        )
        self._assert_response(response, status.HTTP_403_FORBIDDEN)

    def test_200_get_for_course_staff_request(self):
        self._create_signature(self.user.username, self.course_id)

        self.instructor.is_staff = False
        self.instructor.save()

        CourseStaffRole(self.course.id).add_users(self.instructor)
        self.client.login(username=self.STAFF_USERNAME, password=self.PASSWORD)

        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
            + '?username={}'.format(self.user.username)
        )
        self._assert_response(response, status.HTTP_200_OK, self.user, self.course_id)

    def test_403_get_for_other_course_instructor(self):
        self._create_signature(self.user.username, self.course_id)

        self.instructor.is_staff = False
        self.instructor.save()

        # create another course and add instructor to that course
        second_course = CourseFactory.create()
        CourseStaffRole(second_course.id).add_users(self.instructor)
        self.client.login(username=self.STAFF_USERNAME, password=self.PASSWORD)

        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
            + '?username={}'.format(self.user.username)
        )
        self._assert_response(response, status.HTTP_403_FORBIDDEN)

    def test_200_get_for_admin(self):
        self._create_signature(self.user.username, self.course_id)

        self.instructor.is_staff = True
        self.instructor.save()

        self.client.login(username=self.STAFF_USERNAME, password=self.PASSWORD)

        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
            + '?username={}'.format(self.user.username)
        )
        self._assert_response(response, status.HTTP_200_OK, self.user, self.course_id)

    @override_waffle_flag(ENABLE_INTEGRITY_SIGNATURE, active=False)
    def test_404_for_no_waffle_flag(self):
        self._create_signature(self.user.username, self.course_id)
        response = self.client.get(
            reverse(
                'integrity_signature',
                kwargs={'course_id': self.course_id},
            )
        )
        self._assert_response(response, status.HTTP_404_NOT_FOUND)
