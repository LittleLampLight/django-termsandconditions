"""Django Models for TermsAndConditions App"""

# pylint: disable=C1001,E0202,W0613

from django.db import models, utils
from django.conf import settings
from django.utils import timezone
from django.core.cache import cache
import logging

LOGGER = logging.getLogger(name='termsandconditions')

DEFAULT_TERMS_SLUG = getattr(settings, 'DEFAULT_TERMS_SLUG', 'site-terms')


class UserTermsAndConditions(models.Model):
    """Holds mapping between TermsAndConditions and Users"""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="userterms")
    terms = models.ForeignKey("TermsAndConditions", related_name="userterms")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name='IP Address')
    date_accepted = models.DateTimeField(auto_now_add=True, verbose_name='Date Accepted')

    class Meta:
        """Model Meta Information"""
        get_latest_by = 'date_accepted'
        verbose_name = 'User Terms and Conditions'
        verbose_name_plural = 'User Terms and Conditions'
        unique_together = ('user', 'terms',)

    def __str__(self):
        return "{0}:{1}-{2:.2f}".format(self.user.username, self.terms.slug, self.terms.version_number)


class TermsAndConditions(models.Model):
    """Holds Versions of TermsAndConditions
    Active one for a given slug is: date_active is not Null and is latest not in future"""
    slug = models.SlugField(default=DEFAULT_TERMS_SLUG)
    name = models.TextField(max_length=255)
    users = models.ManyToManyField(settings.AUTH_USER_MODEL, through=UserTermsAndConditions, blank=True)
    version_number = models.DecimalField(default=1.0, decimal_places=2, max_digits=6)
    text = models.TextField(null=True, blank=True)
    info = models.TextField(null=True, blank=True, help_text="Provide users with some info about what's changed and why")
    date_active = models.DateTimeField(blank=True, null=True, help_text="Leave Null To Never Make Active")
    date_created = models.DateTimeField(blank=True, auto_now_add=True)

    class Meta:
        """Model Meta Information"""
        ordering = ['-date_active', ]
        get_latest_by = 'date_active'
        verbose_name = 'Terms and Conditions'
        verbose_name_plural = 'Terms and Conditions'

    def __str__(self):
        return "{0}-{1:.2f}".format(self.slug, self.version_number)

    @models.permalink
    def get_absolute_url(self):
        return ('tc_view_specific_version_page', [self.slug, self.version_number])  # pylint: disable=E1101

    @staticmethod
    def get_active(slug=DEFAULT_TERMS_SLUG):
        """Finds the latest of a particular terms and conditions"""

        active_terms = cache.get('tandc.active_terms_' + slug)
        if not active_terms:
            try:
                active_terms = TermsAndConditions.objects.filter(
                    date_active__isnull=False,
                    date_active__lte=timezone.now(),
                    slug=slug).latest('date_active')
                cache.set('tandc.active_terms_' + slug, active_terms)
            except TermsAndConditions.DoesNotExist:
                LOGGER.error("Requested Terms and Conditions that Have Not Been Created.")
                return None

        return active_terms

    @staticmethod
    def get_active_terms_ids():
        """Returns a list of the IDs of of all terms and conditions"""

        active_terms_ids = cache.get('tandc.active_terms_ids')
        if not active_terms_ids:
            active_terms_ids = []

            try:
                active_terms_set = TermsAndConditions.objects.raw('SELECT id, slug, max(date_active) FROM termsandconditions_termsandconditions WHERE date_active IS NOT NULL AND date_active < %s GROUP BY slug ORDER BY slug', [timezone.now()])

                for terms in active_terms_set:
                    active_terms_ids.append(terms.id)

                cache.set('tandc.active_terms_ids', active_terms_ids)

            except utils.ProgrammingError:  # pragma: nocover
                # Handle a particular tricky path that occurs when trying to makemigrations and migrate database first time.
                LOGGER.warning('Unable to find active terms ids because terms and conditions tables not initialized.')
                return active_terms_ids

        return active_terms_ids

    @staticmethod
    def get_active_terms_list():
        """Returns all the latest active terms and conditions"""

        active_terms_list = cache.get('tandc.active_terms_list')
        if not active_terms_list:
            active_terms_list = None
            try:
                active_terms_list = TermsAndConditions.objects.filter(id__in=TermsAndConditions.get_active_terms_ids()).order_by('slug')
                cache.set('tandc.active_terms_list', active_terms_list)
            except utils.ProgrammingError:  # pragma: nocover
                # Handle a particular tricky path that occurs when trying to makemigrations and migrate database first time.
                LOGGER.warning('Unable to find active terms list because terms and conditions tables not initialized.')
                return active_terms_list

        return active_terms_list

    @staticmethod
    def agreed_to_latest(user, slug=DEFAULT_TERMS_SLUG):
        """Checks to see if a specified user has agreed to the latest of a particular terms and conditions"""

        try:
            UserTermsAndConditions.objects.get(user=user, terms=TermsAndConditions.get_active(slug))
            return True
        except UserTermsAndConditions.MultipleObjectsReturned:  # pragma: nocover
            return True
        except UserTermsAndConditions.DoesNotExist:
            return False
        except TypeError:  # pragma: nocover
            return False

    @staticmethod
    def get_active_terms_not_agreed_to(user):
        """Checks to see if a specified user has agreed to all the latest terms and conditions"""

        not_agreed_terms = cache.get('tandc_not_agreed_terms')
        if not not_agreed_terms:
            try:
                not_agreed_terms = TermsAndConditions.objects.filter(id__in=TermsAndConditions.get_active_terms_ids()).exclude(
                    userterms__in=UserTermsAndConditions.objects.filter(user=user).values_list('id')
                ).order_by('slug')

                cache.set('tandc_not_agreed_terms', not_agreed_terms)
            except (TypeError, UserTermsAndConditions.DoesNotExist):
                return None

        return not_agreed_terms

    @staticmethod
    def agreed_to_terms(user, terms=None):
        """Checks to see if a specified user has agreed to a specific terms and conditions"""

        try:
            UserTermsAndConditions.objects.get(user=user, terms=terms)
            return True
        except UserTermsAndConditions.DoesNotExist:
            return False
        except TypeError:
            return False
