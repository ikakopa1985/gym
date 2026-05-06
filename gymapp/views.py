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
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Max
from django.http import JsonResponse
from  gym.services.zk_listener    import start, stop, imitate
from pyzkaccess import ZKAccess, ZK200, ZK100, ZK400
from pyzkaccess.tables import *
from datetime import datetime
import time
from decimal import Decimal
from django.db.models import DecimalField
from pyzkaccess.common import ZKDatetimeUtils
from pyzkaccess.enums import VerifyMode, PassageDirection
import asyncio
from gym.settings import ipSettings
from django.db.models import Prefetch
from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout

from .models import *


zktIp =  ipSettings


# =========================
# HTML Views
# =========================
@login_required
def index(request):
    # client = Client.objects.all()
    # for item in client:
    #     name = item.first_name
    #
    #     name = name.replace("j", "ჯ")
    #     name = name.replace("C", "ჩ")
    #
    #
    #     item.first_name = name
    #     item.save()
    #
    #     last_name = item.last_name
    #     last_name = last_name.replace("j", "ჯ")
    #     last_name = last_name.replace("C", "ჩ")
    #     item.last_name = last_name
    #     item.save()

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

@login_required
def card_payments_page(request):
    return render(request, "card_payments.html")



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

    active_membership_id = serializers.SerializerMethodField()
    is_active = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = [
            "id",
            "first_name",
            "last_name",
            "passId",
            "birth_date",
            "gender",
            "phone",
            "email",
            "organization",
            "card_number",
            "photo",
            "comment",
            "active_membership_id",
            "is_active",
            "created_at",
        ]

    def get_active_membership_id(self, obj):
        cm = obj.active_membership
        return cm.id if cm else None

    def get_is_active(self, obj):
        return obj.active_membership is not None


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
    search_fields = ["first_name", "last_name", "card_number"]
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


