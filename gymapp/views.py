from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Q
from django.db.models.functions import Coalesce

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from django.utils import timezone

from rest_framework import serializers, viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter

from django.utils.dateparse import parse_datetime

from .models import *


# =========================
# HTML Views
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
class TrainerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trainer
        fields = ["id", "first_name", "last_name", "phone", "specialization", "fee"]


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
            "comment",
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


class PaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField(read_only=True)
    membership_name = serializers.SerializerMethodField(read_only=True)
    trainer_name = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "operation_date",
            "client", "client_name",
            "membership", "membership_name",
            "trainer", "trainer_name",
            "fixed_start", "fixed_end",
            "membership_amount", "trainer_fee",
            "amount", "method", "client_membership",
            "created_at",
        ]
        read_only_fields = ["membership_amount", "trainer_fee"]

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
# ViewSets
# =========================
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





# =========================
# Reports (✅ ერთიანი, breakdown-ით)
# =========================
class ReportsViewSet(viewsets.ViewSet):


    @action(detail=False, methods=["get"])
    def active_members_by_trainer(self, request):
        """
        დღეს აქტიური კლიენტები ტრენერების მიხედვით (ბოლო Membership Payment-ის trainer-ით)
        """
        today = timezone.localdate()

        # აქტიური ClientMembership-ები დღეს
        active_cms = ClientMembership.objects.select_related("client").filter(status="active").filter(
            Q(membership__membership_type="limited", remaining_visits__gt=0) |
            Q(membership__membership_type="unlimited", end_date__gte=today) |
            Q(membership__membership_type="fixed", start_date__lte=today, end_date__gte=today)
        )

        # თითო client-ზე ვიპოვოთ ბოლო payment სადაც membership != null (აბონემენტის გაყიდვა)
        # (სწრაფი გზა: payments-ით group)
        latest_payments = (
            Payment.objects.filter(membership__isnull=False)
            .values("client_id")
            .annotate(last_id=Max("id"))
        )
        last_ids = [x["last_id"] for x in latest_payments]

        last_payments = Payment.objects.select_related("trainer").filter(id__in=last_ids)

        # map client -> trainer_name
        client_to_trainer = {}
        for p in last_payments:
            tname = str(p.trainer) if p.trainer else "უტრენერო"
            client_to_trainer[p.client_id] = tname

        # ახლა დავაჯგუფოთ active clients trainer-ზე
        buckets = {}
        for cm in active_cms:
            tname = client_to_trainer.get(cm.client_id, "უტრენერო")
            buckets.setdefault(tname, []).append(cm.client)

        rows = [
            {
                "trainer_name": k,
                "count": len(v),
                "clients": [{"id": c.id, "name": str(c), "phone": c.phone} for c in v]
            }
            for k, v in buckets.items()
        ]
        rows.sort(key=lambda r: r["count"], reverse=True)

        return Response({"rows": rows, "total_active": active_cms.values("client_id").distinct().count()})

    def _parse_date(self, s):
        if not s:
            return None
        try:
            y, m, d = str(s).split("-")
            return timezone.datetime(int(y), int(m), int(d)).date()
        except Exception:
            return None

    @action(detail=False, methods=["get"])
    def payments(self, request):
        qs = Payment.objects.select_related("client", "membership", "trainer").all()

        # --- date range (operation_date)
        dfrom = self._parse_date(request.query_params.get("date_from"))
        dto = self._parse_date(request.query_params.get("date_to"))
        if dfrom:
            qs = qs.filter(operation_date__date__gte=dfrom)
        if dto:
            qs = qs.filter(operation_date__date__lte=dto)

        # --- multi: trainer (id or "null")
        trainer_vals = request.query_params.getlist("trainer")
        if trainer_vals:
            q_tr = Q()
            for v in trainer_vals:
                if str(v).lower() == "null":
                    q_tr |= Q(trainer__isnull=True)
                else:
                    q_tr |= Q(trainer_id=int(v))
            qs = qs.filter(q_tr)

        # --- multi: method
        method_vals = request.query_params.getlist("method")
        if method_vals:
            qs = qs.filter(method__in=method_vals)

        # --- multi: membership (id or "null")
        membership_vals = request.query_params.getlist("membership")
        if membership_vals:
            q_m = Q()
            for v in membership_vals:
                if str(v).lower() == "null":
                    q_m |= Q(membership__isnull=True)
                else:
                    q_m |= Q(membership_id=int(v))
            qs = qs.filter(q_m)

        # --- multi: client ids
        client_vals = request.query_params.getlist("client")
        if client_vals:
            qs = qs.filter(client_id__in=[int(x) for x in client_vals])

        # --- free text search
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q) |
                Q(client__phone__icontains=q) |
                Q(client__card_number__icontains=q)
            )

        # --- amount range
        min_amount = request.query_params.get("min_amount")
        max_amount = request.query_params.get("max_amount")
        if min_amount not in (None, ""):
            qs = qs.filter(amount__gte=min_amount)
        if max_amount not in (None, ""):
            qs = qs.filter(amount__lte=max_amount)

        # ✅ “აბონემენტი გაიყიდა” = membership != null
        membership_sold_qs = qs.filter(membership__isnull=False)

        stats = {
            "payments_count": qs.count(),
            "total_amount": float(qs.aggregate(s=Sum("amount"))["s"] or 0),

            "memberships_sold_count": membership_sold_qs.count(),
            "memberships_sold_amount": float(membership_sold_qs.aggregate(s=Sum("amount"))["s"] or 0),
        }

        # ✅ breakdown: by trainer (მხოლოდ გაყიდული აბონემენტები)
        by_trainer = (
            membership_sold_qs
            .values("trainer_id", "trainer__first_name", "trainer__last_name")
            .annotate(cnt=Count("id"), total=Sum("amount"))
            .order_by("-cnt")
        )

        stats["by_trainer"] = [
            {
                "trainer_id": r["trainer_id"],
                "trainer_name": (f'{r["trainer__first_name"] or ""} {r["trainer__last_name"] or ""}').strip()
                               if r["trainer_id"] else "უტრენერო",
                "count": int(r["cnt"] or 0),
                "total": float(r["total"] or 0),
                "is_without_trainer": (r["trainer_id"] is None),
            }
            for r in by_trainer
        ]

        wt = membership_sold_qs.filter(trainer__isnull=True)
        stats["without_trainer_count"] = wt.count()
        stats["without_trainer_total"] = float(wt.aggregate(s=Sum("amount"))["s"] or 0)

        rows = PaymentSerializer(qs.order_by("-operation_date", "-id")[:2000], many=True).data

        client_ids = list(qs.values_list("client_id", flat=True).distinct())
        clients = ClientSerializer(
            Client.objects.filter(id__in=client_ids).order_by("last_name", "first_name"),
            many=True
        ).data

        return Response({
            "filters": {
                "date_from": str(dfrom) if dfrom else None,
                "date_to": str(dto) if dto else None,
                "trainer": trainer_vals,
                "method": method_vals,
                "membership": membership_vals,
                "client": client_vals,
                "q": q,
                "min_amount": min_amount,
                "max_amount": max_amount,
            },
            "stats": stats,
            "rows": rows,
            "clients": clients,
        })


