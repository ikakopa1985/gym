from datetime import date, timedelta

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now
from django.db.models import Sum, Count

from rest_framework import serializers, viewsets, status, mixins
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import *


# =========================
# HTML View (index.html)
# =========================

@login_required
def index(request):
    return render(request, "index.html")

@login_required
def clients_page(request):
    return render(request, "clients.html")

@login_required
def trainers_page(request):
    return render(request, "trainers.html")

@login_required
def memberships_page(request):
    return render(request, "memberships.html")

@login_required
def payments_page(request):
    return render(request, "payments.html")

@login_required
def checkins_page(request):
    return render(request, "checkins.html")

@login_required
def reports_page(request):
    return render(request, "reports.html")

# =========================
# Serializers
# =========================
from rest_framework import serializers
from .models import Trainer, Membership, Client, ClientMembership, Payment, CheckIn


class TrainerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trainer
        fields = ["id", "first_name", "last_name", "phone", "specialization","fee"]


class MembershipSerializer(serializers.ModelSerializer):
    class Meta:
        model = Membership
        fields = ["id", "name", "membership_type", "price", "duration_days", "visit_count"]

    def validate(self, attrs):
        mtype = attrs.get("membership_type", getattr(self.instance, "membership_type", None))
        duration = attrs.get("duration_days", getattr(self.instance, "duration_days", None))
        visits = attrs.get("visit_count", getattr(self.instance, "visit_count", None))

        if mtype == "unlimited" and not duration:
            raise serializers.ValidationError({"duration_days": "ულიმიტოსთვის duration_days აუცილებელია"})
        if mtype == "limited" and not visits:
            raise serializers.ValidationError({"visit_count": "რაოდენობრივისთვის visit_count აუცილებელია"})
        return attrs


class ClientSerializer(serializers.ModelSerializer):
    active_membership_id = serializers.SerializerMethodField(read_only=True)
    is_active = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name", "last_name",
            "birth_date", "gender",
            "phone", "email", "organization",
            "card_number", "photo",
            "active_membership_id", "is_active",
            "created_at",
        ]

    def get_active_membership_id(self, obj):
        cm = obj.active_membership
        return cm.id if cm else None

    def get_is_active(self, obj):
        return obj.is_membership_active()


class ClientMembershipSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField(read_only=True)
    membership_name = serializers.SerializerMethodField(read_only=True)
    membership_type = serializers.SerializerMethodField(read_only=True)
    is_active = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = ClientMembership
        fields = [
            "id",
            "client", "client_name",
            "membership", "membership_name", "membership_type",
            "start_date", "end_date",
            "remaining_visits",
            "status",
            "is_active",
            "created_at",
        ]

    def get_client_name(self, obj):
        return str(obj.client)

    def get_membership_name(self, obj):
        return obj.membership.name if obj.membership else None

    def get_membership_type(self, obj):
        return obj.membership.membership_type if obj.membership else None

    def get_is_active(self, obj):
        return obj.is_active()

    def validate(self, attrs):
        membership = attrs.get("membership", getattr(self.instance, "membership", None))
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        remaining = attrs.get("remaining_visits", getattr(self.instance, "remaining_visits", None))

        mtype = membership.membership_type if membership else None

        if not start:
            raise serializers.ValidationError({"start_date": "start_date აუცილებელია"})

        if mtype == "fixed" and not end:
            raise serializers.ValidationError({"end_date": "fixed ტიპისთვის end_date აუცილებელია"})

        if mtype == "limited" and (remaining is None):
            raise serializers.ValidationError({"remaining_visits": "limited ტიპისთვის remaining_visits აუცილებელია"})

        return attrs


class PaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField(read_only=True)
    membership_name = serializers.SerializerMethodField(read_only=True)
    trainer_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "client", "client_name",
            "membership", "membership_name",
            "trainer", "trainer_name",
            "fixed_start", "fixed_end",
            "membership_amount", "trainer_fee",
            "amount", "method",
            "created_at",
        ]
        read_only_fields = ["membership_amount", "trainer_fee", "amount"]

    def get_client_name(self, obj):
        return str(obj.client)

    def get_membership_name(self, obj):
        return obj.membership.name if obj.membership else None

    def get_trainer_name(self, obj):
        return str(obj.trainer) if obj.trainer else None



class CheckInSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CheckIn
        fields = ["id", "client", "client_name", "created_at"]

    def get_client_name(self, obj):
        return str(obj.client)


# =========================
# Helpers
# =========================