class ReportsViewSet(viewsets.ViewSet):

    def _parse_date(self, s):
        if not s:
            return None
        try:
            y, m, d = str(s).split("-")
            return timezone.datetime(int(y), int(m), int(d)).date()
        except Exception:
            return None

    @action(detail=False, methods=["get"])
    def active_members_by_trainer(self, request):
        today = timezone.localdate()

        active_cms = ClientMembership.objects.select_related("client").filter(status="active").filter(
            Q(membership__membership_type="limited", remaining_visits__gt=0) |
            Q(membership__membership_type="unlimited", end_date__gte=today) |
            Q(membership__membership_type="fixed", start_date__lte=today, end_date__gte=today)
        )

        latest_payments = (
            Payment.objects.filter(membership__isnull=False)
            .values("client_id")
            .annotate(last_id=Max("id"))
        )
        last_ids = [x["last_id"] for x in latest_payments]

        last_payments = Payment.objects.select_related("trainer").filter(id__in=last_ids)

        client_to_trainer = {}
        for p in last_payments:
            tname = str(p.trainer) if p.trainer else "უტრენერო"
            client_to_trainer[p.client_id] = tname

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

        return Response({
            "rows": rows,
            "total_active": active_cms.values("client_id").distinct().count()
        })

    @action(detail=False, methods=["get"])
    def summary(self, request):
        today = timezone.localdate()
        month_start = today.replace(day=1)

        today_checkins = CheckIn.objects.filter(created_at__date=today).count()

        payments_today = Payment.objects.filter(operation_date__date=today)
        payments_month = Payment.objects.filter(operation_date__date__gte=month_start)

        memberships_sold_today_qs = payments_today.filter(membership__isnull=False)
        memberships_sold_today_count = memberships_sold_today_qs.count()
        memberships_sold_today_amount = memberships_sold_today_qs.aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]

        card_payments_today_qs = CardPayment.objects.filter(operation_date__date=today)
        card_payments_today_count = card_payments_today_qs.count()
        card_payments_today_amount = card_payments_today_qs.aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]

        today_income = payments_today.aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]

        month_income = payments_month.aggregate(
            s=Coalesce(Sum("amount"), Decimal("0.00"))
        )["s"]

        def by_method(qs, method):
            return qs.filter(method=method).aggregate(
                s=Coalesce(Sum("amount"), Decimal("0.00"))
            )["s"]

        active_memberships = ClientMembership.objects.filter(status="active").count()
        expired_memberships = ClientMembership.objects.filter(status="expired").count()

        return Response({
            "today_checkins": today_checkins,
            "today_income": float(today_income or 0),
            "month_income": float(month_income or 0),

            "today_cash": float(by_method(payments_today, "cash") or 0),
            "today_card": float(by_method(payments_today, "card") or 0),
            "today_transfer": float(by_method(payments_today, "transfer") or 0),

            "month_cash": float(by_method(payments_month, "cash") or 0),
            "month_card": float(by_method(payments_month, "card") or 0),
            "month_transfer": float(by_method(payments_month, "transfer") or 0),

            "active_memberships": active_memberships,
            "expired_memberships": expired_memberships,

            "memberships_sold_today_count": memberships_sold_today_count,
            "memberships_sold_today_amount": float(memberships_sold_today_amount or 0),

            "card_payments_today_count": card_payments_today_count,
            "card_payments_today_amount": float(card_payments_today_amount or 0),
        })

    @action(detail=False, methods=["get"])
    def payments(self, request):
        qs = Payment.objects.select_related("client", "membership", "trainer").all()

        dfrom = self._parse_date(request.query_params.get("date_from"))
        dto = self._parse_date(request.query_params.get("date_to"))
        if dfrom:
            qs = qs.filter(operation_date__date__gte=dfrom)
        if dto:
            qs = qs.filter(operation_date__date__lte=dto)

        trainer_vals = request.query_params.getlist("trainer")
        if trainer_vals:
            q_tr = Q()
            for v in trainer_vals:
                if str(v).lower() == "null":
                    q_tr |= Q(trainer__isnull=True)
                else:
                    q_tr |= Q(trainer_id=int(v))
            qs = qs.filter(q_tr)

        method_vals = request.query_params.getlist("method")
        if method_vals:
            qs = qs.filter(method__in=method_vals)

        membership_vals = request.query_params.getlist("membership")
        if membership_vals:
            q_m = Q()
            for v in membership_vals:
                if str(v).lower() == "null":
                    q_m |= Q(membership__isnull=True)
                else:
                    q_m |= Q(membership_id=int(v))
            qs = qs.filter(q_m)

        client_vals = request.query_params.getlist("client")
        if client_vals:
            qs = qs.filter(client_id__in=[int(x) for x in client_vals])

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q) |
                Q(client__phone__icontains=q) |
                Q(client__card_number__icontains=q) |
                Q(client__passId__icontains=q)
            )

        min_amount = request.query_params.get("min_amount")
        max_amount = request.query_params.get("max_amount")
        if min_amount not in (None, ""):
            qs = qs.filter(amount__gte=min_amount)
        if max_amount not in (None, ""):
            qs = qs.filter(amount__lte=max_amount)

        membership_sold_qs = qs.filter(membership__isnull=False)

        stats = {
            "payments_count": qs.count(),
            "total_amount": float(qs.aggregate(s=Sum("amount"))["s"] or 0),
            "memberships_sold_count": membership_sold_qs.count(),
            "memberships_sold_amount": float(membership_sold_qs.aggregate(s=Sum("amount"))["s"] or 0),
        }

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

    @action(detail=False, methods=["get"])
    def membership_sales(self, request):
        qs = Payment.objects.select_related("client", "trainer", "membership").filter(
            membership__isnull=False
        )

        dfrom = self._parse_date(request.query_params.get("date_from"))
        dto = self._parse_date(request.query_params.get("date_to"))
        if dfrom:
            qs = qs.filter(operation_date__date__gte=dfrom)
        if dto:
            qs = qs.filter(operation_date__date__lte=dto)

        trainer_vals = request.query_params.getlist("trainer")
        if trainer_vals:
            q_tr = Q()
            for v in trainer_vals:
                if str(v).lower() == "null":
                    q_tr |= Q(trainer__isnull=True)
                else:
                    q_tr |= Q(trainer_id=int(v))
            qs = qs.filter(q_tr)

        method_vals = request.query_params.getlist("method")
        if method_vals:
            qs = qs.filter(method__in=method_vals)

        membership_vals = request.query_params.getlist("membership")
        if membership_vals:
            qs = qs.filter(membership_id__in=[int(x) for x in membership_vals])

        client_vals = request.query_params.getlist("client")
        if client_vals:
            qs = qs.filter(client_id__in=[int(x) for x in client_vals])

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q) |
                Q(client__phone__icontains=q) |
                Q(client__card_number__icontains=q) |
                Q(client__passId__icontains=q)
            )

        rows = [
            {
                "id": p.id,
                "date": p.operation_date,
                "client_id": p.client_id,
                "client_name": str(p.client),
                "membership_id": p.membership_id,
                "membership_name": p.membership.name if p.membership else None,
                "membership_amount": float(p.membership_amount or 0),
                "trainer_id": p.trainer_id,
                "trainer_name": str(p.trainer) if p.trainer else "უტრენერო",
                "method": p.method,
            }
            for p in qs.order_by("-operation_date", "-id")[:3000]
        ]

        total = qs.aggregate(s=Coalesce(Sum("membership_amount"), Decimal("0.00")))["s"]

        return Response({
            "count": qs.count(),
            "total_membership_amount": float(total or 0),
            "rows": rows,
        })

    @action(detail=False, methods=["get"])
    def card_payments_report(self, request):
        qs = CardPayment.objects.select_related("client").all()

        dfrom = self._parse_date(request.query_params.get("date_from"))
        dto = self._parse_date(request.query_params.get("date_to"))
        if dfrom:
            qs = qs.filter(operation_date__date__gte=dfrom)
        if dto:
            qs = qs.filter(operation_date__date__lte=dto)

        client_vals = request.query_params.getlist("client")
        if client_vals:
            qs = qs.filter(client_id__in=[int(x) for x in client_vals])

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q) |
                Q(client__phone__icontains=q) |
                Q(client__card_number__icontains=q) |
                Q(client__passId__icontains=q)
            )

        min_amount = request.query_params.get("min_amount")
        max_amount = request.query_params.get("max_amount")
        if min_amount not in (None, ""):
            qs = qs.filter(amount__gte=min_amount)
        if max_amount not in (None, ""):
            qs = qs.filter(amount__lte=max_amount)

        rows = [
            {
                "id": r.id,
                "date": r.operation_date,
                "client_id": r.client_id,
                "client_name": str(r.client),
                "amount": float(r.amount or 0),
            }
            for r in qs.order_by("-operation_date", "-id")[:3000]
        ]

        total = qs.aggregate(s=Coalesce(Sum("amount"), Decimal("0.00")))["s"]

        return Response({
            "count": qs.count(),
            "total_amount": float(total or 0),
            "rows": rows,
        })

    @action(detail=False, methods=["get"])
    def active_clients_report(self, request):
        today = timezone.localdate()

        qs = ClientMembership.objects.select_related("client", "membership").filter(
            status="active"
        ).filter(
            Q(membership__membership_type="limited", remaining_visits__gt=0) |
            Q(membership__membership_type="unlimited", end_date__gte=today) |
            Q(membership__membership_type="fixed", start_date__lte=today, end_date__gte=today)
        )

        membership_vals = request.query_params.getlist("membership")
        if membership_vals:
            qs = qs.filter(membership_id__in=[int(x) for x in membership_vals])

        client_vals = request.query_params.getlist("client")
        if client_vals:
            qs = qs.filter(client_id__in=[int(x) for x in client_vals])

        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(client__first_name__icontains=q) |
                Q(client__last_name__icontains=q) |
                Q(client__phone__icontains=q) |
                Q(client__card_number__icontains=q) |
                Q(client__passId__icontains=q)
            )

        rows = [
            {
                "id": cm.id,
                "client_id": cm.client_id,
                "client_name": str(cm.client),
                "membership_id": cm.membership_id,
                "membership_name": cm.membership.name if cm.membership else None,
                "start_date": cm.start_date,
                "end_date": cm.end_date,
                "remaining_visits": cm.remaining_visits,
                "status": cm.status,
            }
            for cm in qs.order_by("client__last_name", "client__first_name")[:3000]
        ]

        return Response({
            "count": qs.values("client_id").distinct().count(),
            "rows": rows,
        })


