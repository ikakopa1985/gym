from django.db import models
from django.utils.timezone import now
from django.db.models import Q
from datetime import timedelta


class Trainer(models.Model):
    first_name = models.CharField("სახელი", max_length=100)
    last_name = models.CharField("გვარი", max_length=100)
    phone = models.CharField("ტელეფონი", max_length=20)
    specialization = models.CharField("სპეციალიზაცია", max_length=255, blank=True)
    fee = models.DecimalField("სტავკა (₾)", max_digits=8, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


class Membership(models.Model):
    TYPE_CHOICES = (
        ("unlimited", "ულიმიტო (დღეებით)"),
        ("limited", "რაოდენობრივი (ვიზიტებით)"),
        ("fixed", "დროითი (თარიღიდან-თარიღამდე)"),
    )

    name = models.CharField("დასახელება", max_length=100)
    membership_type = models.CharField("ტიპი", max_length=20, choices=TYPE_CHOICES)
    price = models.DecimalField("ფასი", max_digits=8, decimal_places=2)

    # unlimited ტიპისთვის (დღეებში)
    duration_days = models.PositiveIntegerField("ვადა (დღეებში)", null=True, blank=True)

    # limited ტიპისთვის
    visit_count = models.PositiveIntegerField("ვიზიტების რაოდენობა", null=True, blank=True)

    def __str__(self):
        return self.name



class ClientMembership(models.Model):
    STATUS_CHOICES = (
        ("active", "აქტიური"),
        ("expired", "ვადაგასული"),
        ("paused", "დაპაუზებული"),
    )

    client = models.ForeignKey(
        "Client",
        on_delete=models.CASCADE,
        related_name="memberships",
        verbose_name="კლიენტი",
    )
    membership = models.ForeignKey(
        "Membership",
        on_delete=models.PROTECT,
        related_name="client_memberships",
        verbose_name="აბონემენტი",
    )

    start_date = models.DateField("დაწყების თარიღი")
    end_date = models.DateField("დასრულების თარიღი", null=True, blank=True)

    # მხოლოდ limited ტიპისთვის
    remaining_visits = models.PositiveIntegerField("დარჩენილი ვიზიტები", null=True, blank=True)

    status = models.CharField("სტატუსი", max_length=10, choices=STATUS_CHOICES, default="active")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["client", "status"]),
            models.Index(fields=["end_date"]),
        ]

    def __str__(self):
        return f"{self.client} • {self.membership.name} ({self.status})"

    def is_active(self) -> bool:
        if self.status != "active":
            return False

        today = now().date()
        mtype = self.membership.membership_type

        if mtype == "limited":
            return (self.remaining_visits or 0) > 0

        if mtype == "unlimited":
            return self.end_date is not None and self.end_date >= today

        if mtype == "fixed":
            if not self.end_date:
                return False
            return self.start_date <= today <= self.end_date

        return False


class Client(models.Model):
    GENDER_CHOICES = (
        ("male", "მამრობითი"),
        ("female", "მდედრობითი"),
        ("other", "სხვა"),
    )

    first_name = models.CharField("სახელი", max_length=100)
    last_name = models.CharField("გვარი", max_length=100)

    birth_date = models.DateField("დაბადების თარიღი", null=True, blank=True)
    gender = models.CharField("სქესი", max_length=10, choices=GENDER_CHOICES, null=True, blank=True)

    phone = models.CharField("ტელეფონი", max_length=20)
    email = models.EmailField("ელ. ფოსტა", blank=True)
    organization = models.CharField("ორგანიზაცია", max_length=150, blank=True)

    card_number = models.CharField("ბარათის ნომერი", max_length=50, blank=True, unique=True)

    photo = models.ImageField("ფოტოსურათი", upload_to="clients/photos/", null=True, blank=True)

    # --- აბონემენტის ველები (რაც უკვე გვქონდა)
    # trainer = models.ForeignKey(
    #     "Trainer", on_delete=models.SET_NULL, null=True, blank=True,
    #     related_name="clients", verbose_name="ტრენერი"
    # )
    created_at = models.DateTimeField("შექმნის დრო", auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def active_membership(self):
        today = now().date()
        return self.memberships.filter(status="active").filter(
            Q(membership__membership_type="limited", remaining_visits__gt=0) |
            Q(membership__membership_type="unlimited", end_date__gte=today) |
            Q(membership__membership_type="fixed", start_date__lte=today, end_date__gte=today)
        ).order_by("-created_at").first()

    def is_membership_active(self) -> bool:
        cm = self.active_membership
        return bool(cm and cm.is_active())


class Payment(models.Model):
    PAYMENT_METHODS = (
        ("cash", "ქეში"),
        ("card", "ბარათი"),
        ("transfer", "ტრანსფერი"),
    )

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="payments", verbose_name="კლიენტი")

    membership = models.ForeignKey(
        Membership, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payments", verbose_name="აბონემენტი"
    )

    trainer = models.ForeignKey(
        Trainer, on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payments", verbose_name="ტრენერი"
    )

    fixed_start = models.DateField("Fixed Start (თუ fixed)", null=True, blank=True)
    fixed_end = models.DateField("Fixed End (თუ fixed)", null=True, blank=True)

    membership_amount = models.DecimalField("აბონემენტის თანხა", max_digits=8, decimal_places=2, default=0)
    trainer_fee = models.DecimalField("ტრენერის თანხა", max_digits=8, decimal_places=2, default=0)

    amount = models.DecimalField("სულ თანხა", max_digits=8, decimal_places=2)

    method = models.CharField("გადახდის მეთოდი", max_length=20, choices=PAYMENT_METHODS)
    created_at = models.DateTimeField("გადახდის დრო", auto_now_add=True)

    def __str__(self):
        return f"{self.client} - {self.amount}₾"



class CheckIn(models.Model):
    client = models.ForeignKey(
        Client, on_delete=models.CASCADE,
        related_name="checkins", verbose_name="კლიენტი"
    )
    created_at = models.DateTimeField("შესვლის დრო", auto_now_add=True)

    def __str__(self):
        return f"{self.client} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
