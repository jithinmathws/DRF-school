from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _

from core_apps.common.models import TimeStampedModel
from decimal import Decimal
from cloudinary.models import CloudinaryField
from django.core.validators import MinValueValidator
from django.core.exceptions import ValidationError
from django.db.models import Sum

User = get_user_model()


class Student(TimeStampedModel):
    class Gender(models.TextChoices):
        MALE = ("male", _("Male"))
        FEMALE = ("female", _("Female"))
        OTHER = ("other", _("Other"))

    class AccountStatus(models.TextChoices):
        ACTIVE = ("active", _("Active"))
        INACTIVE = ("in-active", _("In-active"))

    parent = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="student_accounts"
    )
    admission_number = models.CharField(
        _("Admission Number"), max_length=20, unique=True
    )
    first_name = models.CharField(_("First Name"), max_length=20)
    last_name = models.CharField(_("Last Name"), max_length=20)
    gender = models.CharField(
        _("Gender"), max_length=10, choices=Gender.choices
    )
    account_status = models.CharField(
        _("Account Status"),
        max_length=10,
        choices=AccountStatus.choices,
        default=AccountStatus.INACTIVE,
    )
    has_sibling = models.BooleanField(_("Has Sibling"), default=False)
    sibling = models.ManyToManyField("self", blank=True, related_name="siblings")
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="verified_accounts",
    )
    verification_date = models.DateTimeField(
        _("Verification Date"), null=True, blank=True
    )
    verification_notes = models.TextField(_("Verification Notes"), blank=True)
    fully_activated = models.BooleanField(
        _("Fully Activated"),
        default=False,
    )
    image = CloudinaryField(
        _("Image"),
        blank=True,
        null=True,
    )
    image_url = models.URLField(_("Image URL"), blank=True, null=True)

    def __str__(self) -> str:
        return (
            f"{self.parent.full_name}'s {self.full_name} - "
            f"{self.get_account_status_display()} Account - {self.admission_number}"
        )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = _("Student")
        verbose_name_plural = _("Students")


class Fees(TimeStampedModel):
    class FeeType(models.TextChoices):
        ADMISSION = ("admission", _("Admission"))
        BOOK_FEE = ("book_fee", _("Book Fee"))
        BUS_FEE = ("bus_fee", _("Bus Fee"))
        TUTION_FEE = ("tution_fee", _("Tuition Fee"))
        EXAM_FEE = ("exam_fee", _("Exam Fee"))
        TERM_FEE = ("term_fee", _("Term Fee"))
        YEARLY_FEE = ("yearly_fee", _("Yearly Fee"))

    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="fees"
    )
    fee_type = models.CharField(
        _("Fee Type"), max_length=20, choices=FeeType.choices
    )
    amount = models.DecimalField(
        _("Amount"), decimal_places=2, max_digits=12, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )

    def __str__(self) -> str:
        return f"{self.student.full_name}'s {self.fee_type} Fee"

    class Meta:
        verbose_name = _("Fee")
        verbose_name_plural = _("Fees")
        unique_together = ["student", "fee_type"]


class Transaction(TimeStampedModel):
    class TransactionStatus(models.TextChoices):
        PENDING = ("pending", _("Pending"))
        COMPLETED = ("completed", _("Completed"))
        FAILED = ("failed", _("Failed"))

    class TransactionType(models.TextChoices):
        CASH = ("cash", _("Cash"))
        CREDIT_CARD = ("credit_card", _("Credit Card"))
        DEBIT_CARD = ("debit_card", _("Debit Card"))
        UPI = ("upi", _("UPI"))
        BANK_TRANSFER = ("bank_transfer", _("Bank Transfer"))

    payer = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        null=False,
        related_name="payments_made",
        verbose_name=_("Payer"),
    )
    amount = models.DecimalField(
        _("Amount"), decimal_places=2, max_digits=12, default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    description = models.CharField(
        _("Description"), max_length=500, null=True, blank=True
    )
    status = models.CharField(
        choices=TransactionStatus.choices,
        max_length=20,
        default=TransactionStatus.PENDING,
    )
    transaction_type = models.CharField(choices=TransactionType.choices, max_length=20)

    def __str__(self) -> str:
        return f"{self.transaction_type} - {self.amount} - {self.status}"

    def clean(self):
        errors = {}
        # Payer must be a parent
        if self.payer and getattr(self.payer, "role", None) != getattr(User.RoleChoices, "PARENT", "parent"):
            errors["payer"] = _("Payer must have role 'Parent'.")

        # Amount must be strictly positive
        if self.amount is not None and self.amount <= Decimal("0.00"):
            errors["amount"] = _("Amount must be greater than 0.")
        # Validate items: sum of item amounts equals transaction amount and fees belong to payer's children
        if self.pk:  # only possible to check related items after object exists
            items = self.items.all()
            if not items.exists():
                errors["items"] = _("At least one fee item must be added to the transaction.")
            total = items.aggregate(total=Sum("amount")).get("total")
            if total is None or total != self.amount:
                errors["items_amount"] = _("Sum of item amounts must equal the transaction amount.")
            # Each item's fee.student.parent must equal payer
            invalid = [ti for ti in items if ti.fee and ti.fee.student and ti.fee.student.parent != self.payer]
            if invalid:
                errors["items_owner"] = _("All fee items must belong to students of the payer.")
        if errors:
            raise ValidationError(errors)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["created_at"])]


class TransactionItem(TimeStampedModel):
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name=_("Transaction"),
    )
    fee = models.ForeignKey(
        Fees,
        on_delete=models.PROTECT,
        related_name="transaction_items",
        verbose_name=_("Fee"),
    )
    amount = models.DecimalField(
        _("Amount"),
        decimal_places=2,
        max_digits=12,
        validators=[MinValueValidator(Decimal("0.01"))],
    )

    def __str__(self) -> str:
        return f"{self.transaction_id} -> {self.fee_id} : {self.amount}"

    class Meta:
        verbose_name = _("Transaction Item")
        verbose_name_plural = _("Transaction Items")
        unique_together = ["transaction", "fee"]