def OpenDoor(request):
    stop()
    # asyncio.sleep(1)
    time.sleep(1)
    connstr = f"protocol=TCP,ipaddress={zktIp},port=4370,timeout=4000,passwd="
    try:
        with ZKAccess(connstr=connstr, device_model=ZK200) as zk:
            zk.doors[0].relays.switch_on(4)
            print('opened')
    except Exception as ex:
        print(str(ex))
        stop()
        return JsonResponse({"status": "error"})
    # asyncio.sleep(1)
    time.sleep(1)
    start()
    return JsonResponse({"status": "ok"})


def sync(request):
    clients = Client.objects.filter(
        memberships__status="active"
    ).distinct()
    for client in clients:
        print(client.id, client.card_number)
        insertor_update_new_user(pin=str(client.id),card=client.card_number)
    return JsonResponse({"status": "ok"})


def syncpartial(request):
    stop()
    # asyncio.sleep(2)
    time.sleep(2)
    print("partial sync")
    rows = ClientSync.objects.select_related("client").filter(
        status__in=["pending", "error"]
    )
    for row in rows:
        try:
            if row.action == "add":
                insertor_update_new_user(
                    pin=str(row.client.id),
                    card=row.client.card_number
                )
            elif row.action == "delete":
                delete_user(
                    pin=str(row.client.id)
                )

            row.status = "done"
            row.synced_at = timezone.now()
            row.error = ""


        except Exception as e:

            row.status = "error"
            row.error = str(e)

        row.save(update_fields=["status", "error", "synced_at"])
    # asyncio.sleep(3)
    time.sleep(2)
    start()
    return JsonResponse({"status": "ok"})