def assign_membership_to_client(client: Client, membership: Membership):
    client.active_membership = membership
    client.membership_start = now().date()

    if membership.membership_type == "unlimited":
        days = membership.duration_days or 30
        client.membership_end = now().date() + timedelta(days=days)
        client.remaining_visits = None
    else:
        client.remaining_visits = membership.visit_count or 0
        client.membership_end = None

    client.save()


def parse_date_or_none(s: str):
    if not s:
        return None
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except Exception:
        return None


# =========================
# ViewSets
# =========================
from datetime import timedelta
from django.utils.timezone import now
from django.db.models import Q, Sum
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from .models import *



class TrainerViewSet(viewsets.ModelViewSet):
    queryset = Trainer.objects.all().order_by("-id")
    serializer_class = TrainerSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["first_name", "last_name", "phone", "specialization"]
    ordering_fields = ["id", "first_name", "last_name"]


class MembershipViewSet(viewsets.ModelViewSet):
    queryset = Membership.objects.all().order_by("-id")
    serializer_class = MembershipSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["name", "membership_type"]
    ordering_fields = ["id", "price"]


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all().order_by("-id")
    serializer_class = ClientSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["first_name", "last_name", "phone", "email", "organization", "card_number"]
    ordering_fields = ["id", "created_at", "first_name", "last_name"]

    @action(detail=True, methods=["get"])
    def memberships(self, request, pk=None):
        client = self.get_object()
        qs = client.memberships.select_related("membership").all()
        return Response(ClientMembershipSerializer(qs, many=True).data)


class ClientMembershipViewSet(viewsets.ModelViewSet):
    queryset = ClientMembership.objects.select_related("client", "membership").all()
    serializer_class = ClientMembershipSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["client__first_name", "client__last_name", "membership__name", "status"]
    ordering_fields = ["id", "created_at", "start_date", "end_date"]


from decimal import Decimal
from datetime import timedelta
from django.utils.timezone import now
from rest_framework import status
from rest_framework.response import Response


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related("client", "membership", "trainer").all().order_by("-id")
    serializer_class = PaymentSerializer

    def _parse_date_or_none(self, s):
        if not s:
            return None
        try:
            y, m, d = str(s).split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None

    def create(self, request, *args, **kwargs):
        client_id = request.data.get("client")
        membership_id = request.data.get("membership")
        trainer_id = request.data.get("trainer")  # optional
        method = request.data.get("method")

        fixed_start = self._parse_date_or_none(request.data.get("fixed_start"))
        fixed_end = self._parse_date_or_none(request.data.get("fixed_end"))

        if not client_id or not method:
            return Response({"detail": "client და method აუცილებელია"}, status=400)

        # --- client
        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client ვერ მოიძებნა"}, status=404)

        # --- membership (optional)
        membership = None
        if membership_id:
            try:
                membership = Membership.objects.get(id=membership_id)
            except Membership.DoesNotExist:
                return Response({"detail": "membership ვერ მოიძებნა"}, status=404)

        # --- trainer (optional)  ✅ აქ აღარ არის client.trainer
        trainer = None
        if trainer_id:
            try:
                trainer = Trainer.objects.get(id=trainer_id)
            except Trainer.DoesNotExist:
                return Response({"detail": "trainer ვერ მოიძებნა"}, status=404)

        # --- fixed validation BEFORE creating payment
        if membership and membership.membership_type == "fixed":
            if not fixed_start or not fixed_end:
                return Response({"detail": "fixed ტიპზე აუცილებელია fixed_start და fixed_end"}, status=400)
            if fixed_end < fixed_start:
                return Response({"detail": "fixed_end არ შეიძლება იყოს fixed_start-ზე ადრე"}, status=400)

        # --- amounts
        membership_amount = Decimal(str(membership.price)) if membership else Decimal("0")
        trainer_fee = Decimal(str(trainer.fee)) if trainer else Decimal("0")
        total_amount = membership_amount + trainer_fee

        # --- create payment
        payment = Payment.objects.create(
            client=client,
            membership=membership,
            trainer=trainer,
            fixed_start=fixed_start,
            fixed_end=fixed_end,
            membership_amount=membership_amount,
            trainer_fee=trainer_fee,
            amount=total_amount,
            method=method,
        )

        # --- create ClientMembership if membership exists
        if membership:
            today = now().date()
            start_date = today
            end_date = None
            remaining_visits = None

            if membership.membership_type == "unlimited":
                if not membership.duration_days:
                    payment.delete()
                    return Response({"detail": "membership.duration_days ცარიელია"}, status=400)
                end_date = today + timedelta(days=int(membership.duration_days))

            elif membership.membership_type == "limited":
                if not membership.visit_count:
                    payment.delete()
                    return Response({"detail": "membership.visit_count ცარიელია"}, status=400)
                remaining_visits = int(membership.visit_count)

            elif membership.membership_type == "fixed":
                # fixed_start/fixed_end უკვე ვალიდირებულია ზემოთ
                start_date = fixed_start
                end_date = fixed_end

            # სურვილისამებრ: ძველი აქტიურების "expired" გაკეთება (თუ გინდა ერთდროულად ერთი აქტიური)
            # ClientMembership.objects.filter(client=client, status="active").update(status="expired")

            ClientMembership.objects.create(
                client=client,
                membership=membership,
                start_date=start_date,
                end_date=end_date,
                remaining_visits=remaining_visits,
                status="active",
            )

        return Response(PaymentSerializer(payment).data, status=status.HTTP_201_CREATED)