# =========================
# Payments (create + patch override)
# =========================


class PaymentViewSet(viewsets.ModelViewSet):

    queryset = Payment.objects.select_related(
        "client",
        "membership",
        "trainer",
        "client_membership"
    ).all().order_by("-id")

    serializer_class = PaymentSerializer

    # --------------------------
    # helpers
    # --------------------------

    def _parse_date_or_none(self, s):
        if not s:
            return None
        try:
            y, m, d = str(s).split("-")
            return date(int(y), int(m), int(d))
        except Exception:
            return None

    def _parse_dt_or_none(self, s):
        if not s:
            return None
        dt = parse_datetime(str(s))
        if not dt:
            return None
        if timezone.is_naive(dt):
            dt = timezone.make_aware(dt, timezone.get_current_timezone())
        return dt

    def _parse_decimal_or_none(self, v):
        if v in (None, "", "null"):
            return None
        try:
            return Decimal(str(v))
        except Exception:
            return None

    # ----------------------------------------------------
    # CREATE PAYMENT
    # ----------------------------------------------------

    def create(self, request, *args, **kwargs):

        client_id = request.data.get("client")
        membership_id = request.data.get("membership")
        trainer_id = request.data.get("trainer")
        method = request.data.get("method")

        fixed_start = self._parse_date_or_none(request.data.get("fixed_start"))
        fixed_end = self._parse_date_or_none(request.data.get("fixed_end"))

        operation_date = self._parse_dt_or_none(
            request.data.get("operation_date")
        ) or timezone.now()

        total_override = self._parse_decimal_or_none(
            request.data.get("total_amount")
        )

        if not client_id or not method:
            return Response(
                {"detail": "client და method აუცილებელია"},
                status=400
            )

        # --------------------------
        # get client
        # --------------------------

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client ვერ მოიძებნა"}, status=404)

        # --------------------------
        # get membership
        # --------------------------

        membership = None

        if membership_id:
            try:
                membership = Membership.objects.get(id=membership_id)
            except Membership.DoesNotExist:
                return Response({"detail": "membership ვერ მოიძებნა"}, status=404)

        # --------------------------
        # get trainer
        # --------------------------

        trainer = None

        if trainer_id not in (None, "", "null"):
            try:
                trainer = Trainer.objects.get(id=trainer_id)
            except Trainer.DoesNotExist:
                return Response({"detail": "trainer ვერ მოიძებნა"}, status=404)

        # --------------------------
        # validate fixed membership
        # --------------------------

        if membership and membership.membership_type == "fixed":

            if not fixed_start or not fixed_end:
                return Response(
                    {"detail": "fixed ტიპზე აუცილებელია fixed_start და fixed_end"},
                    status=400
                )

            if fixed_end < fixed_start:
                return Response(
                    {"detail": "fixed_end არ შეიძლება იყოს fixed_start-ზე ადრე"},
                    status=400
                )

        # --------------------------
        # calculate amounts
        # --------------------------

        membership_amount = Decimal(str(membership.price)) if membership else Decimal("0")
        trainer_fee = Decimal(str(trainer.fee)) if trainer else Decimal("0")

        total_amount = (
            total_override
            if total_override is not None
            else membership_amount + trainer_fee
        )

        # --------------------------
        # create payment
        # --------------------------

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
            operation_date=operation_date,
        )

        # --------------------------
        # CREATE CLIENT MEMBERSHIP
        # --------------------------

        if membership:

            today = timezone.localdate()

            start_date = today
            end_date = None
            remaining_visits = None

            if membership.membership_type == "unlimited":

                if not membership.duration_days:
                    payment.delete()
                    return Response(
                        {"detail": "membership.duration_days ცარიელია"},
                        status=400
                    )

                end_date = today + timedelta(days=int(membership.duration_days))

            elif membership.membership_type == "limited":

                if not membership.visit_count:
                    payment.delete()
                    return Response(
                        {"detail": "membership.visit_count ცარიელია"},
                        status=400
                    )

                remaining_visits = int(membership.visit_count)

            elif membership.membership_type == "fixed":

                start_date = fixed_start
                end_date = fixed_end

            cm = ClientMembership.objects.create(
                client=client,
                membership=membership,
                start_date=start_date,
                end_date=end_date,
                remaining_visits=remaining_visits,
                status="active",
            )

            payment.client_membership = cm
            payment.save(update_fields=["client_membership"])

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )

    # ----------------------------------------------------
    # UPDATE PAYMENT
    # ----------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        payment = self.get_object()

        with transaction.atomic():
            cm = payment.client_membership
            if cm:
                cm.status = "expired"
                cm.save(update_fields=["status"])

                payment.client_membership = None
                payment.save(update_fields=["client_membership"])

            payment.delete()

        return Response(status=status.HTTP_204_NO_CONTENT)

    def partial_update(self, request, *args, **kwargs):

        payment = self.get_object()

        client_id = request.data.get("client", payment.client_id)
        membership_id = request.data.get("membership", payment.membership_id)
        trainer_id = request.data.get("trainer", payment.trainer_id)
        method = request.data.get("method", payment.method)

        fixed_start = (
            self._parse_date_or_none(request.data.get("fixed_start"))
            if "fixed_start" in request.data
            else payment.fixed_start
        )

        fixed_end = (
            self._parse_date_or_none(request.data.get("fixed_end"))
            if "fixed_end" in request.data
            else payment.fixed_end
        )

        operation_date = (
            self._parse_dt_or_none(request.data.get("operation_date"))
            if "operation_date" in request.data
            else payment.operation_date
        )

        total_override = self._parse_decimal_or_none(
            request.data.get("total_amount")
        )

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client ვერ მოიძებნა"}, status=404)

        membership = None

        if membership_id:
            try:
                membership = Membership.objects.get(id=membership_id)
            except Membership.DoesNotExist:
                return Response({"detail": "membership ვერ მოიძებნა"}, status=404)

        trainer = None

        if trainer_id not in (None, "", "null"):
            try:
                trainer = Trainer.objects.get(id=trainer_id)
            except Trainer.DoesNotExist:
                return Response({"detail": "trainer ვერ მოიძებნა"}, status=404)

        membership_amount = Decimal(str(membership.price)) if membership else Decimal("0")
        trainer_fee = Decimal(str(trainer.fee)) if trainer else Decimal("0")

        amount = (
            total_override
            if total_override is not None
            else membership_amount + trainer_fee
        )

        # --------------------------
        # UPDATE PAYMENT
        # --------------------------

        payment.client = client
        payment.membership = membership
        payment.trainer = trainer
        payment.fixed_start = fixed_start
        payment.fixed_end = fixed_end
        payment.method = method
        payment.operation_date = operation_date or timezone.now()
        payment.membership_amount = membership_amount
        payment.trainer_fee = trainer_fee
        payment.amount = amount

        payment.save()

        # --------------------------
        # UPDATE CLIENT MEMBERSHIP
        # --------------------------

        cm = payment.client_membership

        if cm and membership:

            today = timezone.localdate()

            start_date = today
            end_date = None
            remaining_visits = None

            if membership.membership_type == "unlimited":

                end_date = today + timedelta(days=int(membership.duration_days))

            elif membership.membership_type == "limited":

                remaining_visits = int(membership.visit_count)

            elif membership.membership_type == "fixed":

                start_date = fixed_start
                end_date = fixed_end

            cm.membership = membership
            cm.start_date = start_date
            cm.end_date = end_date
            cm.remaining_visits = remaining_visits
            cm.status = "active"

            cm.save()

        return Response(PaymentSerializer(payment).data, status=200)


class CheckInViewSet(viewsets.ModelViewSet):
    queryset = CheckIn.objects.select_related("client").all().order_by("-id")
    serializer_class = CheckInSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["client__first_name", "client__last_name", "client__phone", "client__card_number"]
    ordering_fields = ["id", "created_at"]

    def create(self, request, *args, **kwargs):
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

        if cm.membership.membership_type == "limited":
            cm.remaining_visits = max((cm.remaining_visits or 0) - 1, 0)
            if cm.remaining_visits == 0:
                cm.status = "expired"
            cm.save(update_fields=["remaining_visits", "status"])

        checkin = CheckIn.objects.create(client=client)
        return Response(CheckInSerializer(checkin).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def quick(self, request):
        card = (request.data.get("card_number") or "").strip()
        phone = (request.data.get("phone") or "").strip()

        if not card and not phone:
            return Response({"detail": "მიუთითე card_number ან phone"}, status=400)

        qs = Client.objects.all()
        qs = qs.filter(card_number=card) if card else qs.filter(phone=phone)

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