def insertor_update_new_user(ip=zktIp, pin="123", card='123456', password='3467'):
    print("insertor_update_new_user")
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    my_user = User(card=card, pin=pin, password=password, super_authorize=False)
    print("added",my_user)
    zk.table(User).upsert(my_user)
    access = UserAuthorize(
        pin=pin,
        doors=(True, True, True, True),
        timezone_id=1
    )
    zk.table(UserAuthorize).upsert(access)


def get_logs_users(ip=zktIp):
    stop()
    print("get_logs")
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    records = zk.table('User')
    for record in records:
        print(record)  # prints all users from the table
    start()


def get_logs_UserAuthorize(ip=zktIp):
    stop()
    print("get_logs")
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    # records = zk.table('User')
    # records = zk.table('Transaction')
    records = zk.table('UserAuthorize')
    for record in records:
        print(record)  # prints all users from the table
    start()


def get_transaction_logs(ip=zktIp):
    stop()
    print("get_logs")
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    events = zk.table('Transaction')
    for e in events:
        epin = e.pin
        etime = e.time
        print(epin, etime)
        if ord(epin) != 4:
            try:
                client = Client.objects.get(id=int(epin))
                CheckIn.objects.get_or_create(
                    client=client,
                    created_at=etime
                )
            except Client.DoesNotExist:
                print("client not found")
            # events.delete(e)
    start()


def del_logs(ip=zktIp):
    stop()
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    events = zk.table("Transaction")
    # zk.table('Transaction').delete_all()
    for e in events:
        epin = e.pin
        etime = e.time
        print(epin, etime)
        try:
            client = Client.objects.get(id=int(epin))
            CheckIn.objects.get_or_create(
                client=client,
                created_at=etime
            )
        except Client.DoesNotExist:
            print("client not found")
        events.delete(e)
    start()
        # print(e,"deleted")


def delete_user(pin, ip=zktIp):
    zk = ZKAccess(f"protocol=TCP,ipaddress={ip},port=4370,timeout=4000,passwd=")
    zk.table('User').where(pin=pin).delete_all()
    zk.table("UserAuthorize").where(pin=pin).delete_all()
    print("delete_user", pin)


def zk_start(request):

    start()
    return JsonResponse({"status": "started"})


def zk_stop(request):

    stop()
    return JsonResponse({"status": "stopped"})



def zk_imitate(request):

    imitate()
    return JsonResponse({"status": "stopped"})