class CheckInViewSet(viewsets.ModelViewSet):
    queryset = CheckIn.objects.select_related("client").all().order_by("-id")
    serializer_class = CheckInSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["client__first_name", "client__last_name", "client__phone", "client__card_number"]
    ordering_fields = ["id", "created_at"]

    def create(self, request, *args, **kwargs):
        """
        Check-in:
        - ამოწმებს client.active_membership
        - თუ არ არის აქტიური -> 403
        - limited -> remaining_visits - 1
        """
        client_id = request.data.get("client")
        if not client_id:
            return Response({"detail": "client აუცილებელია"}, status=400)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client ვერ მოიძებნა"}, status=404)

        cm = client.active_membership
        if not cm or not cm.is_active():
            return Response({"detail": "აბონემენტი ვადაგასულია ან არ აქვს აქტიური"}, status=403)

        # limited -> ვიზიტი -1
        if cm.membership.membership_type == "limited":
            cm.remaining_visits = max((cm.remaining_visits or 0) - 1, 0)
            if cm.remaining_visits == 0:
                cm.status = "expired"
            cm.save(update_fields=["remaining_visits", "status"])

        checkin = CheckIn.objects.create(client=client)
        return Response(CheckInSerializer(checkin).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def quick(self, request):
        """
        სწრაფი Check-in ბარათის ნომრით ან ტელეფონით:
        POST /api/checkins/quick/
        body: { "card_number": "..."} or { "phone": "..." }
        """
        card = (request.data.get("card_number") or "").strip()
        phone = (request.data.get("phone") or "").strip()

        if not card and not phone:
            return Response({"detail": "მიუთითე card_number ან phone"}, status=400)

        qs = Client.objects.all()
        if card:
            qs = qs.filter(card_number=card)
        else:
            qs = qs.filter(phone=phone)

        client = qs.first()
        if not client:
            return Response({"detail": "კლიენტი ვერ მოიძებნა"}, status=404)

        cm = client.active_membership
        if not cm or not cm.is_active():
            return Response({"detail": "აბონემენტი ვადაგასულია ან არ აქვს აქტიური"}, status=403)

        if cm.membership.membership_type == "limited":
            cm.remaining_visits = max((cm.remaining_visits or 0) - 1, 0)
            if cm.remaining_visits == 0:
                cm.status = "expired"
            cm.save(update_fields=["remaining_visits", "status"])

        checkin = CheckIn.objects.create(client=client)
        return Response({
            "checkin": CheckInSerializer(checkin).data,
            "client": ClientSerializer(client).data,
            "client_membership": ClientMembershipSerializer(cm).data,
        }, status=201)


class ReportsViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["get"])
    def summary(self, request):
        """
        GET /api/reports/summary/
        """
        today = now().date()
        month_start = today.replace(day=1)

        # შემოსავლები
        today_income = Payment.objects.filter(created_at__date=today).aggregate(s=Sum("amount"))["s"] or 0
        month_income = Payment.objects.filter(created_at__date__gte=month_start).aggregate(s=Sum("amount"))["s"] or 0

        # აქტიურ/ვადაგასულ კლიენტებს დათვლით “აქტიური აბონემენტით”
        cms = ClientMembership.objects.select_related("membership").filter(status="active")

        active_count = 0
        expired_count = 0
        for cm in cms:
            if cm.is_active():
                active_count += 1
            else:
                expired_count += 1

        today_checkins = CheckIn.objects.filter(created_at__date=today).count()

        return Response({
            "today": str(today),
            "today_income": float(today_income),
            "month_income": float(month_income),
            "today_checkins": today_checkins,
            "active_memberships": active_count,
            "expired_memberships": expired_count,
        })