class PaymentViewSet(viewsets.ModelViewSet):

    queryset = Payment.objects.select_related(
        "client",
        "membership",
        "trainer",
        "client_membership"
    ).all().order_by("-id")

    serializer_class = PaymentSerializer

    # ----------------------------------------------------
    # HELPERS
    # ----------------------------------------------------

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
    # RECALC MEMBERSHIPS
    # ----------------------------------------------------

    def _recalc_client_memberships(self, client):
        """
        კლიენტის ყველა membership გადავამოწმოთ
        """
        cms = client.memberships.select_related("membership").all()

        for cm in cms:

            if cm.is_active():

                if cm.status != "active":
                    cm.status = "active"
                    cm.save(update_fields=["status"])

            else:

                if cm.status != "expired":
                    cm.status = "expired"
                    cm.save(update_fields=["status"])

    # ----------------------------------------------------
    # CREATE PAYMENT
    # ----------------------------------------------------

    def create(self, request, *args, **kwargs):

        with transaction.atomic():

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
                return Response({"detail": "client და method აუცილებელია"}, status=400)

            client = Client.objects.get(id=client_id)

            membership = None
            if membership_id:
                membership = Membership.objects.get(id=membership_id)

            trainer = None
            if trainer_id not in (None, "", "null"):
                trainer = Trainer.objects.get(id=trainer_id)

            membership_amount = Decimal(str(membership.price)) if membership else Decimal("0")
            trainer_fee = Decimal(str(trainer.fee)) if trainer else Decimal("0")

            total_amount = (
                total_override
                if total_override is not None
                else membership_amount + trainer_fee
            )

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

            if membership:

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

            # 🔹 recalculation
            self._recalc_client_memberships(client)

        return Response(
            PaymentSerializer(payment).data,
            status=status.HTTP_201_CREATED
        )

    # ----------------------------------------------------
    # UPDATE PAYMENT
    # ----------------------------------------------------

    def partial_update(self, request, *args, **kwargs):

        with transaction.atomic():

            payment = self.get_object()

            client = payment.client

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

            client = Client.objects.get(id=client_id)

            membership = None
            if membership_id:
                membership = Membership.objects.get(id=membership_id)

            trainer = None
            if trainer_id not in (None, "", "null"):
                trainer = Trainer.objects.get(id=trainer_id)

            membership_amount = Decimal(str(membership.price)) if membership else Decimal("0")
            trainer_fee = Decimal(str(trainer.fee)) if trainer else Decimal("0")

            amount = (
                total_override
                if total_override is not None
                else membership_amount + trainer_fee
            )

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

            cm = payment.client_membership

            if cm and not membership:

                cm.status = "expired"
                cm.save(update_fields=["status"])

                payment.client_membership = None
                payment.save(update_fields=["client_membership"])

            elif cm and membership:

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

            elif membership and not cm:

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

            # 🔹 recalculation
            self._recalc_client_memberships(client)

        return Response(PaymentSerializer(payment).data)

    # ----------------------------------------------------
    # DELETE PAYMENT
    # ----------------------------------------------------

    def destroy(self, request, *args, **kwargs):

        payment = self.get_object()

        with transaction.atomic():

            client = payment.client
            cm = payment.client_membership

            if cm:
                cm.status = "expired"
                cm.save(update_fields=["status"])

            payment.delete()

            # 🔹 recalculation
            self._recalc_client_memberships(client)

        return Response(status=status.HTTP_204_NO_CONTENT)


class CheckInViewSet(viewsets.ModelViewSet):
    queryset = CheckIn.objects.select_related("client").all().order_by("-id")
    serializer_class = CheckInSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["client__first_name", "client__last_name", "client__phone", "client__card_number"]
    ordering_fields = ["id", "created_at"]

    def create(self, request, *args, **kwargs):
        # print(1)
        client_id = request.data.get("client")
        if not client_id:
            return Response({"detail": "client აუცილებელია"}, status=400)

        try:
            # print(2)
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "client ვერ მოიძებნა"}, status=404)
        # print(3)
        cm = client.active_membership
        if not cm:
            return Response({"detail": "კლიენტს არ აქვს აქტიური აბონემენტი"}, status=403)
        if cm.membership.membership_type == "limited":
            cm.remaining_visits = max((cm.remaining_visits or 0) - 1, 0)
            if cm.remaining_visits == 0:
                cm.status = "expired"
            cm.save(update_fields=["remaining_visits", "status"])

        # OpenDoor()
        # insertor_update_new_user(pin="101", card='123456', password='4321')
        # delete_user("123456")
        # del_logs()
        # get_logs_users()
        # get_logs_UserAuthorize()
        # sync()
        checkin = CheckIn.objects.create(client=client)
        OpenDoor(request)

        return Response({
            "checkin": CheckInSerializer(checkin).data,
            "client": ClientSerializer(client).data,
            "client_membership": ClientMembershipSerializer(cm).data,
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"])
    def quick(self, request):
        card = (request.data.get("card_number") or "").strip()
        phone = (request.data.get("phone") or "").strip()

        if not card and not phone:
            return Response({"detail": "მიუთითე card_number ან phone"}, status=400)

        qs = Client.objects.all()

        if card:
            qs = qs.filter(
                Q(card_number__icontains=card) |
                Q(passId__icontains=card)
            )
        elif phone:
            qs = qs.filter(phone__icontains=phone)

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
        OpenDoor()
        return Response({
            "checkin": CheckInSerializer(checkin).data,
            "client": ClientSerializer(client).data,
            "client_membership": ClientMembershipSerializer(cm).data,
        }, status=201)




def sync_status(request):

    pending = ClientSync.objects.filter(status="pending").count()
    error = ClientSync.objects.filter(status="error").count()

    return JsonResponse({
        "pending": pending,
        "error": error
    })





class CardPaymentSerializer(serializers.ModelSerializer):
    client_name = serializers.SerializerMethodField()
    client_card_number = serializers.CharField(source="client.card_number", read_only=True)
    client_first_name = serializers.CharField(source="client.first_name", read_only=True)
    client_last_name = serializers.CharField(source="client.last_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)
    client_passId = serializers.CharField(source="client.passId", read_only=True)
    client_comment = serializers.CharField(source="client.comment", read_only=True)

    class Meta:
        model = CardPayment
        fields = [
            "id",
            "client",
            "client_name",
            "client_card_number",
            "client_first_name",
            "client_last_name",
            "client_phone",
            "client_passId",
            "client_comment",
            "amount",
            "method",
            "operation_date",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}"



class CardPaymentViewSet(viewsets.ModelViewSet):
    serializer_class = CardPaymentSerializer
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = [
        "client__first_name",
        "client__last_name",
        "client__phone",
        "client__card_number",
        "client__passId",
    ]
    ordering_fields = ["operation_date", "created_at", "amount", "id"]
    ordering = ["-operation_date", "-id"]

    def get_queryset(self):
        qs = CardPayment.objects.select_related("client").all().order_by("-operation_date", "-id")

        date_from = self.request.query_params.get("date_from")
        date_to = self.request.query_params.get("date_to")
        client_id = self.request.query_params.get("client")

        if client_id:
            qs = qs.filter(client_id=client_id)
        if date_from:
            qs = qs.filter(operation_date__date__gte=date_from)
        if date_to:
            qs = qs.filter(operation_date__date__lte=date_to)

        return qs

    def create(self, request, *args, **kwargs):
        client_id = request.data.get("client")
        amount = request.data.get("amount")
        operation_date = request.data.get("operation_date")
        nc_card = request.data.get("nc_card")
        method = request.data.get("method")

        if not client_id or amount in (None, ""):
            return Response({"detail": "client და amount აუცილებელია"}, status=400)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "კლიენტი ვერ მოიძებნა"}, status=404)

        if nc_card not in (None, "", "null"):
            client.card_number = str(nc_card).strip()
            client.save(update_fields=["card_number"])

        serializer = self.get_serializer(data={
            "client": client.id,
            "amount": amount,
            "method": method,  # ✅
            "operation_date": operation_date,
        })
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()

        client_id = request.data.get("client", instance.client_id)
        nc_card = request.data.get("nc_card", None)

        try:
            client = Client.objects.get(id=client_id)
        except Client.DoesNotExist:
            return Response({"detail": "კლიენტი ვერ მოიძებნა"}, status=404)

        if nc_card not in (None, "", "null"):
            client.card_number = str(nc_card).strip()
            client.save(update_fields=["card_number"])

        data = request.data.copy()
        data["client"] = client.id

        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)




def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")  # უკვე შესულია

    error = None

    if request.method == "POST":
        username = request.POST.get("username")
        password = request.POST.get("password")

        user = authenticate(request, username=username, password=password)

        if user:
            login(request, user)
            return redirect("/")
        else:
            error = "არასწორი მომხმარებელი ან პაროლი"

    return render(request, "login.html", {"error": error})


def logout_view(request):
    logout(request)
    return redirect("login")


